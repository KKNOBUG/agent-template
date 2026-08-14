from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import re
import shutil
import socket
import subprocess
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import requests
from sqlalchemy import case, delete, func, literal, select, text, update
from sqlalchemy.exc import IntegrityError

from applications.code_server_ide.dependencies import CurrentUser
from applications.code_server_ide.config import settings
from applications.code_server_ide.database import get_db_session
from applications.code_server_ide.models.ide import IdePermissionConfig, IdeProjectRecord, IdeSessionRecord

logger = logging.getLogger(__name__)
CLAUDE_ENGINEERING_PREFIX = "/claudeEngineering"


class IdeError(RuntimeError):
    pass


class IdeForbidden(IdeError):
    pass


class IdeNotFound(IdeError):
    pass


class IdeSessionInactive(IdeError):
    pass


class IdeCapacityExceeded(IdeError):
    pass


class IdeSessionGone(IdeError):
    pass


@dataclass(frozen=True)
class ProjectContext:
    project_id: str
    owner_user_id: str
    system_id: str


@dataclass(frozen=True)
class WebSocketProxyTarget:
    upstream_url: str
    container_id: str | None
    workspace_writable: bool


class IdeService:
    def __init__(self) -> None:
        self.image = settings.ide_image
        self.network = settings.ide_docker_network
        self.container_prefix = settings.ide_container_prefix
        self.uid = settings.ide_uid
        self.sessions_root = Path(settings.ide_sessions_root).expanduser()
        self.compose_file = Path(__file__).resolve().parents[1] / "resources" / "docker-compose.yml"
        self._reclaimer_task: asyncio.Task[None] | None = None

    def start_background_tasks(self) -> None:
        if self._reclaimer_task is None or self._reclaimer_task.done():
            self._reclaimer_task = asyncio.create_task(self._reclaimer_loop())

    async def stop_background_tasks(self) -> None:
        if self._reclaimer_task is None:
            return
        self._reclaimer_task.cancel()
        try:
            await self._reclaimer_task
        except asyncio.CancelledError:
            pass
        self._reclaimer_task = None

    async def ensure_session(self, user: CurrentUser, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        project = await self.resolve_project_context(user, payload or {})
        await self.require_view_project(user, project)
        can_edit = await self.can_edit_project(user, project)
        record = await self.get_or_create_session_record(user, project, can_edit)
        await self.start_session(record)
        now = datetime.now()
        await self.update_record(
            record.session_id,
            last_seen_at=now,
            last_user_activity_at=now,
            idle_pending_at=None,
            busy_reason=None,
        )
        return await self.session_payload(record.session_id, user)

    async def list_projects(self, user: CurrentUser) -> list[dict[str, Any]]:
        config = await self.permission_config()
        stmt = select(IdeProjectRecord).order_by(IdeProjectRecord.updated_at.desc())
        if not user.is_super_admin and not config.allow_view_other_users_projects:
            stmt = stmt.where(IdeProjectRecord.owner_user_id == user.user_id)
        async with get_db_session() as db:
            result = await db.execute(stmt)
            records = list(result.scalars().all())
        return [await self.project_payload(record, user) for record in records]

    async def create_project(self, user: CurrentUser, payload: dict[str, Any]) -> dict[str, Any]:
        name = str(payload.get("name") or "").strip()
        if not name:
            raise IdeError("Project name cannot be empty")
        system_id = self.normalize_id(str(payload.get("system_id") or payload.get("system") or "default"))
        project_id = self.normalize_id(str(payload.get("project_id") or f"{system_id}-{uuid.uuid4().hex[:12]}"))
        record = IdeProjectRecord(
            project_id=project_id,
            name=name[:200],
            owner_user_id=user.user_id,
            system_id=system_id,
            description=str(payload.get("description") or "")[:500] or None,
        )
        async with get_db_session() as db:
            db.add(record)
            await db.commit()
            await db.refresh(record)
        return await self.project_payload(record, user)

    async def delete_project(
        self,
        user: CurrentUser,
        project_id: str,
        delete_workspace: bool = False,
    ) -> dict[str, Any]:
        project = await self.find_project(self.normalize_id(project_id))
        if project is None:
            raise IdeNotFound("Project not found")
        if not user.is_super_admin and project.owner_user_id != user.user_id:
            raise IdeForbidden("Only the project owner or super administrator can delete this project")

        async with get_db_session() as db:
            result = await db.execute(
                select(IdeSessionRecord).where(IdeSessionRecord.project_id == project.project_id),
            )
            session_records = list(result.scalars().all())

        removed_containers = 0
        for record in session_records:
            removed_containers += await self.stop_and_remove_session_container(record)

        project_root = self.sessions_root / project.system_id / project.project_id
        workspace_deleted = False
        if delete_workspace:
            workspace_deleted = await asyncio.to_thread(self.remove_project_directory, project_root)

        async with get_db_session() as db:
            await db.execute(delete(IdeSessionRecord).where(IdeSessionRecord.project_id == project.project_id))
            await db.execute(delete(IdeProjectRecord).where(IdeProjectRecord.project_id == project.project_id))
            await db.commit()

        return {
            "project_id": project.project_id,
            "deleted_sessions": len(session_records),
            "removed_containers": removed_containers,
            "workspace_deleted": workspace_deleted,
            "workspace_retained": not workspace_deleted,
            "workspace_root": str(project_root),
        }

    async def session_payload(self, session_id: str, user: CurrentUser) -> dict[str, Any]:
        record = await self.require_session(session_id)
        record, can_edit = await self.sync_session_access(user, record)
        running = await asyncio.to_thread(self.container_running, record.container_name)
        status = self.effective_container_status(record.status, running)
        if status != record.status:
            await self.update_record(record.session_id, status=status)
        return {
            "session_id": record.session_id,
            "project_id": record.project_id,
            "system_id": record.system_id,
            "container_name": record.container_name,
            "compose_project": record.compose_project,
            "running": running,
            "status": status,
            "proxy_url": f"{record.proxy_path}?folder=/home/coder/project",
            "workspace_dir": record.workspace_dir,
            "runtime_dir": record.runtime_dir,
            "workspace_writable": record.workspace_writable,
            "claude_writable": True,
            "can_edit": can_edit,
            "host_port": record.host_port,
            "active_ws_count": record.active_ws_count,
            "last_seen_at": self.iso(record.last_seen_at),
            "last_heartbeat_at": self.iso(record.last_heartbeat_at),
            "last_user_activity_at": self.iso(record.last_user_activity_at),
            "idle_pending_at": self.iso(record.idle_pending_at),
            "last_busy_at": self.iso(record.last_busy_at),
            "busy_reason": record.busy_reason,
        }

    async def heartbeat(self, session_id: str, user: CurrentUser, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        record = await self.require_session(session_id)
        record, _can_edit = await self.sync_session_access(user, record)
        now = datetime.now()
        payload = payload or {}
        user_activity_at = self.normalize_activity_time(payload.get("last_user_activity_at"), record, now)
        has_new_user_activity = bool(
            user_activity_at
            and (record.last_user_activity_at is None or user_activity_at > record.last_user_activity_at)
        )
        values: dict[str, Any] = {
            "last_seen_at": now,
            "last_heartbeat_at": now,
        }
        if has_new_user_activity:
            values["last_user_activity_at"] = user_activity_at
            values["status"] = "RUNNING" if record.status == "IDLE_PENDING" else record.status
            values["idle_pending_at"] = None
            values["busy_reason"] = None
        await self.update_record(
            session_id,
            **values,
        )
        return await self.session_payload(session_id, user)

    async def stop_session(self, session_id: str, user: CurrentUser) -> dict[str, Any]:
        if not user.is_super_admin:
            raise IdeForbidden("Only super administrators can stop IDE containers")
        record = await self.require_session(session_id)
        await self.stop_session_record(record, stopped_by=user.user_id)
        return self.record_payload(await self.require_session(session_id))

    async def list_sessions(self, user: CurrentUser, filters: dict[str, str | None]) -> list[dict[str, Any]]:
        if not user.is_super_admin:
            raise IdeForbidden("Only super administrators can list IDE sessions")
        stmt = select(IdeSessionRecord).order_by(IdeSessionRecord.updated_at.desc())
        if filters.get("status"):
            stmt = stmt.where(IdeSessionRecord.status == filters["status"])
        if filters.get("user_id"):
            stmt = stmt.where(IdeSessionRecord.user_id == filters["user_id"])
        if filters.get("project_id"):
            stmt = stmt.where(IdeSessionRecord.project_id == filters["project_id"])
        if filters.get("system_id"):
            stmt = stmt.where(IdeSessionRecord.system_id == filters["system_id"])
        async with get_db_session() as db:
            result = await db.execute(stmt.limit(200))
            records = list(result.scalars().all())
        now = datetime.now()
        refreshed_records = [await self.refresh_busy_observation(record, now) for record in records]
        return [self.record_payload(record) for record in refreshed_records]

    async def proxy_http(
        self,
        session_id: str,
        user: CurrentUser,
        path: str,
        method: str,
        headers: dict[str, str],
        query: bytes,
        body: bytes,
    ) -> requests.Response:
        record = await self.require_session(session_id)
        record, _can_edit = await self.sync_session_access(user, record)
        self.require_proxy_active(record)
        if not await asyncio.to_thread(self.container_running, record.container_name):
            await self.start_session(record)
        await self.touch(record.session_id)

        upstream = f"{self.upstream_base_url(record)}/{path}"
        if query:
            upstream += "?" + query.decode("latin-1")

        excluded = {"host", "content-length", "connection", "upgrade", "proxy-connection", "accept-encoding"}
        proxy_headers = {k: v for k, v in headers.items() if k.lower() not in excluded}
        proxy_headers["Accept-Encoding"] = "identity"

        return await asyncio.to_thread(
            requests.request,
            method,
            upstream,
            headers=proxy_headers,
            data=body,
            allow_redirects=False,
            timeout=60.0,
        )

    async def proxy_ws_connect(self, session_id: str, user: CurrentUser, path: str, query: str) -> WebSocketProxyTarget:
        record = await self.require_session(session_id)
        record, _can_edit = await self.sync_session_access(user, record)
        self.require_proxy_active(record)
        if not await asyncio.to_thread(self.container_running, record.container_name):
            await self.start_session(record)
            record = await self.require_session(session_id)
        await self.increment_ws(record.session_id, 1)
        upstream_base = self.upstream_base_url(record).replace("http://", "ws://").replace("https://", "wss://")
        return WebSocketProxyTarget(
            upstream_url=f"{upstream_base}/{path}" + (f"?{query}" if query else ""),
            container_id=record.container_id,
            workspace_writable=record.workspace_writable,
        )

    async def assert_ws_proxy_current(
        self,
        session_id: str,
        user: CurrentUser,
        target: WebSocketProxyTarget,
    ) -> None:
        record = await self.require_session(session_id)
        record, _can_edit = await self.sync_session_access(user, record)
        self.require_proxy_active(record)
        if record.status == "CREATING":
            raise IdeSessionGone("IDE session permissions changed; reconnect the workspace")
        if not await asyncio.to_thread(self.container_running, record.container_name):
            raise IdeSessionGone("IDE session is not running; reconnect the workspace")
        if target.container_id and record.container_id != target.container_id:
            raise IdeSessionGone("IDE session container changed; reconnect the workspace")
        if record.workspace_writable != target.workspace_writable:
            raise IdeSessionGone("IDE session permissions changed; reconnect the workspace")
        mount = await asyncio.to_thread(self.container_workspace_mount, record.container_name)
        if mount is None:
            raise IdeSessionGone("IDE session workspace mount changed; reconnect the workspace")
        _mount_source, mount_writable = mount
        if mount_writable != record.workspace_writable:
            raise IdeSessionGone("IDE session workspace permissions changed; reconnect the workspace")

    async def proxy_ws_disconnect(self, session_id: str) -> None:
        await self.increment_ws(session_id, -1)

    @staticmethod
    def require_proxy_active(record: IdeSessionRecord) -> None:
        if record.status in {"STOPPING", "STOPPED"}:
            raise IdeSessionGone("IDE session is stopped; reopen the workspace to reconnect")
        if record.status == "FAILED":
            raise IdeSessionInactive("IDE session is failed; reconnect from the workspace entry")

    @staticmethod
    def preserves_idle_pending_for_busy_reason(busy_reason: str) -> bool:
        return busy_reason == "cpu_active"

    @staticmethod
    def effective_container_status(record_status: str, running: bool) -> str:
        if running:
            if record_status in {"CREATING", "STOPPED", "FAILED"}:
                return "RUNNING"
            return record_status
        if record_status in {"CREATING", "RUNNING", "IDLE_PENDING", "STOPPING"}:
            return "STOPPED"
        return record_status

    @staticmethod
    def last_user_activity_anchor(record: Any) -> datetime:
        return record.last_user_activity_at or record.started_at or record.created_at or datetime.now()

    @staticmethod
    def has_user_activity_after_idle_pending(record: Any) -> bool:
        return bool(
            record.last_user_activity_at
            and record.idle_pending_at
            and record.last_user_activity_at > record.idle_pending_at
        )

    @staticmethod
    def clears_idle_pending_to_running(values: dict[str, Any]) -> bool:
        return (
            values.get("status") == "RUNNING"
            and "idle_pending_at" in values
            and values.get("idle_pending_at") is None
            and "busy_reason" in values
            and values.get("busy_reason") is None
        )

    async def resolve_project_context(self, user: CurrentUser, payload: dict[str, Any]) -> ProjectContext:
        project_id = str(payload.get("project_id") or payload.get("session_id") or "default")
        project = await self.find_project(self.normalize_id(project_id))
        if project is None:
            raise IdeNotFound("Project not found")
        return ProjectContext(
            project_id=project.project_id,
            owner_user_id=project.owner_user_id,
            system_id=project.system_id,
        )

    async def find_project(self, project_id: str) -> IdeProjectRecord | None:
        async with get_db_session() as db:
            result = await db.execute(
                select(IdeProjectRecord).where(IdeProjectRecord.project_id == project_id),
            )
            return result.scalar_one_or_none()

    async def project_payload(self, record: IdeProjectRecord, user: CurrentUser) -> dict[str, Any]:
        project = ProjectContext(
            project_id=record.project_id,
            owner_user_id=record.owner_user_id,
            system_id=record.system_id,
        )
        can_edit = await self.can_edit_project(user, project)
        return {
            "project_id": record.project_id,
            "id": record.project_id,
            "name": record.name,
            "owner_user_id": record.owner_user_id,
            "owner": record.owner_user_id,
            "system_id": record.system_id,
            "system": record.system_id,
            "description": record.description,
            "can_edit": can_edit,
            "shared_claude_writable": True,
            "can_delete": user.is_super_admin or record.owner_user_id == user.user_id,
            "permission": "editable" if can_edit else "read_only",
            "created_at": self.iso(record.created_at),
            "updated_at": self.iso(record.updated_at),
        }

    async def get_or_create_session_record(
        self,
        user: CurrentUser,
        project: ProjectContext,
        can_edit: bool,
    ) -> IdeSessionRecord:
        existing = await self.find_session_by_user_project(user.user_id, project.project_id)
        runtime_dir = self.user_runtime_dir(project, user.user_id)
        workspace_dir = self.project_workspace_dir(project)
        if existing:
            updates: dict[str, Any] = {}
            expected_runtime_dir = str(runtime_dir)
            expected_workspace_dir = str(workspace_dir)
            expected_proxy_path = self.session_proxy_path(existing.session_id)
            if existing.runtime_dir != expected_runtime_dir:
                updates["runtime_dir"] = expected_runtime_dir
                existing.runtime_dir = expected_runtime_dir
            if existing.workspace_dir != expected_workspace_dir:
                updates["workspace_dir"] = expected_workspace_dir
                existing.workspace_dir = expected_workspace_dir
            if existing.workspace_writable != can_edit:
                updates["workspace_writable"] = can_edit
                existing.workspace_writable = can_edit
            if existing.proxy_path != expected_proxy_path:
                updates["proxy_path"] = expected_proxy_path
                existing.proxy_path = expected_proxy_path
            if updates:
                await self.update_record(existing.session_id, **updates)
            await self.ensure_record_host_port(existing)
            return existing

        session_id = self.normalize_id(f"{user.user_id}-{project.project_id}")[:150]
        container_name = self.normalize_container_name(f"{self.container_prefix}-{user.user_id}-{project.project_id}")
        compose_project = self.normalize_compose_project(f"ide-{session_id}")
        proxy_path = self.session_proxy_path(session_id)

        await self.enforce_container_capacity()

        last_error: Exception | None = None
        for _ in range(10):
            host_port = await self.allocate_host_port()
            record = IdeSessionRecord(
                session_id=session_id,
                user_id=user.user_id,
                project_id=project.project_id,
                project_owner_user_id=project.owner_user_id,
                system_id=project.system_id,
                compose_project=compose_project,
                container_name=container_name,
                host_port=host_port,
                status="CREATING",
                workspace_dir=str(workspace_dir),
                runtime_dir=str(runtime_dir),
                workspace_writable=can_edit,
                proxy_path=proxy_path,
                last_seen_at=datetime.now(),
                last_user_activity_at=datetime.now(),
            )
            try:
                async with get_db_session() as db:
                    db.add(record)
                    await db.commit()
                    await db.refresh(record)
                return record
            except IntegrityError as exc:
                last_error = exc
                existing = await self.find_session_by_user_project(user.user_id, project.project_id)
                if existing:
                    expected_proxy_path = self.session_proxy_path(existing.session_id)
                    await self.update_record(
                        existing.session_id,
                        workspace_dir=str(workspace_dir),
                        runtime_dir=str(runtime_dir),
                        workspace_writable=can_edit,
                        proxy_path=expected_proxy_path,
                    )
                    existing.workspace_dir = str(workspace_dir)
                    existing.runtime_dir = str(runtime_dir)
                    existing.workspace_writable = can_edit
                    existing.proxy_path = expected_proxy_path
                    await self.ensure_record_host_port(existing)
                    return existing
        raise IdeError(f"Unable to allocate IDE host port: {last_error}")

    @staticmethod
    def session_proxy_path(session_id: str) -> str:
        return f"{CLAUDE_ENGINEERING_PREFIX}/ide/sessions/{session_id}/proxy/"

    def user_runtime_dir(self, project: ProjectContext, user_id: str) -> Path:
        return self.sessions_root / project.system_id / project.project_id / self.normalize_id(user_id)

    def project_workspace_dir(self, project: ProjectContext) -> Path:
        return self.user_runtime_dir(project, project.owner_user_id) / "workspace"

    async def find_session_by_user_project(self, user_id: str, project_id: str) -> IdeSessionRecord | None:
        async with get_db_session() as db:
            result = await db.execute(
                select(IdeSessionRecord).where(
                    IdeSessionRecord.user_id == user_id,
                    IdeSessionRecord.project_id == project_id,
                ),
            )
            return result.scalar_one_or_none()

    async def require_session(self, session_id: str) -> IdeSessionRecord:
        async with get_db_session() as db:
            result = await db.execute(
                select(IdeSessionRecord).where(IdeSessionRecord.session_id == self.normalize_id(session_id)),
            )
            record = result.scalar_one_or_none()
        if record is None:
            raise IdeNotFound("IDE session not found")
        return record

    async def require_view_record(self, user: CurrentUser, record: IdeSessionRecord) -> None:
        await self.project_context_for_record(user, record)

    async def project_context_for_record(self, user: CurrentUser, record: IdeSessionRecord) -> ProjectContext:
        if record.user_id != user.user_id:
            raise IdeForbidden("No permission to access this IDE session")
        project_record = await self.find_project(record.project_id)
        if project_record is None:
            raise IdeNotFound("Project not found")
        project = ProjectContext(
            project_id=project_record.project_id,
            owner_user_id=project_record.owner_user_id,
            system_id=project_record.system_id,
        )
        await self.require_view_project(user, project)
        return project

    async def sync_session_access(
        self,
        user: CurrentUser,
        record: IdeSessionRecord,
    ) -> tuple[IdeSessionRecord, bool]:
        project = await self.project_context_for_record(user, record)
        can_edit = await self.can_edit_project(user, project)
        expected_runtime_dir = str(self.user_runtime_dir(project, record.user_id))
        expected_workspace_dir = str(self.project_workspace_dir(project))
        updates: dict[str, Any] = {}
        remount_needed = False

        if record.project_owner_user_id != project.owner_user_id:
            updates["project_owner_user_id"] = project.owner_user_id
            record.project_owner_user_id = project.owner_user_id
            remount_needed = True
        if record.system_id != project.system_id:
            updates["system_id"] = project.system_id
            record.system_id = project.system_id
            remount_needed = True

        if record.runtime_dir != expected_runtime_dir:
            updates["runtime_dir"] = expected_runtime_dir
            record.runtime_dir = expected_runtime_dir
            remount_needed = True
        if record.workspace_dir != expected_workspace_dir:
            updates["workspace_dir"] = expected_workspace_dir
            record.workspace_dir = expected_workspace_dir
            remount_needed = True
        if record.workspace_writable != can_edit:
            updates["workspace_writable"] = can_edit
            record.workspace_writable = can_edit
            remount_needed = True

        running = await asyncio.to_thread(self.container_running, record.container_name)
        if running:
            mount = await asyncio.to_thread(self.container_workspace_mount, record.container_name)
            if mount is None:
                remount_needed = True
            else:
                mount_source, mount_writable = mount
                if mount_writable != can_edit or not self.same_path(mount_source, expected_workspace_dir):
                    remount_needed = True

        if updates:
            await self.update_record(record.session_id, **updates)
        if running and remount_needed:
            await self.stop_session_for_remount(record)
        return record, can_edit

    async def require_view_project(self, user: CurrentUser, project: ProjectContext) -> None:
        config = await self.permission_config()
        if user.is_super_admin or project.owner_user_id == user.user_id or config.allow_view_other_users_projects:
            return
        raise IdeForbidden("No permission to view this project")

    async def can_edit_project(self, user: CurrentUser, project: ProjectContext) -> bool:
        config = await self.permission_config()
        return (
            user.is_super_admin
            or project.owner_user_id == user.user_id
            or config.allow_cross_user_edit_in_system
        )

    async def permission_config(self) -> IdePermissionConfig:
        try:
            async with get_db_session() as db:
                result = await db.execute(select(IdePermissionConfig).where(IdePermissionConfig.id == 1))
                config = result.scalar_one_or_none()
                if config:
                    return config
        except Exception:
            pass
        return IdePermissionConfig(
            id=1,
            allow_view_other_users_projects=settings.allow_view_other_users_projects,
            allow_cross_user_edit_in_system=settings.allow_cross_user_edit_in_system,
        )

    def prepare_dirs(self, record: IdeSessionRecord) -> None:
        runtime_dir = self.safe_session_path(record.runtime_dir)
        workspace_dir = self.safe_session_path(record.workspace_dir)
        claude_dir = self.claude_dir_for_record(record)
        workspace_dir.mkdir(parents=True, exist_ok=True)
        for name in (".local", ".config"):
            (runtime_dir / name).mkdir(parents=True, exist_ok=True)
        self.prepare_code_server_settings(runtime_dir)
        self.write_compose_env(record)
        self.prepare_mount_permissions(runtime_dir, workspace_dir, claude_dir, record.workspace_writable)

    def claude_dir_for_record(self, record: IdeSessionRecord) -> Path:
        return self.safe_session_path(record.workspace_dir) / ".claude"

    def safe_session_path(self, value: str) -> Path:
        path = Path(value).expanduser().absolute()
        root = self.sessions_root.expanduser().absolute()
        if not self.is_relative_to(path, root):
            raise IdeError(f"IDE path escapes session root: {value}")
        return path

    def owns_session_record(self, record: IdeSessionRecord) -> bool:
        try:
            runtime_dir = Path(record.runtime_dir).expanduser().absolute()
            sessions_root = self.sessions_root.expanduser().absolute()
        except (OSError, RuntimeError):
            return False
        return self.is_relative_to(runtime_dir, sessions_root)

    def remove_project_directory(self, project_root: Path) -> bool:
        target = project_root.expanduser().absolute()
        root = self.sessions_root.expanduser().absolute()
        if target == root or not self.is_relative_to(target, root):
            raise IdeError(f"IDE project path escapes session root: {project_root}")
        if not target.exists():
            return False
        shutil.rmtree(target)
        return True

    @staticmethod
    def is_relative_to(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    def prepare_code_server_settings(self, runtime_dir: Path) -> None:
        settings_path = runtime_dir / ".config" / "code-server" / "User" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        data: dict[str, Any] = {}
        changed = False
        if settings_path.exists():
            try:
                data = json.loads(settings_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                data = {}
                changed = True
        if "security.workspace.trust.enabled" not in data:
            data["security.workspace.trust.enabled"] = False
            changed = True
        if "workbench.startupEditor" not in data:
            data["workbench.startupEditor"] = "none"
            changed = True
        if settings_path.exists() and not changed:
            return
        settings_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def write_compose_env(self, record: IdeSessionRecord) -> None:
        runtime_dir = self.safe_session_path(record.runtime_dir)
        workspace_dir = self.safe_session_path(record.workspace_dir)
        if not record.host_port:
            raise IdeError(f"IDE session {record.session_id} has no host port")
        env = {
            "IDE_IMAGE": self.image,
            "IDE_DOCKER_NETWORK": self.network,
            "IDE_CONTAINER_NAME": record.container_name,
            "SESSION_ID": record.session_id,
            "USER_ID": record.user_id,
            "PROJECT_ID": record.project_id,
            "SYSTEM_ID": record.system_id,
            "IDE_HOST_PORT": str(record.host_port),
            "IDE_CODE_SERVER_AUTH": settings.ide_code_server_auth,
            "WORKSPACE_DIR": str(workspace_dir),
            "WORKSPACE_MOUNT_MODE": "rw" if record.workspace_writable else "ro",
            "CLAUDE_DIR": str(self.claude_dir_for_record(record)),
            "CLAUDE_MOUNT_MODE": "rw",
            "CONFIG_DIR": str(runtime_dir / ".config"),
            "LOCAL_DIR": str(runtime_dir / ".local"),
            "IDE_MEMORY_LIMIT": settings.ide_memory_limit,
            "IDE_MEMORY_SWAP_LIMIT": settings.ide_memory_swap_limit,
            "IDE_CPU_LIMIT": settings.ide_cpu_limit,
            "IDE_PIDS_LIMIT": settings.ide_pids_limit,
            "COCO_NPM_REGISTRY": settings.coco_npm_registry,
            "COCO_PIP_INDEX_URL": settings.coco_pip_index_url,
            "COCO_PIP_TRUSTED_HOST": settings.coco_pip_trusted_host,
        }
        (runtime_dir / "compose.env").write_text(
            "\n".join(f"{key}={value}" for key, value in env.items()) + "\n",
            encoding="utf-8",
        )

    def prepare_mount_permissions(
        self,
        runtime_dir: Path,
        workspace_dir: Path,
        claude_dir: Path,
        workspace_writable: bool,
    ) -> None:
        claude_mount_mode = "rw"
        args = [
            "run",
            "--rm",
            "--entrypoint",
            "sh",
            "-v",
            f"{claude_dir}:/home/coder/project/.claude:{claude_mount_mode}",
            "-v",
            f"{claude_dir}:/home/coder/.claude:{claude_mount_mode}",
            "-v",
            f"{runtime_dir / '.config'}:/home/coder/.config",
            "-v",
            f"{runtime_dir / '.local'}:/home/coder/.local",
            self.image,
            "-lc",
            (
                "mkdir -p /home/coder/project/.claude /home/coder/.claude /home/coder/.config /home/coder/.local; "
                f"chown -R {self.uid} /home/coder/project/.claude /home/coder/.claude /home/coder/.config /home/coder/.local 2>/dev/null || true; "
                "chmod -R u+rwX,g+rwX /home/coder/project/.claude /home/coder/.claude /home/coder/.config /home/coder/.local 2>/dev/null || true"
            ),
        ]
        if workspace_writable:
            args[4:4] = [
                "-v",
                f"{workspace_dir}:/home/coder/project",
            ]
            args[-1] = (
                "mkdir -p /home/coder/project /home/coder/project/.claude /home/coder/.claude /home/coder/.config /home/coder/.local; "
                f"chown -R {self.uid} /home/coder/project /home/coder/project/.claude /home/coder/.claude /home/coder/.config /home/coder/.local 2>/dev/null || true; "
                "chmod -R u+rwX,g+rwX /home/coder/project /home/coder/project/.claude /home/coder/.claude /home/coder/.config /home/coder/.local 2>/dev/null || true"
            )
        self.run_docker(args)

    async def start_session(self, record: IdeSessionRecord) -> None:
        last_error: Exception | None = None
        for attempt in range(3):
            await self.ensure_record_host_port(record)
            if await asyncio.to_thread(self.container_running, record.container_name):
                container_id = await asyncio.to_thread(self.container_id, record.container_name)
                started_at = record.started_at or datetime.now()
                await self.update_record(
                    record.session_id,
                    status="RUNNING",
                    container_id=container_id,
                    started_at=started_at,
                    error_message=None,
                )
                record.status = "RUNNING"
                record.container_id = container_id
                record.started_at = started_at
                record.error_message = None
                return
            await self.enforce_container_capacity()
            await asyncio.to_thread(self.prepare_dirs, record)
            await asyncio.to_thread(self.ensure_network)
            args = [*self.compose_args(record), "up", "-d"]
            try:
                await asyncio.to_thread(self.run_docker, args)
                container_id = await asyncio.to_thread(self.container_id, record.container_name)
                await asyncio.to_thread(self.wait_for_code_server_ready, record)
                started_at = datetime.now()
                await self.update_record(
                    record.session_id,
                    status="RUNNING",
                    container_id=container_id,
                    started_at=started_at,
                    error_message=None,
                )
                record.status = "RUNNING"
                record.container_id = container_id
                record.started_at = started_at
                record.error_message = None
                return
            except Exception as exc:
                last_error = exc
                if attempt < 2 and self.is_port_bind_error(str(exc)):
                    await self.assign_new_host_port(record)
                    continue
                if attempt < 2 and self.is_transient_start_error(str(exc)):
                    await self.update_record(record.session_id, status="CREATING", error_message=str(exc))
                    record.status = "CREATING"
                    time.sleep(2.0)
                    continue
                await self.update_record(record.session_id, status="FAILED", error_message=str(exc))
                raise
        if last_error:
            await self.update_record(record.session_id, status="FAILED", error_message=str(last_error))
            raise last_error

    async def enforce_container_capacity(self) -> None:
        limit = int(settings.ide_max_running_containers)
        if limit <= 0:
            return
        running_count = await asyncio.to_thread(self.running_ide_container_count)
        if running_count >= limit:
            raise IdeCapacityExceeded("目前使用人数过多，请稍后再试")

    async def stop_session_record(self, record: IdeSessionRecord, stopped_by: str) -> None:
        if await asyncio.to_thread(self.container_exists, record.container_name):
            await asyncio.to_thread(self.stop_container, record.container_name)
        await self.update_record(
            record.session_id,
            status="STOPPED",
            active_ws_count=0,
            idle_pending_at=None,
            busy_reason=None,
            stopped_by=stopped_by,
            stopped_at=datetime.now(),
        )

    async def stop_and_remove_session_container(self, record: IdeSessionRecord) -> int:
        if not self.owns_session_record(record):
            raise IdeError("Refusing to remove a container outside the IDE sessions root")
        if not await asyncio.to_thread(self.container_exists, record.container_name):
            return 0
        if await asyncio.to_thread(self.container_running, record.container_name):
            await asyncio.to_thread(self.stop_container, record.container_name)
        removed = await asyncio.to_thread(self.remove_container, record.container_name)
        return 1 if removed else 0

    async def stop_session_for_remount(self, record: IdeSessionRecord) -> None:
        if await asyncio.to_thread(self.container_exists, record.container_name):
            await asyncio.to_thread(self.stop_container, record.container_name)
        await self.update_record(
            record.session_id,
            status="CREATING",
            active_ws_count=0,
            busy_reason="permission_remount",
            stopped_by="permission-sync",
            stopped_at=datetime.now(),
        )
        record.status = "CREATING"
        record.active_ws_count = 0
        record.busy_reason = "permission_remount"

    def compose_args(self, record: IdeSessionRecord) -> list[str]:
        env_file = self.safe_session_path(record.runtime_dir) / "compose.env"
        return [
            "compose",
            "--env-file",
            str(env_file),
            "-f",
            str(self.compose_file),
            "-p",
            record.compose_project,
        ]

    def ensure_network(self) -> None:
        result = self.docker(["network", "inspect", self.network], check=False)
        if result.returncode != 0:
            self.run_docker(["network", "create", self.network])

    def container_exists(self, name: str) -> bool:
        return self.docker(["inspect", name], check=False).returncode == 0

    def stop_container(self, name: str) -> None:
        self.run_docker(
            ["stop", "-t", str(settings.ide_docker_stop_timeout_seconds), name],
            settings.ide_docker_stop_timeout_seconds + 15,
        )

    def remove_container(self, name: str) -> bool:
        result = self.docker(["rm", name], check=False)
        if result.returncode == 0:
            return True
        message = f"{result.stdout}\n{result.stderr}".lower()
        if "no such container" in message:
            return False
        raise IdeError(f"Failed to remove IDE container {name}: {result.stderr or result.stdout}")

    def running_ide_container_count(self) -> int:
        result = self.docker(["ps", "--format", "{{.Names}}"], check=False)
        if result.returncode != 0:
            raise IdeError(f"Failed to list IDE containers: {result.stderr or result.stdout}")
        prefix = f"{self.container_prefix}-"
        return sum(1 for name in result.stdout.splitlines() if name.strip().startswith(prefix))

    def container_running(self, name: str) -> bool:
        result = self.docker(["inspect", "-f", "{{.State.Running}}", name], check=False)
        return result.returncode == 0 and result.stdout.strip().lower() == "true"

    def container_id(self, name: str) -> str:
        result = self.run_docker(["inspect", "-f", "{{.Id}}", name])
        return result.stdout.strip()

    def container_bound_host_port(self, name: str, container_port: str = "8080/tcp") -> int | None:
        result = self.docker(["inspect", name], check=False)
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout)
        ports = data[0].get("NetworkSettings", {}).get("Ports", {})
        bindings = ports.get(container_port) or []
        if not bindings:
            return None
        host_port = bindings[0].get("HostPort")
        return int(host_port) if host_port else None

    def container_workspace_mount(self, name: str) -> tuple[str, bool] | None:
        result = self.docker(["inspect", name], check=False)
        if result.returncode != 0:
            return None
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return None
        mounts = data[0].get("Mounts", []) if data else []
        for mount in mounts:
            if mount.get("Destination") == "/home/coder/project":
                return str(mount.get("Source") or ""), bool(mount.get("RW"))
        return None

    def container_ip(self, name: str) -> str:
        result = self.run_docker(["inspect", name])
        data = json.loads(result.stdout)
        networks = data[0].get("NetworkSettings", {}).get("Networks", {})
        network = networks.get(self.network) or next(iter(networks.values()), {})
        ip = network.get("IPAddress", "")
        if not ip:
            raise IdeError(f"Cannot resolve container IP for {name}")
        return ip

    def upstream_base_url(self, record: IdeSessionRecord) -> str:
        if record.host_port:
            return f"http://127.0.0.1:{record.host_port}"
        return f"http://{self.container_ip(record.container_name)}:8080"

    def ready_probe_url(self, record: IdeSessionRecord) -> str:
        return f"{self.upstream_base_url(record)}/healthz"

    def wait_for_code_server_ready(self, record: IdeSessionRecord, timeout_seconds: float = 60.0) -> None:
        deadline = time.monotonic() + timeout_seconds
        last_error = ""
        while time.monotonic() < deadline:
            if not self.container_running(record.container_name):
                last_error = "container is not running"
                break
            try:
                response = requests.get(
                    self.ready_probe_url(record),
                    headers={"Accept-Encoding": "identity"},
                    timeout=3.0,
                )
                if response.status_code < 500:
                    return
                last_error = f"HTTP {response.status_code}"
            except requests.RequestException as exc:
                last_error = str(exc)
            time.sleep(1.0)
        raise IdeError(f"code-server did not become ready for {record.session_id}: {last_error}")

    async def ensure_record_host_port(self, record: IdeSessionRecord) -> None:
        if record.host_port:
            if await asyncio.to_thread(self.container_running, record.container_name):
                actual_port = await asyncio.to_thread(self.container_bound_host_port, record.container_name)
                if actual_port == int(record.host_port):
                    return
                if actual_port:
                    await self.update_record(record.session_id, host_port=actual_port)
                    record.host_port = actual_port
                    return
            if await asyncio.to_thread(self.host_port_available, int(record.host_port)):
                return
        await self.assign_new_host_port(record)

    async def assign_new_host_port(self, record: IdeSessionRecord) -> None:
        last_error: Exception | None = None
        for _ in range(10):
            host_port = await self.allocate_host_port(exclude_session_id=record.session_id)
            try:
                await self.update_record(record.session_id, host_port=host_port)
                record.host_port = host_port
                return
            except IntegrityError as exc:
                last_error = exc
                continue
        raise IdeError(f"Unable to allocate IDE host port: {last_error}")

    @staticmethod
    def is_port_bind_error(message: str) -> bool:
        lowered = message.lower()
        return (
            "port is already allocated" in lowered
            or "bind" in lowered and "address already in use" in lowered
            or "ports are not available" in lowered
        )

    @staticmethod
    def is_transient_start_error(message: str) -> bool:
        lowered = message.lower()
        return (
            "remotedisconnected" in lowered
            or "remote end closed connection" in lowered
            or "connection aborted" in lowered
            or "connection reset" in lowered
            or "container is not running" in lowered
        )

    @staticmethod
    def same_path(left: str, right: str) -> bool:
        return os.path.normcase(os.path.abspath(left)) == os.path.normcase(os.path.abspath(right))

    async def allocate_host_port(self, exclude_session_id: str | None = None) -> int:
        base = int(settings.ide_base_host_port)
        span = max(1, int(settings.ide_host_port_range))
        end = base + span
        async with get_db_session() as db:
            stmt = select(IdeSessionRecord.host_port).where(IdeSessionRecord.host_port.is_not(None))
            if exclude_session_id:
                stmt = stmt.where(IdeSessionRecord.session_id != exclude_session_id)
            result = await db.execute(stmt)
            used_ports = {int(port) for port in result.scalars().all() if port}

        candidates = list(range(base, end))
        random.shuffle(candidates)
        for port in candidates:
            if port in used_ports:
                continue
            if self.host_port_available(port):
                return port
        raise IdeError(f"No available IDE host port in range {base}-{end - 1}")

    @staticmethod
    def host_port_available(port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", int(port)))
            except OSError:
                return False
        return True

    async def update_record(self, session_id: str, **values: Any) -> None:
        clears_idle_pending = self.clears_idle_pending_to_running(values)
        user_activity_at = values.get("last_user_activity_at")
        values["updated_at"] = datetime.now()
        conditions = [IdeSessionRecord.session_id == session_id]
        if clears_idle_pending:
            if isinstance(user_activity_at, datetime):
                conditions.append(
                    (IdeSessionRecord.status != "IDLE_PENDING")
                    | IdeSessionRecord.idle_pending_at.is_(None)
                    | (literal(user_activity_at) > IdeSessionRecord.idle_pending_at)
                )
            else:
                conditions.append(
                    (IdeSessionRecord.status != "IDLE_PENDING") | IdeSessionRecord.idle_pending_at.is_(None)
                )
        async with get_db_session() as db:
            await db.execute(
                update(IdeSessionRecord)
                .where(*conditions)
                .values(**values),
            )
            await db.commit()

    async def mark_idle_pending(
        self,
        session_id: str,
        now: datetime,
        *,
        busy_reason: str = "user_idle_observing",
        last_busy_at: datetime | None = None,
    ) -> None:
        values: dict[str, Any] = {
            "status": "IDLE_PENDING",
            "idle_pending_at": func.coalesce(IdeSessionRecord.idle_pending_at, now),
            "busy_reason": busy_reason,
            "updated_at": datetime.now(),
        }
        if last_busy_at is not None:
            values["last_busy_at"] = last_busy_at
        async with get_db_session() as db:
            await db.execute(
                update(IdeSessionRecord)
                .where(IdeSessionRecord.session_id == session_id)
                .values(**values),
            )
            await db.commit()

    async def touch(self, session_id: str) -> None:
        await self.update_record(session_id, last_seen_at=datetime.now())

    async def increment_ws(self, session_id: str, delta: int) -> None:
        now = datetime.now()
        next_count = IdeSessionRecord.active_ws_count + delta
        values: dict[str, Any] = {
            "active_ws_count": case((next_count < 0, 0), else_=next_count),
            "last_seen_at": now,
            "updated_at": now,
        }
        async with get_db_session() as db:
            await db.execute(
                update(IdeSessionRecord)
                .where(IdeSessionRecord.session_id == session_id)
                .values(**values),
            )
            await db.commit()

    async def _reclaimer_loop(self) -> None:
        while True:
            await asyncio.sleep(60)
            try:
                await self.run_reclaimer_cycle()
            except Exception as exc:
                logger.exception("IDE idle reclaimer failed: %s", exc)
                continue

    async def run_reclaimer_cycle(self) -> None:
        """Run one cleanup cycle under a cross-process MySQL advisory lock."""
        async with get_db_session() as lock_db:
            acquired = await lock_db.scalar(
                text("SELECT GET_LOCK('agent_template_ide_reclaimer', 0)")
            )
            if acquired != 1:
                return
            try:
                await self.reclaim_idle_sessions()
                await self.remove_inactive_stopped_containers()
            finally:
                await lock_db.execute(
                    text("SELECT RELEASE_LOCK('agent_template_ide_reclaimer')")
                )

    async def reclaim_idle_sessions(self) -> None:
        now = datetime.now()
        cutoff = now - timedelta(minutes=settings.ide_idle_stop_minutes)
        async with get_db_session() as db:
            result = await db.execute(
                select(IdeSessionRecord).where(IdeSessionRecord.status.in_(["RUNNING", "IDLE_PENDING", "STOPPING"])),
            )
            records = list(result.scalars().all())
        for record in records:
            if not self.owns_session_record(record):
                continue
            if record.status == "STOPPING":
                stopping_cutoff = now - timedelta(minutes=settings.ide_stopping_timeout_minutes)
                if record.updated_at and record.updated_at > stopping_cutoff:
                    continue
                await self.mark_idle_pending(
                    record.session_id,
                    now,
                    busy_reason="stopping_retry",
                )
                continue
            last_user_activity = self.last_user_activity_anchor(record)
            if record.status == "IDLE_PENDING" and self.has_user_activity_after_idle_pending(record):
                await self.update_record(
                    record.session_id,
                    status="RUNNING",
                    last_user_activity_at=record.last_user_activity_at,
                    idle_pending_at=None,
                    busy_reason=None,
                )
                continue
            if record.status != "IDLE_PENDING" and last_user_activity > cutoff:
                continue
            busy_reason = await asyncio.to_thread(self.busy_reason, record)
            if busy_reason:
                if self.preserves_idle_pending_for_busy_reason(busy_reason):
                    await self.mark_idle_pending(
                        record.session_id,
                        now,
                        busy_reason=busy_reason,
                        last_busy_at=now,
                    )
                    continue
                await self.update_record(
                    record.session_id,
                    status="RUNNING",
                    busy_reason=busy_reason,
                    last_busy_at=now,
                    idle_pending_at=None,
                )
                continue
            if record.status != "IDLE_PENDING":
                await self.mark_idle_pending(
                    record.session_id,
                    now,
                    busy_reason="user_idle_observing",
                )
                continue
            if record.idle_pending_at is None:
                await self.mark_idle_pending(
                    record.session_id,
                    now,
                    busy_reason=record.busy_reason or "user_idle_observing",
                )
                continue
            pending_started_at = record.idle_pending_at
            pending_cutoff = now - timedelta(minutes=settings.ide_idle_pending_minutes)
            if pending_started_at > pending_cutoff:
                continue
            if not await self.claim_idle_session_stop(record.session_id, cutoff, pending_cutoff):
                continue
            claimed_record = await self.require_session(record.session_id)
            final_busy_reason = await asyncio.to_thread(self.reclaim_blocking_busy_reason, claimed_record)
            if final_busy_reason:
                await self.update_record(
                    record.session_id,
                    status="RUNNING",
                    busy_reason=final_busy_reason,
                    last_busy_at=datetime.now(),
                    idle_pending_at=None,
                )
                continue
            try:
                await self.stop_session_record(claimed_record, stopped_by="system-reclaimer")
            except Exception as exc:
                await self.update_record(record.session_id, status="FAILED", error_message=str(exc))
                logger.exception("Failed to stop idle IDE session %s: %s", record.session_id, exc)

    async def remove_inactive_stopped_containers(self) -> None:
        if settings.ide_stopped_container_rm_minutes < 0:
            return
        now = datetime.now()
        cutoff = now - timedelta(minutes=settings.ide_stopped_container_rm_minutes)
        async with get_db_session() as db:
            result = await db.execute(
                select(IdeSessionRecord).where(IdeSessionRecord.status.in_(["STOPPED", "FAILED"])),
            )
            records = list(result.scalars().all())
        for record in records:
            if not self.owns_session_record(record):
                continue
            inactive_at = record.stopped_at or record.updated_at or record.last_seen_at or record.created_at
            if inactive_at and inactive_at > cutoff:
                continue
            if not await asyncio.to_thread(self.container_exists, record.container_name):
                if record.container_id:
                    await self.update_record(record.session_id, container_id=None)
                continue
            if await asyncio.to_thread(self.container_running, record.container_name):
                continue
            try:
                removed = await asyncio.to_thread(self.remove_container, record.container_name)
            except Exception as exc:
                await self.update_record(record.session_id, error_message=str(exc))
                logger.exception("Failed to remove inactive IDE container %s: %s", record.session_id, exc)
                continue
            if removed:
                await self.update_record(
                    record.session_id,
                    container_id=None,
                    error_message=None,
                    updated_at=now,
                )

    async def refresh_busy_observation(self, record: IdeSessionRecord, now: datetime) -> IdeSessionRecord:
        if record.status not in {"RUNNING", "IDLE_PENDING"}:
            return record
        busy_reason = await asyncio.to_thread(self.filesystem_busy_reason, record)
        if not busy_reason:
            return record
        await self.update_record(
            record.session_id,
            status="RUNNING",
            busy_reason=busy_reason,
            last_busy_at=now,
            idle_pending_at=None,
        )
        record.status = "RUNNING"
        record.busy_reason = busy_reason
        record.last_busy_at = now
        record.idle_pending_at = None
        return record

    async def claim_idle_session_stop(
        self,
        session_id: str,
        activity_cutoff: datetime,
        pending_cutoff: datetime,
    ) -> bool:
        fresh = await self.require_session(session_id)
        if not self.owns_session_record(fresh):
            return False
        if fresh.status != "IDLE_PENDING":
            return False
        last_user_activity = self.last_user_activity_anchor(fresh)
        if last_user_activity > activity_cutoff and (
            fresh.status != "IDLE_PENDING" or self.has_user_activity_after_idle_pending(fresh)
        ):
            return False
        if fresh.idle_pending_at is None:
            await self.mark_idle_pending(
                session_id,
                datetime.now(),
                busy_reason=fresh.busy_reason or "user_idle_observing",
            )
            return False
        if fresh.idle_pending_at > pending_cutoff:
            return False
        if await asyncio.to_thread(self.reclaim_blocking_busy_reason, fresh):
            return False
        now = datetime.now()
        async with get_db_session() as db:
            result = await db.execute(
                update(IdeSessionRecord)
                .where(
                    IdeSessionRecord.session_id == session_id,
                    IdeSessionRecord.status == "IDLE_PENDING",
                )
                .values(
                    status="STOPPING",
                    busy_reason="reclaimer_stopping",
                    updated_at=now,
                ),
            )
            await db.commit()
        return result.rowcount == 1

    def busy_reason(self, record: IdeSessionRecord) -> str | None:
        if not self.container_running(record.container_name):
            return None
        cpu = self.container_cpu_percent(record.container_name)
        if cpu is not None and cpu >= settings.ide_busy_cpu_threshold:
            return "cpu_active"
        return self.filesystem_busy_reason(record)

    def reclaim_blocking_busy_reason(self, record: IdeSessionRecord) -> str | None:
        return self.filesystem_busy_reason(record)

    def filesystem_busy_reason(self, record: IdeSessionRecord) -> str | None:
        claude_root = self.claude_dir_for_record(record)
        busy_window = datetime.now() - timedelta(minutes=settings.ide_busy_file_window_minutes)
        latest_claude_write = self.latest_write_time([claude_root])
        if latest_claude_write and latest_claude_write > busy_window:
            return "recent_claude_write"
        if record.workspace_writable:
            latest_workspace_write = self.latest_write_time([Path(record.workspace_dir)])
            if latest_workspace_write and latest_workspace_write > busy_window:
                return "recent_workspace_write"
        claude_state = self.claude_session_state(claude_root)
        if claude_state:
            return claude_state
        return None

    def container_cpu_percent(self, name: str) -> float | None:
        result = self.docker(["stats", "--no-stream", "--format", "{{.CPUPerc}}", name], check=False)
        if result.returncode != 0:
            return None
        value = result.stdout.strip().replace("%", "")
        try:
            return float(value)
        except ValueError:
            return None

    def latest_write_time(self, roots: list[Path], limit: int = 20000) -> datetime | None:
        newest: float | None = None
        seen = 0
        for root in roots:
            if not root.exists():
                continue
            try:
                root_mtime = root.stat().st_mtime
                newest = max(newest or root_mtime, root_mtime)
            except OSError:
                pass
            for current, dirs, files in os.walk(root):
                for name in [*dirs, *files]:
                    try:
                        mtime = (Path(current) / name).stat().st_mtime
                    except OSError:
                        continue
                    newest = max(newest or mtime, mtime)
                    seen += 1
                    if seen >= limit:
                        break
                if seen >= limit:
                    break
        return datetime.fromtimestamp(newest) if newest else None

    def claude_session_state(self, claude_root: Path) -> str | None:
        projects_root = claude_root / "projects"
        if not projects_root.exists():
            return None
        candidates: list[tuple[float, Path]] = []
        for current, _dirs, files in os.walk(projects_root):
            for name in files:
                if not name.endswith(".jsonl"):
                    continue
                path = Path(current) / name
                try:
                    mtime = path.stat().st_mtime
                except OSError:
                    continue
                candidates.append((mtime, path))
        max_busy_cutoff = datetime.now() - timedelta(hours=settings.ide_busy_max_hours)
        for mtime, path in sorted(candidates, reverse=True)[:3]:
            last_event = self.last_jsonl_event(path)
            if last_event is None or self.is_claude_end_turn(last_event):
                continue
            if datetime.fromtimestamp(mtime) < max_busy_cutoff:
                continue
            if last_event.get("type") == "queue-operation":
                operation = str(last_event.get("operation") or "")
                if operation == "enqueue":
                    return "claude_queue_active"
            message = last_event.get("message")
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "tool_use":
                            return "claude_tool_pending"
            return "claude_running"
        return None

    @staticmethod
    def last_jsonl_event(path: Path, max_lines: int = 200) -> dict[str, Any] | None:
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            return None
        for line in reversed(lines[-max_lines:]):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                return event
        return None

    @staticmethod
    def is_claude_end_turn(event: dict[str, Any]) -> bool:
        if event.get("type") != "assistant":
            return False
        message = event.get("message")
        return isinstance(message, dict) and message.get("stop_reason") == "end_turn"

    def normalize_activity_time(
        self,
        value: Any,
        record: IdeSessionRecord,
        now: datetime,
    ) -> datetime | None:
        if value in (None, ""):
            return None
        parsed: datetime | None = None
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, (int, float)):
            seconds = float(value)
            if seconds > 10_000_000_000:
                seconds /= 1000
            parsed = datetime.fromtimestamp(seconds)
        else:
            raw = str(value).strip()
            if raw:
                try:
                    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                except ValueError:
                    return None
        if parsed is None:
            return None
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone().replace(tzinfo=None)
        earliest = record.started_at or record.created_at
        if earliest and parsed < earliest:
            parsed = earliest
        latest = now + timedelta(seconds=30)
        if parsed > latest:
            parsed = now
        return parsed

    def record_payload(self, record: IdeSessionRecord) -> dict[str, Any]:
        return {
            "session_id": record.session_id,
            "user_id": record.user_id,
            "project_id": record.project_id,
            "project_owner_user_id": record.project_owner_user_id,
            "system_id": record.system_id,
            "compose_project": record.compose_project,
            "container_name": record.container_name,
            "host_port": record.host_port,
            "status": record.status,
            "workspace_dir": record.workspace_dir,
            "runtime_dir": record.runtime_dir,
            "workspace_writable": record.workspace_writable,
            "active_ws_count": record.active_ws_count,
            "last_seen_at": self.iso(record.last_seen_at),
            "last_heartbeat_at": self.iso(record.last_heartbeat_at),
            "last_user_activity_at": self.iso(record.last_user_activity_at),
            "idle_pending_at": self.iso(record.idle_pending_at),
            "last_busy_at": self.iso(record.last_busy_at),
            "busy_reason": record.busy_reason,
            "stopped_by": record.stopped_by,
            "error_message": record.error_message,
            "created_at": self.iso(record.created_at),
            "started_at": self.iso(record.started_at),
            "stopped_at": self.iso(record.stopped_at),
        }

    @staticmethod
    def normalize_id(raw: str) -> str:
        value = (raw or "default").strip() or "default"
        return "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "-" for ch in value)[:120]

    @staticmethod
    def normalize_container_name(raw: str) -> str:
        value = re.sub(r"[^a-zA-Z0-9_.-]+", "-", raw).strip("-")
        return value[:180] or "ide-code-server-default"

    @staticmethod
    def normalize_compose_project(raw: str) -> str:
        value = re.sub(r"[^a-z0-9_-]+", "-", raw.lower()).strip("-_")
        if not value or not value[0].isalnum():
            value = f"ide-{value}"
        return value[:120]

    @staticmethod
    def iso(value: datetime | None) -> str | None:
        return value.isoformat(sep=" ", timespec="seconds") if value else None

    def docker(
        self,
        args: list[str],
        check: bool = True,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["docker", *args],
            check=check,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )

    def run_docker(self, args: list[str], timeout: int | None = None) -> subprocess.CompletedProcess[str]:
        try:
            return self.docker(args, check=True, timeout=timeout)
        except subprocess.CalledProcessError as exc:
            message = (exc.stderr or exc.stdout or str(exc)).strip()
            raise IdeError(message) from exc
        except subprocess.TimeoutExpired as exc:
            raise IdeError(f"Docker command timed out after {exc.timeout} seconds: docker {' '.join(args)}") from exc

ide_service = IdeService()
