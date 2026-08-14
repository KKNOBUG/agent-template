-- IDE sessions and permission switches for code-server integration.

CREATE TABLE IF NOT EXISTS ide_projects (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    project_id VARCHAR(120) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    owner_user_id VARCHAR(120) NOT NULL,
    system_id VARCHAR(120) NOT NULL DEFAULT 'default',
    description VARCHAR(500) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_ide_projects_owner (owner_user_id),
    KEY idx_ide_projects_system (system_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS ide_sessions (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    session_id VARCHAR(160) NOT NULL UNIQUE,
    user_id VARCHAR(120) NOT NULL,
    project_id VARCHAR(120) NOT NULL,
    project_owner_user_id VARCHAR(120) NOT NULL,
    system_id VARCHAR(120) NOT NULL DEFAULT 'default',
    compose_project VARCHAR(160) NOT NULL,
    container_name VARCHAR(180) NOT NULL,
    container_id VARCHAR(180) NULL,
    host_port INT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'CREATING',
    workspace_dir VARCHAR(1024) NOT NULL,
    runtime_dir VARCHAR(1024) NOT NULL,
    workspace_writable TINYINT(1) NOT NULL DEFAULT 1,
    proxy_path VARCHAR(512) NOT NULL,
    active_ws_count INT NOT NULL DEFAULT 0,
    last_seen_at DATETIME NULL,
    last_heartbeat_at DATETIME NULL,
    last_user_activity_at DATETIME NULL,
    idle_pending_at DATETIME NULL,
    last_busy_at DATETIME NULL,
    busy_reason VARCHAR(255) NULL,
    stopped_by VARCHAR(120) NULL,
    error_message TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at DATETIME NULL,
    stopped_at DATETIME NULL,
    expires_at DATETIME NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_ide_user_project (user_id, project_id),
    UNIQUE KEY uq_ide_host_port (host_port),
    KEY idx_ide_status_seen (status, last_seen_at),
    KEY idx_ide_user_activity (status, last_user_activity_at),
    KEY idx_ide_project (project_id),
    KEY idx_ide_system (system_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

SET @ide_workspace_writable_exists := (
    SELECT COUNT(1)
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'ide_sessions'
      AND column_name = 'workspace_writable'
);
SET @ide_workspace_writable_sql := IF(
    @ide_workspace_writable_exists = 0,
    'ALTER TABLE ide_sessions ADD COLUMN workspace_writable TINYINT(1) NOT NULL DEFAULT 1 AFTER runtime_dir',
    'SELECT 1'
);
PREPARE ide_workspace_writable_stmt FROM @ide_workspace_writable_sql;
EXECUTE ide_workspace_writable_stmt;
DEALLOCATE PREPARE ide_workspace_writable_stmt;

UPDATE ide_sessions
SET workspace_writable = 0
WHERE user_id <> project_owner_user_id;

SET @ide_last_user_activity_exists := (
    SELECT COUNT(1)
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'ide_sessions'
      AND column_name = 'last_user_activity_at'
);
SET @ide_last_user_activity_sql := IF(
    @ide_last_user_activity_exists = 0,
    'ALTER TABLE ide_sessions ADD COLUMN last_user_activity_at DATETIME NULL AFTER last_heartbeat_at',
    'SELECT 1'
);
PREPARE ide_last_user_activity_stmt FROM @ide_last_user_activity_sql;
EXECUTE ide_last_user_activity_stmt;
DEALLOCATE PREPARE ide_last_user_activity_stmt;

SET @ide_idle_pending_exists := (
    SELECT COUNT(1)
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'ide_sessions'
      AND column_name = 'idle_pending_at'
);
SET @ide_idle_pending_sql := IF(
    @ide_idle_pending_exists = 0,
    'ALTER TABLE ide_sessions ADD COLUMN idle_pending_at DATETIME NULL AFTER last_user_activity_at',
    'SELECT 1'
);
PREPARE ide_idle_pending_stmt FROM @ide_idle_pending_sql;
EXECUTE ide_idle_pending_stmt;
DEALLOCATE PREPARE ide_idle_pending_stmt;

SET @ide_last_busy_exists := (
    SELECT COUNT(1)
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'ide_sessions'
      AND column_name = 'last_busy_at'
);
SET @ide_last_busy_sql := IF(
    @ide_last_busy_exists = 0,
    'ALTER TABLE ide_sessions ADD COLUMN last_busy_at DATETIME NULL AFTER idle_pending_at',
    'SELECT 1'
);
PREPARE ide_last_busy_stmt FROM @ide_last_busy_sql;
EXECUTE ide_last_busy_stmt;
DEALLOCATE PREPARE ide_last_busy_stmt;

SET @ide_user_activity_index_exists := (
    SELECT COUNT(1)
    FROM information_schema.statistics
    WHERE table_schema = DATABASE()
      AND table_name = 'ide_sessions'
      AND index_name = 'idx_ide_user_activity'
);
SET @ide_user_activity_index_sql := IF(
    @ide_user_activity_index_exists = 0,
    'ALTER TABLE ide_sessions ADD KEY idx_ide_user_activity (status, last_user_activity_at)',
    'SELECT 1'
);
PREPARE ide_user_activity_index_stmt FROM @ide_user_activity_index_sql;
EXECUTE ide_user_activity_index_stmt;
DEALLOCATE PREPARE ide_user_activity_index_stmt;

SET @ide_host_port_index_exists := (
    SELECT COUNT(1)
    FROM information_schema.statistics
    WHERE table_schema = DATABASE()
      AND table_name = 'ide_sessions'
      AND index_name = 'uq_ide_host_port'
);
SET @ide_host_port_index_sql := IF(
    @ide_host_port_index_exists = 0,
    'ALTER TABLE ide_sessions ADD UNIQUE KEY uq_ide_host_port (host_port)',
    'SELECT 1'
);
PREPARE ide_host_port_index_stmt FROM @ide_host_port_index_sql;
EXECUTE ide_host_port_index_stmt;
DEALLOCATE PREPARE ide_host_port_index_stmt;

CREATE TABLE IF NOT EXISTS ide_permission_config (
    id TINYINT PRIMARY KEY,
    allow_view_other_users_projects TINYINT(1) NOT NULL DEFAULT 1,
    allow_cross_user_edit_in_system TINYINT(1) NOT NULL DEFAULT 0,
    updated_by VARCHAR(120) NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO ide_permission_config (
    id,
    allow_view_other_users_projects,
    allow_cross_user_edit_in_system
) VALUES (1, 1, 0)
ON DUPLICATE KEY UPDATE id = id;
