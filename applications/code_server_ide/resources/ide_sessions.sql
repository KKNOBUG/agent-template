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

-- =============================================
-- 新增业务表开始
-- =============================================

CREATE TABLE IF NOT EXISTS `push_tasks` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `request_id` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `message_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `push_time` datetime(6) NOT NULL,
  `status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'PENDING',
  `total_records` int(10) unsigned NOT NULL DEFAULT '0',
  `processed_records` int(10) unsigned NOT NULL DEFAULT '0',
  `raw_payload` json NOT NULL,
  `result_json` json NOT NULL,
  `error_message` text COLLATE utf8mb4_unicode_ci,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `started_at` datetime(6) DEFAULT NULL,
  `finished_at` datetime(6) DEFAULT NULL,
  `heartbeat_at` datetime(6) DEFAULT NULL COMMENT '任务处理心跳时间',
  `lease_token` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '当前任务领取令牌',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_push_tasks_request_id` (`request_id`),
  UNIQUE KEY `uk_push_tasks_message_id` (`message_id`),
  KEY `idx_push_tasks_status_created` (`status`,`created_at`,`id`),
  KEY `idx_push_tasks_created_at` (`created_at`),
  KEY `idx_status_heartbeat` (`status`,`heartbeat_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `review_results` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '预审结果ID',
  `table_name` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '环境工单预审结果' COMMENT '表格名称',
  `source_file` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '原始Excel文件名',
  `source_file_data` longblob COMMENT '原始Excel文件二进制内容',
  `row_count` int(11) NOT NULL DEFAULT '0' COMMENT '已经处理并保存的工单行数',
  `result_json` json NOT NULL COMMENT '预审结果、原始行数据及元数据',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `ix_review_results_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='环境工单预审结果及历史记录';

CREATE TABLE IF NOT EXISTS `fw039_review_results` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT COMMENT '结果表主键',
  `request_id` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `message_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '上游推送messageId',
  `row_number` int(10) unsigned NOT NULL COMMENT '当前推送任务内的全局行号',
  `ticket_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '原始记录id',
  `instance_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '流程实例instance_id',
  `ticket_no` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '工单编号，通常来源于extra1',
  `ticket_type` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '工单类型，例如服务请求类',
  `ticket_center` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '所属中心：上海、苏州或无法判断',
  `title` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '工单标题',
  `work_type` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '业务类型，FW039通常为服务请求',
  `app_system` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '应用系统',
  `matched_keyword` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '命中的分类关键词',
  `primary_category` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '一级分类',
  `secondary_category` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '二级分类',
  `screening_condition` text COLLATE utf8mb4_unicode_ci COMMENT '命中的初筛判定条件',
  `required_fields` json NOT NULL COMMENT '分类规则要求的必填字段数组',
  `missing_fields` json NOT NULL COMMENT '缺失字段数组',
  `information_complete` tinyint(1) NOT NULL DEFAULT '0' COMMENT '信息是否完整：1完整，0不完整',
  `operation_party` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '操作方',
  `assignee` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '指派人员或处理组',
  `review_result` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '预审结果：通过、退回申请人、人工处理',
  `reason` text COLLATE utf8mb4_unicode_ci COMMENT '预审原因',
  `source_sheet` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '来源，例如FW039-服务请求',
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间',
  `updated_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_fw039_request_row` (`request_id`,`row_number`),
  KEY `idx_fw039_message_id` (`message_id`),
  KEY `idx_fw039_ticket_id` (`ticket_id`),
  KEY `idx_fw039_ticket_no` (`ticket_no`),
  KEY `idx_fw039_instance_id` (`instance_id`),
  KEY `idx_fw039_review_result` (`review_result`),
  KEY `idx_fw039_assignee` (`assignee`),
  KEY `idx_fw039_created_at` (`created_at`),
  CONSTRAINT `fk_fw039_push_task` FOREIGN KEY (`request_id`) REFERENCES `push_tasks` (`request_id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='FW039服务请求预审结果';

CREATE TABLE IF NOT EXISTS `fw038_review_results` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT COMMENT '结果表主键',
  `request_id` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `message_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '上游推送messageId',
  `row_number` int(10) unsigned NOT NULL COMMENT '当前推送任务内的全局行号',
  `ticket_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '原始记录id',
  `instance_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '流程实例instance_id',
  `ticket_no` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '工单编号，通常来源于extra1',
  `ticket_type` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '工单类型，例如故障类',
  `ticket_center` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '所属中心：上海、苏州或无法判断',
  `title` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '工单标题',
  `work_type` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '业务类型，FW038通常为故障上报',
  `app_system` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '应用系统',
  `matched_keyword` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '命中的分类关键词',
  `primary_category` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '一级分类',
  `secondary_category` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '二级分类',
  `screening_condition` text COLLATE utf8mb4_unicode_ci COMMENT '命中的初筛判定条件',
  `required_fields` json NOT NULL COMMENT '分类规则要求的必填字段数组',
  `missing_fields` json NOT NULL COMMENT '缺失字段数组',
  `information_complete` tinyint(1) NOT NULL DEFAULT '0' COMMENT '信息是否完整：1完整，0不完整',
  `operation_party` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '操作方',
  `assignee` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '指派人员或处理组',
  `review_result` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '预审结果：通过、退回申请人、人工处理',
  `reason` text COLLATE utf8mb4_unicode_ci COMMENT '预审原因',
  `source_sheet` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '' COMMENT '来源，例如FW038-故障上报',
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间',
  `updated_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_fw038_request_row` (`request_id`,`row_number`),
  KEY `idx_fw038_message_id` (`message_id`),
  KEY `idx_fw038_ticket_id` (`ticket_id`),
  KEY `idx_fw038_ticket_no` (`ticket_no`),
  KEY `idx_fw038_instance_id` (`instance_id`),
  KEY `idx_fw038_review_result` (`review_result`),
  KEY `idx_fw038_assignee` (`assignee`),
  KEY `idx_fw038_created_at` (`created_at`),
  CONSTRAINT `fk_fw038_push_task` FOREIGN KEY (`request_id`) REFERENCES `push_tasks` (`request_id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='FW038故障上报预审结果';

CREATE TABLE IF NOT EXISTS `department` (
  `department_id` int(11) NOT NULL AUTO_INCREMENT COMMENT '部门主键',
  `department_name` varchar(50) NOT NULL COMMENT '部门名称',
  `parent_id` int(11) DEFAULT NULL COMMENT '父节点',
  `is_leaf_node` enum('0','1') NOT NULL DEFAULT '1' COMMENT '是否为叶子节点(0-否;1-是)',
  `is_show` enum('0','1') NOT NULL DEFAULT '0' COMMENT '是否展示在业务组中(0-否;1-是)',
  `adpm_id` decimal(20,0) NOT NULL DEFAULT '0' COMMENT '对应sys_org_bank表中的org_id',
  `org_code` varchar(50) DEFAULT NULL COMMENT '机构编码',
  `org_short_name` varchar(20) DEFAULT NULL COMMENT '机构简称',
  `org_email` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_german2_ci DEFAULT NULL COMMENT '机构简称',
  `org_remark` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_german2_ci DEFAULT NULL COMMENT '机构备注',
  `org_level` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_german2_ci DEFAULT NULL COMMENT '机构备注',
  `last_update_time` datetime(6) DEFAULT NULL COMMENT '维护时间',
  `last_update_user` varchar(20) DEFAULT NULL COMMENT '维护人',
  `create_time` datetime(6) DEFAULT NULL COMMENT '创建时间',
  `create_user` varchar(20) DEFAULT NULL COMMENT '创建人',
  `org_state` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_german2_ci DEFAULT NULL COMMENT '机构状态',
  PRIMARY KEY (`department_id`),
  UNIQUE KEY `uk_department_id` (`department_id`) USING BTREE,
  KEY `department_test_platform_id_IDX` (`adpm_id`) USING BTREE,
  KEY `department_department_name_IDX` (`department_name`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;