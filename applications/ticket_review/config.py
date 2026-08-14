from __future__ import annotations

from configure import PROJECT_CONFIG


def get_env_int(name: str, default: int) -> int:
    """Compatibility helper for settings previously read directly from .env."""
    if name == "COCO_BATCH_SIZE":
        return PROJECT_CONFIG.TICKET_COCO_BATCH_SIZE
    return default


class TicketReviewSettings:
    app_title = "环境工单预审"
    app_version = "1.0.0"
    model_pool = PROJECT_CONFIG.TICKET_MODEL_POOL.split(";")
    model_timeout = PROJECT_CONFIG.TICKET_MODEL_TIMEOUT
    model_retry_count = PROJECT_CONFIG.TICKET_MODEL_RETRY_COUNT
    model_retry_delay = PROJECT_CONFIG.TICKET_MODEL_RETRY_DELAY
    sdk_model_pool = PROJECT_CONFIG.TICKET_SDK_MODEL_POOL
    anthropic_model = PROJECT_CONFIG.TICKET_ANTHROPIC_MODEL

    db1_host = PROJECT_CONFIG.TICKET_DB1_HOST
    db1_port = PROJECT_CONFIG.TICKET_DB1_PORT
    db1_user = PROJECT_CONFIG.TICKET_DB1_USER
    db1_password = PROJECT_CONFIG.TICKET_DB1_PASSWORD
    db1_name = PROJECT_CONFIG.TICKET_DB1_NAME
    db1_pool_min_size = PROJECT_CONFIG.TICKET_DB1_POOL_MIN_SIZE
    db1_pool_max_size = PROJECT_CONFIG.TICKET_DB1_POOL_MAX_SIZE
    db1_connect_timeout = PROJECT_CONFIG.TICKET_DB1_CONNECT_TIMEOUT

    db2_host = PROJECT_CONFIG.TICKET_DB2_HOST
    db2_port = PROJECT_CONFIG.TICKET_DB2_PORT
    db2_user = PROJECT_CONFIG.TICKET_DB2_USER
    db2_password = PROJECT_CONFIG.TICKET_DB2_PASSWORD
    db2_name = PROJECT_CONFIG.TICKET_DB2_NAME
    db2_pool_min_size = PROJECT_CONFIG.TICKET_DB2_POOL_MIN_SIZE
    db2_pool_max_size = PROJECT_CONFIG.TICKET_DB2_POOL_MAX_SIZE
    db2_connect_timeout = PROJECT_CONFIG.TICKET_DB2_CONNECT_TIMEOUT

    push_task_poll_interval = PROJECT_CONFIG.TICKET_PUSH_TASK_POLL_INTERVAL
    push_task_batch_size = PROJECT_CONFIG.TICKET_PUSH_TASK_BATCH_SIZE
    push_task_retention_days = PROJECT_CONFIG.TICKET_PUSH_TASK_RETENTION_DAYS
    push_task_cleanup_interval = PROJECT_CONFIG.TICKET_PUSH_TASK_CLEANUP_INTERVAL
    push_task_stale_processing_seconds = PROJECT_CONFIG.TICKET_PUSH_TASK_STALE_PROCESSING_SECONDS
    push_task_failed_retry_delay_seconds = PROJECT_CONFIG.TICKET_PUSH_TASK_FAILED_RETRY_DELAY_SECONDS
    push_task_sse_heartbeat_seconds = PROJECT_CONFIG.TICKET_PUSH_TASK_SSE_HEARTBEAT_SECONDS
    push_task_heartbeat_interval_seconds = PROJECT_CONFIG.TICKET_PUSH_TASK_HEARTBEAT_INTERVAL_SECONDS


settings = TicketReviewSettings()
