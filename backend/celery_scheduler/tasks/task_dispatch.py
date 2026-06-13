# -*- coding: utf-8 -*-
"""
@Project : KeenRobot
@Module  : task_dispatch
"""
from __future__ import annotations

import traceback
from typing import Any, Dict, Optional

from backend.celery_scheduler.celery_base import (
    check_task_expired,
    get_scheduled_tasks,
    run_async,
)
from backend.celery_scheduler.celery_worker import celery
from backend.configure import LOGGER


def dispatch_task_center_task(task: Any, override_kwargs: Optional[Dict[str, Any]] = None) -> None:
    """
    按 TaskCenterInfo.task_celery 下发 Celery 任务。
    celery_node 与 task_celery 对齐，不再经 run_scheduled_task 中转。
    """
    task_celery = (getattr(task, "task_celery", None) or "").strip()
    if not task_celery:
        raise ValueError(f"任务ID={getattr(task, 'id', None)} 未配置 task_celery")

    task_kwargs = {**(getattr(task, "task_kwargs", None) or {}), **(override_kwargs or {})}
    celery.send_task(
        task_celery,
        kwargs=task_kwargs,
        __task_id=task.id,
    )


async def _scan_and_dispatch_impl() -> Dict[str, Any]:
    tasks = await get_scheduled_tasks(task_type="example")
    scanned: int = len(tasks)
    dispatched: int = 0
    for task in tasks:
        try:
            if await check_task_expired(task):
                dispatch_task_center_task(task)
                dispatched += 1
        except Exception as e:
            task_id = getattr(task, "id", None)
            LOGGER.error(
                f"【Worker】函数scan_and_dispatch_tasks执行异常: \n"
                f"任务ID: {task_id}\n"
                f"错误类型: {type(e).__name__}\n"
                f"错误描述: {e}\n"
                f"错误回溯: {traceback.format_exc()}\n"
            )
    skipped: int = scanned - dispatched
    if dispatched and skipped:
        desc: str = "已发现可调度任务, 但部分任务未到期，仅提交到期任务"
    elif dispatched > 0:
        desc: str = "已发现可调度任务, 全部提交"
    elif skipped > 0:
        desc: str = "未发现可调度任务, 全部跳过"
    else:
        desc: str = "暂未发现启用并可调度的任务, 等待下次扫描"
    return {
        "scanned": scanned,
        "dispatched": dispatched,
        "skipped": skipped,
        "desc": desc
    }


@celery.task(name="backend.celery_scheduler.tasks.task_dispatch.scan_and_dispatch_tasks")
def scan_and_dispatch_tasks():
    """定时扫描：读取启用且配置了调度的 example 任务，到期则按 task_celery 下发。"""
    return run_async(_scan_and_dispatch_impl())
