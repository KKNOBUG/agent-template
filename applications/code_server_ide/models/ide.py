from __future__ import annotations

from datetime import datetime

from sqlmodel import Field

from applications.code_server_ide.models.base import AsyncSQLModelRecord


class IdeSessionRecord(AsyncSQLModelRecord, table=True):
    __tablename__ = "ide_sessions"

    id: int | None = Field(default=None, primary_key=True)
    session_id: str = Field(index=True, max_length=160)
    user_id: str = Field(max_length=120)
    project_id: str = Field(max_length=120)
    project_owner_user_id: str = Field(max_length=120)
    system_id: str = Field(default="default", max_length=120)
    compose_project: str = Field(max_length=160)
    container_name: str = Field(max_length=180)
    container_id: str | None = Field(default=None, max_length=180)
    host_port: int | None = None
    status: str = Field(default="CREATING", max_length=32)
    workspace_dir: str = Field(max_length=1024)
    runtime_dir: str = Field(max_length=1024)
    workspace_writable: bool = True
    proxy_path: str = Field(max_length=512)
    active_ws_count: int = 0
    last_seen_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    last_user_activity_at: datetime | None = None
    idle_pending_at: datetime | None = None
    last_busy_at: datetime | None = None
    busy_reason: str | None = Field(default=None, max_length=255)
    stopped_by: str | None = Field(default=None, max_length=120)
    error_message: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    expires_at: datetime | None = None
    updated_at: datetime = Field(default_factory=datetime.now)


class IdeProjectRecord(AsyncSQLModelRecord, table=True):
    __tablename__ = "ide_projects"

    id: int | None = Field(default=None, primary_key=True)
    project_id: str = Field(index=True, max_length=120)
    name: str = Field(max_length=200)
    owner_user_id: str = Field(max_length=120)
    system_id: str = Field(default="default", max_length=120)
    description: str | None = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class IdePermissionConfig(AsyncSQLModelRecord, table=True):
    __tablename__ = "ide_permission_config"

    id: int = Field(default=1, primary_key=True)
    allow_view_other_users_projects: bool = True
    allow_cross_user_edit_in_system: bool = False
    updated_by: str | None = Field(default=None, max_length=120)
    updated_at: datetime = Field(default_factory=datetime.now)
