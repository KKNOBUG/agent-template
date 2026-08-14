from __future__ import annotations

from urllib.parse import quote_plus

from configure import PROJECT_CONFIG


class CodeServerIdeSettings:
    app_title = "Code Server IDE Backend"
    app_version = "0.1.0"
    db_host = PROJECT_CONFIG.IDE_DATABASE_HOST
    db_port = PROJECT_CONFIG.IDE_DATABASE_PORT
    db_user = PROJECT_CONFIG.IDE_DATABASE_USER
    db_password = PROJECT_CONFIG.IDE_DATABASE_PASSWORD
    db_name = PROJECT_CONFIG.IDE_DATABASE_NAME
    db_echo = PROJECT_CONFIG.IDE_DATABASE_ECHO
    ide_image = PROJECT_CONFIG.IDE_IMAGE
    ide_docker_network = PROJECT_CONFIG.IDE_DOCKER_NETWORK
    ide_container_prefix = PROJECT_CONFIG.IDE_CONTAINER_PREFIX
    ide_sessions_root = PROJECT_CONFIG.IDE_SESSIONS_ROOT
    ide_code_server_auth = PROJECT_CONFIG.IDE_CODE_SERVER_AUTH.strip().lower() or "none"
    ide_uid = PROJECT_CONFIG.IDE_UID
    ide_base_host_port = PROJECT_CONFIG.IDE_BASE_HOST_PORT
    ide_host_port_range = PROJECT_CONFIG.IDE_HOST_PORT_RANGE
    ide_memory_limit = PROJECT_CONFIG.IDE_MEMORY_LIMIT
    ide_memory_swap_limit = PROJECT_CONFIG.IDE_MEMORY_SWAP_LIMIT
    ide_cpu_limit = PROJECT_CONFIG.IDE_CPU_LIMIT
    ide_pids_limit = PROJECT_CONFIG.IDE_PIDS_LIMIT
    coco_npm_registry = PROJECT_CONFIG.COCO_NPM_REGISTRY
    coco_pip_index_url = PROJECT_CONFIG.COCO_PIP_INDEX_URL
    coco_pip_trusted_host = PROJECT_CONFIG.COCO_PIP_TRUSTED_HOST
    ide_max_running_containers = PROJECT_CONFIG.IDE_MAX_RUNNING_CONTAINERS
    ide_idle_stop_minutes = PROJECT_CONFIG.IDE_IDLE_STOP_MINUTES
    ide_idle_pending_minutes = PROJECT_CONFIG.IDE_IDLE_PENDING_MINUTES
    ide_stopping_timeout_minutes = PROJECT_CONFIG.IDE_STOPPING_TIMEOUT_MINUTES
    ide_docker_stop_timeout_seconds = PROJECT_CONFIG.IDE_DOCKER_STOP_TIMEOUT_SECONDS
    ide_stopped_container_rm_minutes = PROJECT_CONFIG.IDE_STOPPED_CONTAINER_RM_MINUTES
    ide_busy_file_window_minutes = PROJECT_CONFIG.IDE_BUSY_FILE_WINDOW_MINUTES
    ide_busy_cpu_threshold = PROJECT_CONFIG.IDE_BUSY_CPU_THRESHOLD
    ide_busy_max_hours = PROJECT_CONFIG.IDE_BUSY_MAX_HOURS
    ide_data_retention_days = PROJECT_CONFIG.IDE_DATA_RETENTION_DAYS
    ide_super_admin_users = PROJECT_CONFIG.IDE_SUPER_ADMIN_USERS
    ide_trust_user_headers = PROJECT_CONFIG.IDE_TRUST_USER_HEADERS
    ide_trusted_auth_proxies = PROJECT_CONFIG.IDE_TRUSTED_AUTH_PROXIES
    ide_allow_ip_identity = PROJECT_CONFIG.IDE_ALLOW_IP_IDENTITY
    allow_view_other_users_projects = PROJECT_CONFIG.IDE_ALLOW_VIEW_OTHER_USERS_PROJECTS
    allow_cross_user_edit_in_system = PROJECT_CONFIG.IDE_ALLOW_CROSS_USER_EDIT_IN_SYSTEM

    def __init__(self) -> None:
        if self.ide_code_server_auth != "none":
            raise ValueError("Only IDE_CODE_SERVER_AUTH=none is supported")

    @property
    def database_url(self) -> str:
        user = quote_plus(self.db_user)
        password = quote_plus(self.db_password)
        return (
            f"mysql+aiomysql://{user}:{password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )


settings = CodeServerIdeSettings()
