from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS `keenrobot_audit` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    `created_user` VARCHAR(16)   COMMENT '创建人员',
    `updated_user` VARCHAR(16)   COMMENT '更新人员',
    `created_time` DATETIME(6) NOT NULL  COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(6),
    `updated_time` DATETIME(6) NOT NULL  COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `user_id` BIGINT NOT NULL  COMMENT '用户ID',
    `username` VARCHAR(32) NOT NULL  COMMENT '用户名称',
    `request_time` DATETIME(6) NOT NULL  COMMENT '请求时间',
    `request_tags` VARCHAR(255)   COMMENT '请求模块' DEFAULT '',
    `request_summary` VARCHAR(255)   COMMENT '请求接口' DEFAULT '',
    `request_method` VARCHAR(7) NOT NULL  COMMENT '请求方式',
    `request_router` VARCHAR(255) NOT NULL  COMMENT '请求路由',
    `request_client` VARCHAR(16)   COMMENT '请求来源' DEFAULT '',
    `request_header` JSON   COMMENT '请求头部',
    `request_params` LONGTEXT   COMMENT '请求参数',
    `response_time` DATETIME(6) NOT NULL  COMMENT '响应时间',
    `response_header` JSON   COMMENT '响应头部',
    `response_code` VARCHAR(16)   COMMENT '响应代码' DEFAULT '',
    `response_message` VARCHAR(512)   COMMENT '响应消息' DEFAULT '',
    `response_params` LONGTEXT   COMMENT '响应参数',
    `response_elapsed` VARCHAR(16) NOT NULL  COMMENT '响应耗时',
    KEY `idx_keenrobot_a_user_id_e9a9dc` (`user_id`),
    KEY `idx_keenrobot_a_usernam_000393` (`username`),
    KEY `idx_keenrobot_a_request_490048` (`request_time`),
    KEY `idx_keenrobot_a_request_87e1d4` (`request_tags`),
    KEY `idx_keenrobot_a_request_63147a` (`request_summary`),
    KEY `idx_keenrobot_a_request_a8c79b` (`request_method`),
    KEY `idx_keenrobot_a_request_f2eab5` (`request_router`),
    KEY `idx_keenrobot_a_respons_f7510c` (`response_time`),
    KEY `idx_keenrobot_a_respons_79f8ce` (`response_code`)
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `keenrobot_example_category` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    `state` SMALLINT NOT NULL  COMMENT '状态(0:启用, 1:禁用)' DEFAULT 0,
    `created_time` DATETIME(6) NOT NULL  COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(6),
    `updated_time` DATETIME(6) NOT NULL  COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `created_user` VARCHAR(16)   COMMENT '创建人员',
    `updated_user` VARCHAR(16)   COMMENT '更新人员',
    `name` VARCHAR(64) NOT NULL  COMMENT '分类名称',
    `code` VARCHAR(32) NOT NULL UNIQUE COMMENT '分类编码',
    `description` LONGTEXT   COMMENT '分类描述',
    `sort_order` INT NOT NULL  COMMENT '排序序号' DEFAULT 0,
    `parent_id` BIGINT   COMMENT '父分类ID',
    KEY `idx_keenrobot_e_state_31cda1` (`state`)
) CHARACTER SET utf8mb4 COMMENT='商品分类模型';
CREATE TABLE IF NOT EXISTS `keenrobot_example_product` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    `state` SMALLINT NOT NULL  COMMENT '状态(0:启用, 1:禁用)' DEFAULT 0,
    `created_time` DATETIME(6) NOT NULL  COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(6),
    `updated_time` DATETIME(6) NOT NULL  COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `created_user` VARCHAR(16)   COMMENT '创建人员',
    `updated_user` VARCHAR(16)   COMMENT '更新人员',
    `uid` CHAR(36)  UNIQUE COMMENT '唯一标识符',
    `name` VARCHAR(128) NOT NULL  COMMENT '商品名称',
    `code` VARCHAR(32) NOT NULL UNIQUE COMMENT '商品编码',
    `description` LONGTEXT   COMMENT '商品描述',
    `price` DECIMAL(10,2) NOT NULL  COMMENT '商品价格',
    `stock` INT NOT NULL  COMMENT '库存数量' DEFAULT 0,
    `category_id` BIGINT NOT NULL  COMMENT '分类ID',
    `is_featured` BOOL NOT NULL  COMMENT '是否推荐' DEFAULT 0,
    `tags` JSON NOT NULL  COMMENT '商品标签',
    KEY `idx_keenrobot_e_state_5b8f6c` (`state`),
    KEY `idx_keenrobot_e_categor_ae628a` (`category_id`)
) CHARACTER SET utf8mb4 COMMENT='商品模型';
CREATE TABLE IF NOT EXISTS `rag_conversation` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    `username` VARCHAR(64) NOT NULL  COMMENT '归属用户（当前阶段恒为 User, 预留真实用户体系）' DEFAULT 'User',
    `title` VARCHAR(255) NOT NULL  COMMENT '会话标题（首问自动截取）' DEFAULT '新对话',
    `pinned` BOOL NOT NULL  COMMENT '是否置顶' DEFAULT 0,
    `created_time` DATETIME(6) NOT NULL  COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(6),
    `updated_time` DATETIME(6)   COMMENT '最近活跃时间',
    `memory_summary` LONGTEXT   COMMENT '对话历史滚动摘要（早期轮次压缩）',
    `summary_up_to_seq` INT NOT NULL  COMMENT '摘要已覆盖到的消息 seq（-1=尚无摘要）' DEFAULT -1,
    KEY `idx_rag_convers_usernam_082205` (`username`),
    KEY `idx_rag_convers_pinned_0d8e14` (`pinned`)
) CHARACTER SET utf8mb4 COMMENT='RAG 对话会话表';
CREATE TABLE IF NOT EXISTS `rag_conversation_message` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    `seq` INT NOT NULL  COMMENT '会话内消息位置(0起, 对外即消息下标)',
    `role` VARCHAR(16) NOT NULL  COMMENT '角色: user/assistant',
    `content` LONGTEXT NOT NULL  COMMENT '消息内容（生成中为增量累积）',
    `status` VARCHAR(16) NOT NULL  COMMENT '状态: done/generating/interrupted' DEFAULT 'done',
    `thinking_ms` INT   COMMENT '思考耗时(毫秒, 仅 AI 回答)',
    `created_time` DATETIME(6)   COMMENT '消息创建时间',
    `conversation_id` BIGINT NOT NULL COMMENT '所属会话',
    UNIQUE KEY `uid_rag_convers_convers_39955b` (`conversation_id`, `seq`),
    CONSTRAINT `fk_rag_conv_rag_conv_66ee41c3` FOREIGN KEY (`conversation_id`) REFERENCES `rag_conversation` (`id`) ON DELETE CASCADE,
    KEY `idx_rag_convers_status_e6e973` (`status`),
    KEY `idx_rag_convers_created_7008b0` (`created_time`)
) CHARACTER SET utf8mb4 COMMENT='RAG 对话消息表';
CREATE TABLE IF NOT EXISTS `rag_conversation_retrieval` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    `message_seq` INT NOT NULL  COMMENT '对应消息在会话内的位置(seq)',
    `detail` JSON NOT NULL  COMMENT '检索详情(改写查询/召回分块等)',
    `created_time` DATETIME(6) NOT NULL  COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(6),
    `updated_time` DATETIME(6) NOT NULL  COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `conversation_id` BIGINT NOT NULL COMMENT '所属会话',
    UNIQUE KEY `uid_rag_convers_convers_916e54` (`conversation_id`, `message_seq`),
    CONSTRAINT `fk_rag_conv_rag_conv_55918cae` FOREIGN KEY (`conversation_id`) REFERENCES `rag_conversation` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4 COMMENT='RAG 对话检索详情表';
CREATE TABLE IF NOT EXISTS `rag_pipeline_history` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    `message` LONGTEXT NOT NULL  COMMENT '历史消息内容',
    `created_time` DATETIME(6)   COMMENT '消息时间',
    KEY `idx_rag_pipelin_created_8024b4` (`created_time`)
) CHARACTER SET utf8mb4 COMMENT='RAG 流水线历史消息表';
CREATE TABLE IF NOT EXISTS `rag_pipeline_state` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    `start_time` DATETIME(6)   COMMENT '流水线启动时间（空闲为 NULL）',
    `updated_time` DATETIME(6) NOT NULL  COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)
) CHARACTER SET utf8mb4 COMMENT='RAG 流水线运行状态表（单行）';
CREATE TABLE IF NOT EXISTS `rag_document` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    `created_time` DATETIME(6) NOT NULL  COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(6),
    `updated_time` DATETIME(6) NOT NULL  COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `job_id` VARCHAR(64) NOT NULL UNIQUE COMMENT '任务ID(doc-<md5前16位>)',
    `filename` VARCHAR(255) NOT NULL UNIQUE COMMENT '文件名',
    `status` VARCHAR(32) NOT NULL  COMMENT '处理状态: queued/splitting/parsing/terminology/analyzing/chunking/embedding/complete/failed' DEFAULT 'queued',
    `abstract` LONGTEXT NOT NULL  COMMENT '文档摘要(失败时存错误描述, 取消时为\'用户取消\')',
    `input_path` VARCHAR(512)   COMMENT '源文件留档路径(input/<job_id>/)',
    `output_path` VARCHAR(512)   COMMENT '产物目录(output/rag_upload/<job_id>/)',
    `artifacts_file` VARCHAR(512)   COMMENT 'docling artifacts 目录路径',
    `sidecar` JSON NOT NULL  COMMENT '侧车文件四元组: meta/blocks/drawings/tables 路径',
    `chunks_file` VARCHAR(512)   COMMENT '分块产物路径',
    `do_ocr` BOOL NOT NULL  COMMENT '是否启用 OCR' DEFAULT 0,
    `force_ocr` BOOL NOT NULL  COMMENT '是否强制 OCR' DEFAULT 0,
    `enable_vlm` BOOL NOT NULL  COMMENT '是否启用多模态(VLM)分析' DEFAULT 0,
    `chunk_strategy` VARCHAR(32)   COMMENT '分块策略(旧记录兼容字段)',
    `page_count` INT   COMMENT 'PDF 页数',
    `total_parts` INT NOT NULL  COMMENT '子文档总数' DEFAULT 1,
    `completed_parts` INT NOT NULL  COMMENT '已完成子文档数' DEFAULT 0,
    `terminology_total_batches` INT NOT NULL  COMMENT '术语抽取总批次' DEFAULT 1,
    `terminology_completed_batches` INT NOT NULL  COMMENT '术语抽取已完成批次' DEFAULT 0,
    `analyzing_stage_skipped` BOOL NOT NULL  COMMENT '是否跳过多模态分析阶段' DEFAULT 0,
    `celery_task_id` VARCHAR(64)   COMMENT 'Celery 任务ID(巡检判活用)',
    `heartbeat_at` DATETIME(6)   COMMENT 'Worker 最近心跳时间(巡检容忍15分钟)',
    `cancel_requested` BOOL NOT NULL  COMMENT '取消标记(守卫: 已取消文档拒绝进度覆盖)' DEFAULT 0,
    `resume` BOOL NOT NULL  COMMENT '重试续跑标记(完成后清除)' DEFAULT 0,
    `content_length` INT   COMMENT '清洗后 markdown 字符数',
    `chunks_count` INT   COMMENT '分块数量',
    `error_trace` LONGTEXT   COMMENT '错误堆栈(尾部500字符)',
    `file_sha256` VARCHAR(64)   COMMENT '最新版本源文件 SHA256(增量更新快速通道: 与上传文件一致则免重处理)',
    `is_updating` BOOL NOT NULL  COMMENT '增量更新处理中(更新期间旧版本向量持续服务, 到达终态后清除)' DEFAULT 0,
    `update_history` JSON   COMMENT '增量更新历史: [{time, filename, reused, embedded}]',
    `parse_start_time` DATETIME(6)   COMMENT '解析开始时间',
    `parse_end_time` DATETIME(6)   COMMENT '解析结束时间',
    `parse_duration` DOUBLE   COMMENT '解析耗时(秒)',
    `term_start_time` DATETIME(6)   COMMENT '术语抽取开始时间',
    `term_end_time` DATETIME(6)   COMMENT '术语抽取结束时间',
    `analyze_start_time` DATETIME(6)   COMMENT '多模态分析开始时间',
    `analyze_end_time` DATETIME(6)   COMMENT '多模态分析结束时间',
    `analyze_duration` DOUBLE   COMMENT '多模态分析耗时(秒)',
    `chunk_start_time` DATETIME(6)   COMMENT '分块开始时间',
    `chunk_end_time` DATETIME(6)   COMMENT '分块结束时间',
    `embed_start_time` DATETIME(6)   COMMENT '嵌入开始时间',
    `embed_end_time` DATETIME(6)   COMMENT '嵌入结束时间',
    `process_end_time` DATETIME(6)   COMMENT '处理结束时间',
    KEY `idx_rag_documen_status_5d8b63` (`status`),
    KEY `idx_rag_documen_celery__9dc14e` (`celery_task_id`),
    KEY `idx_rag_documen_heartbe_8e3982` (`heartbeat_at`)
) CHARACTER SET utf8mb4 COMMENT='RAG 文档表(文档管理页持久化载体)';
CREATE TABLE IF NOT EXISTS `keenrobot_task_center` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    `created_user` VARCHAR(16)   COMMENT '创建人员',
    `updated_user` VARCHAR(16)   COMMENT '更新人员',
    `created_time` DATETIME(6) NOT NULL  COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(6),
    `updated_time` DATETIME(6) NOT NULL  COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `state` SMALLINT NOT NULL  COMMENT '状态(0:启用, 1:禁用)' DEFAULT 0,
    `reserve_1` VARCHAR(64)   COMMENT '备用字段1',
    `reserve_2` VARCHAR(128)   COMMENT '备用字段2',
    `reserve_3` VARCHAR(255)   COMMENT '备用字段3',
    `task_name` VARCHAR(255) NOT NULL  COMMENT '任务名称',
    `task_code` VARCHAR(64) NOT NULL UNIQUE COMMENT '任务标识代码',
    `task_desc` VARCHAR(2048)   COMMENT '任务描述',
    `task_type` VARCHAR(128)   COMMENT '任务分类',
    `task_celery_node` VARCHAR(1024)   COMMENT '任务调度节点',
    `task_kwargs` JSON   COMMENT '任务执行参数',
    `task_celery_time` DATETIME(6)   COMMENT '任务调度时间',
    `task_celery_status` VARCHAR(4)   COMMENT '任务调度状态',
    `task_celery_scheduler` VARCHAR(8)   COMMENT '任务调度模式',
    `task_interval_expr` INT   COMMENT '间隔秒数(interval)',
    `task_datetime_expr` VARCHAR(64)   COMMENT '一次性执行时间(datetime)',
    `task_crontabs_expr` VARCHAR(255)   COMMENT 'Cron表达式',
    `task_notify` JSON   COMMENT '执行反馈配置',
    `task_notifier` JSON   COMMENT '通知人员',
    `task_enabled` BOOL NOT NULL  COMMENT '是否启用调度' DEFAULT 0,
    `task_version` INT NOT NULL  COMMENT '任务版本(每次启动调度+1)' DEFAULT 0,
    UNIQUE KEY `uid_keenrobot_t_task_na_752f3f` (`task_name`, `created_user`),
    KEY `idx_keenrobot_t_state_8dca42` (`state`),
    KEY `idx_keenrobot_t_task_na_6b142f` (`task_name`),
    KEY `idx_keenrobot_t_task_ty_4c3c4a` (`task_type`),
    KEY `idx_keenrobot_t_task_en_bf9dc3` (`task_enabled`)
) CHARACTER SET utf8mb4 COMMENT='任务中心-任务信息表';
CREATE TABLE IF NOT EXISTS `keenrobot_task_center_record` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    `created_user` VARCHAR(16)   COMMENT '创建人员',
    `updated_user` VARCHAR(16)   COMMENT '更新人员',
    `created_time` DATETIME(6) NOT NULL  COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(6),
    `updated_time` DATETIME(6) NOT NULL  COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `state` SMALLINT NOT NULL  COMMENT '状态(0:启用, 1:禁用)' DEFAULT 0,
    `reserve_1` VARCHAR(64)   COMMENT '备用字段1',
    `reserve_2` VARCHAR(128)   COMMENT '备用字段2',
    `reserve_3` VARCHAR(255)   COMMENT '备用字段3',
    `task_id` BIGINT   COMMENT '任务ID',
    `task_version` INT   COMMENT '任务版本(执行时快照)',
    `task_name` VARCHAR(255)   COMMENT '任务名称',
    `task_kwargs` JSON   COMMENT '任务执行参数快照',
    `task_summary` LONGTEXT   COMMENT '执行摘要',
    `task_error` LONGTEXT   COMMENT '错误信息',
    `celery_id` VARCHAR(255) NOT NULL  COMMENT 'Celery调度ID',
    `task_celery_node` VARCHAR(512)   COMMENT '任务调度节点',
    `celery_trace_id` VARCHAR(255)   COMMENT '调度回溯ID',
    `task_celery_status` VARCHAR(4) NOT NULL  COMMENT '任务调度状态' DEFAULT '正在执行',
    `task_celery_scheduler` VARCHAR(8)   COMMENT '任务调度模式',
    `celery_start_time` DATETIME(6)   COMMENT '开始时间',
    `celery_end_time` DATETIME(6)   COMMENT '结束时间',
    `celery_duration` VARCHAR(64)   COMMENT '耗时',
    KEY `idx_keenrobot_t_state_1ef1ca` (`state`),
    KEY `idx_keenrobot_t_task_id_165300` (`task_id`),
    KEY `idx_keenrobot_t_task_ve_bed05d` (`task_version`),
    KEY `idx_keenrobot_t_task_na_3fff7e` (`task_name`),
    KEY `idx_keenrobot_t_celery__0069ce` (`celery_id`),
    KEY `idx_keenrobot_t_task_ce_1c6e48` (`task_celery_node`),
    KEY `idx_keenrobot_t_celery__a2eddc` (`celery_trace_id`),
    KEY `idx_keenrobot_t_task_id_af1536` (`task_id`, `task_version`),
    KEY `idx_keenrobot_t_task_ce_a53ab8` (`task_celery_status`),
    KEY `idx_keenrobot_t_celery__4d85d4` (`celery_start_time`),
    KEY `idx_keenrobot_t_task_ce_7a0d8d` (`task_celery_status`, `celery_start_time`)
) CHARACTER SET utf8mb4 COMMENT='任务中心-执行记录表';
CREATE TABLE IF NOT EXISTS `keenrobot_test_case_task` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    `created_time` DATETIME(6) NOT NULL  COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(6),
    `updated_time` DATETIME(6) NOT NULL  COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `created_user` VARCHAR(16)   COMMENT '创建人员',
    `updated_user` VARCHAR(16)   COMMENT '更新人员',
    `folder_path` VARCHAR(500) NOT NULL  COMMENT '输出文件夹路径' DEFAULT '',
    `app_system` VARCHAR(50) NOT NULL  COMMENT '应用系统' DEFAULT '',
    `requirement_name` VARCHAR(200) NOT NULL  COMMENT '需求名称' DEFAULT '',
    `status` VARCHAR(20) NOT NULL  COMMENT '任务状态' DEFAULT 'generating',
    `error_reason` VARCHAR(500)   COMMENT '错误原因' DEFAULT ''
) CHARACTER SET utf8mb4 COMMENT='测试用例生成任务模型';
CREATE TABLE IF NOT EXISTS `keenrobot_user` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    `state` SMALLINT NOT NULL  COMMENT '状态(0:启用, 1:禁用)' DEFAULT 0,
    `created_time` DATETIME(6) NOT NULL  COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(6),
    `updated_time` DATETIME(6) NOT NULL  COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `created_user` VARCHAR(16)   COMMENT '创建人员',
    `updated_user` VARCHAR(16)   COMMENT '更新人员',
    `username` VARCHAR(32) NOT NULL UNIQUE COMMENT '用户账号',
    `password` VARCHAR(255) NOT NULL  COMMENT '用户密码',
    `alias` VARCHAR(64) NOT NULL  COMMENT '用户姓名',
    `email` VARCHAR(64) NOT NULL  COMMENT '用户邮箱',
    `phone` VARCHAR(20)   COMMENT '用户电话',
    `motto` VARCHAR(255)   COMMENT '用户签名',
    `avatar` VARCHAR(255)   COMMENT '用户头像',
    `is_active` BOOL NOT NULL  COMMENT '是否激活' DEFAULT 1,
    `is_superuser` BOOL NOT NULL  COMMENT '是否为超级管理员' DEFAULT 0,
    `last_login` DATETIME(6)   COMMENT '最后一次登陆时间',
    `token_version` INT NOT NULL  COMMENT 'Token版本号，用于吊销用户所有Token' DEFAULT 0,
    `address` VARCHAR(255)   COMMENT '用户住址',
    `gender` SMALLINT NOT NULL  COMMENT '用户性别: 0未知 1男 2女' DEFAULT 0,
    `user_type` SMALLINT NOT NULL  COMMENT '用户类型：0xx 1xx 2xx' DEFAULT 0,
    `emergency_name` VARCHAR(32)   COMMENT '紧急联系人',
    `emergency_phone` VARCHAR(20)   COMMENT '紧急联系电话',
    UNIQUE KEY `uid_keenrobot_u_alias_ac1839` (`alias`, `email`),
    KEY `idx_keenrobot_u_state_aefb13` (`state`),
    KEY `idx_keenrobot_u_is_acti_f5a960` (`is_active`),
    KEY `idx_keenrobot_u_is_supe_8cdf9e` (`is_superuser`),
    KEY `idx_keenrobot_u_last_lo_44d475` (`last_login`)
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `keenrobot_mcp_servers` (
    `id` VARCHAR(64) NOT NULL  PRIMARY KEY COMMENT 'MCP服务ID',
    `state` SMALLINT NOT NULL  COMMENT '状态(0:启用, 1:禁用)' DEFAULT 0,
    `created_time` DATETIME(6) NOT NULL  COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(6),
    `updated_time` DATETIME(6) NOT NULL  COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `name` VARCHAR(128) NOT NULL  COMMENT '服务名称',
    `description` LONGTEXT   COMMENT '服务描述',
    `is_enabled` BOOL NOT NULL  COMMENT '是否启用' DEFAULT 1,
    `transport` VARCHAR(32) NOT NULL  COMMENT '传输方式(stdio/sse/http)' DEFAULT 'stdio',
    `config` JSON   COMMENT '连接配置',
    `user_id` BIGINT NOT NULL COMMENT '所属用户',
    CONSTRAINT `fk_keenrobo_keenrobo_e23ffb01` FOREIGN KEY (`user_id`) REFERENCES `keenrobot_user` (`id`) ON DELETE CASCADE,
    KEY `idx_keenrobot_m_state_b64b9e` (`state`)
) CHARACTER SET utf8mb4 COMMENT='MCP 服务配置';
CREATE TABLE IF NOT EXISTS `keenrobot_skills` (
    `id` VARCHAR(64) NOT NULL  PRIMARY KEY COMMENT '技能ID',
    `state` SMALLINT NOT NULL  COMMENT '状态(0:启用, 1:禁用)' DEFAULT 0,
    `created_time` DATETIME(6) NOT NULL  COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(6),
    `updated_time` DATETIME(6) NOT NULL  COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `name` VARCHAR(128) NOT NULL  COMMENT '技能名称',
    `description` LONGTEXT   COMMENT '技能描述',
    `is_enabled` BOOL NOT NULL  COMMENT '是否启用' DEFAULT 1,
    `config` JSON   COMMENT '技能配置(提示词/参数等)',
    `user_id` BIGINT NOT NULL COMMENT '所属用户',
    CONSTRAINT `fk_keenrobo_keenrobo_b2edeea6` FOREIGN KEY (`user_id`) REFERENCES `keenrobot_user` (`id`) ON DELETE CASCADE,
    KEY `idx_keenrobot_s_state_be7348` (`state`)
) CHARACTER SET utf8mb4 COMMENT='Agent 技能定义';
CREATE TABLE IF NOT EXISTS `keenrobot_knowledge_bases` (
    `id` VARCHAR(64) NOT NULL  PRIMARY KEY COMMENT '知识库ID',
    `state` SMALLINT NOT NULL  COMMENT '状态(0:启用, 1:禁用)' DEFAULT 0,
    `created_time` DATETIME(6) NOT NULL  COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(6),
    `updated_time` DATETIME(6) NOT NULL  COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `knowledge_name` VARCHAR(128) NOT NULL  COMMENT '知识库名称',
    `description` LONGTEXT   COMMENT '知识库描述',
    `is_public` BOOL NOT NULL  COMMENT '是否公开' DEFAULT 0,
    `chunk_size` INT   COMMENT '分块大小(字符数)，为空时使用全局配置',
    `chunk_overlap` INT   COMMENT '分块重叠(字符数)，为空时使用全局配置',
    `user_id` BIGINT NOT NULL COMMENT '所属用户',
    CONSTRAINT `fk_keenrobo_keenrobo_75e2ad14` FOREIGN KEY (`user_id`) REFERENCES `keenrobot_user` (`id`) ON DELETE CASCADE,
    KEY `idx_keenrobot_k_state_aa0f13` (`state`)
) CHARACTER SET utf8mb4 COMMENT='知识库模型';
CREATE TABLE IF NOT EXISTS `keenrobot_documents` (
    `id` VARCHAR(64) NOT NULL  PRIMARY KEY COMMENT '文档ID',
    `created_time` DATETIME(6) NOT NULL  COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(6),
    `updated_time` DATETIME(6) NOT NULL  COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `filename` VARCHAR(255) NOT NULL  COMMENT '文件名',
    `file_type` VARCHAR(32) NOT NULL  COMMENT '文件类型(pdf/txt/docx)' DEFAULT 'pdf',
    `file_path` VARCHAR(512) NOT NULL  COMMENT '文件路径',
    `file_size` INT NOT NULL  COMMENT '文件大小(字节)',
    `content_hash` VARCHAR(64)   COMMENT '文件内容SHA256',
    `embedding_model` VARCHAR(64)   COMMENT '向量化模型',
    `chunk_count` INT NOT NULL  COMMENT '分块数量' DEFAULT 0,
    `status` VARCHAR(32) NOT NULL  COMMENT '处理状态' DEFAULT 'processing',
    `error_message` LONGTEXT   COMMENT '错误信息',
    `knowledge_base_id` VARCHAR(64) NOT NULL COMMENT '所属知识库',
    UNIQUE KEY `uid_keenrobot_d_knowled_8dd4e3` (`knowledge_base_id`, `content_hash`),
    CONSTRAINT `fk_keenrobo_keenrobo_9ee4470d` FOREIGN KEY (`knowledge_base_id`) REFERENCES `keenrobot_knowledge_bases` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4 COMMENT='文档模型';
CREATE TABLE IF NOT EXISTS `keenrobot_document_chunks` (
    `id` VARCHAR(64) NOT NULL  PRIMARY KEY COMMENT '分块ID',
    `created_time` DATETIME(6) NOT NULL  COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(6),
    `updated_time` DATETIME(6) NOT NULL  COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `content` LONGTEXT NOT NULL  COMMENT '分块内容',
    `chunk_index` INT NOT NULL  COMMENT '分块序号',
    `page_number` INT   COMMENT 'PDF页码(从1开始)',
    `chroma_id` VARCHAR(128)   COMMENT 'Chroma向量ID',
    `document_id` VARCHAR(64) NOT NULL COMMENT '所属文档',
    CONSTRAINT `fk_keenrobo_keenrobo_a6b21ca6` FOREIGN KEY (`document_id`) REFERENCES `keenrobot_documents` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4 COMMENT='文档分块模型';
CREATE TABLE IF NOT EXISTS `keenrobot_model_configs` (
    `id` VARCHAR(64) NOT NULL  PRIMARY KEY COMMENT '配置ID',
    `state` SMALLINT NOT NULL  COMMENT '状态(0:启用, 1:禁用)' DEFAULT 0,
    `created_time` DATETIME(6) NOT NULL  COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(6),
    `updated_time` DATETIME(6) NOT NULL  COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `created_user` VARCHAR(16)   COMMENT '创建人员',
    `updated_user` VARCHAR(16)   COMMENT '更新人员',
    `config_name` VARCHAR(64) NOT NULL  COMMENT '配置名称' DEFAULT '默认配置',
    `config_desc` VARCHAR(255)   COMMENT '配置说明',
    `model_provider` VARCHAR(32) NOT NULL  COMMENT '模型所属供应商' DEFAULT 'custom',
    `model_thinking` BOOL NOT NULL  COMMENT '模型深度思考开关' DEFAULT 0,
    `llm_api_key` VARCHAR(512)   COMMENT 'LLM API Key（加密存储）',
    `llm_base_url` VARCHAR(512)   COMMENT 'LLM API Base URL',
    `llm_model_name` VARCHAR(64) NOT NULL  COMMENT 'API model 参数' DEFAULT 'deepseek-chat',
    `temperature` DOUBLE NOT NULL  COMMENT '温度(控制AI回答随机性)' DEFAULT 0.7,
    `max_tokens` INT NOT NULL  COMMENT '限制单次回答的最大输出Token数' DEFAULT 4096,
    `top_p` DOUBLE NOT NULL  COMMENT 'Top P(核采样参数)' DEFAULT 0.95,
    `top_k` INT NOT NULL  COMMENT 'Top K(知识库检索条数)' DEFAULT 5,
    `max_history_rounds` INT NOT NULL  COMMENT '保留历史对话轮数' DEFAULT 10,
    `score_threshold` DOUBLE NOT NULL  COMMENT '检索相似度阈值(0-1)' DEFAULT 0,
    `system_prompt` LONGTEXT   COMMENT '系统提示词，支持{context}占位符',
    `is_default` BOOL NOT NULL  COMMENT '是否默认配置' DEFAULT 1,
    `user_id` BIGINT NOT NULL COMMENT '所属用户',
    CONSTRAINT `fk_keenrobo_keenrobo_be3d5f5e` FOREIGN KEY (`user_id`) REFERENCES `keenrobot_user` (`id`) ON DELETE CASCADE,
    KEY `idx_keenrobot_m_state_9f382d` (`state`)
) CHARACTER SET utf8mb4 COMMENT='模型配置';
CREATE TABLE IF NOT EXISTS `keenrobot_conversations` (
    `id` VARCHAR(64) NOT NULL  PRIMARY KEY COMMENT '对话ID',
    `state` SMALLINT NOT NULL  COMMENT '状态(0:启用, 1:禁用)' DEFAULT 0,
    `created_time` DATETIME(6) NOT NULL  COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(6),
    `updated_time` DATETIME(6) NOT NULL  COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `title` VARCHAR(255) NOT NULL  COMMENT '对话标题' DEFAULT '新对话',
    `knowledge_base_ids` JSON   COMMENT '关联知识库ID列表',
    `skill_ids` JSON   COMMENT '关联技能ID列表',
    `mcp_ids` JSON   COMMENT '关联MCP服务ID列表',
    `model_config_id` VARCHAR(64) COMMENT '所属模型配置',
    `user_id` BIGINT NOT NULL COMMENT '所属用户',
    CONSTRAINT `fk_keenrobo_keenrobo_7946670a` FOREIGN KEY (`model_config_id`) REFERENCES `keenrobot_model_configs` (`id`) ON DELETE SET NULL,
    CONSTRAINT `fk_keenrobo_keenrobo_fe85a5a4` FOREIGN KEY (`user_id`) REFERENCES `keenrobot_user` (`id`) ON DELETE CASCADE,
    KEY `idx_keenrobot_c_state_6cebe7` (`state`)
) CHARACTER SET utf8mb4 COMMENT='对话会话模型';
CREATE TABLE IF NOT EXISTS `keenrobot_messages` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '消息ID',
    `state` SMALLINT NOT NULL  COMMENT '状态(0:启用, 1:禁用)' DEFAULT 0,
    `created_time` DATETIME(6) NOT NULL  COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(6),
    `updated_time` DATETIME(6) NOT NULL  COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `role` VARCHAR(20) NOT NULL  COMMENT '消息角色',
    `content` LONGTEXT NOT NULL  COMMENT '消息内容',
    `prompt_tokens` INT   COMMENT '输入Token数(Prompt)',
    `completion_tokens` INT   COMMENT '输出Token数(Completion)',
    `reasoning_tokens` INT   COMMENT '推理Token数(Thinking/Reasoning)',
    `process_trace` JSON   COMMENT '过程追踪(推理链/工具调用等)',
    `conversation_id` VARCHAR(64) NOT NULL COMMENT '所属对话',
    CONSTRAINT `fk_keenrobo_keenrobo_caaa6119` FOREIGN KEY (`conversation_id`) REFERENCES `keenrobot_conversations` (`id`) ON DELETE CASCADE,
    KEY `idx_keenrobot_m_state_5bb882` (`state`)
) CHARACTER SET utf8mb4 COMMENT='聊天消息模型';
CREATE TABLE IF NOT EXISTS `aerich` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `version` VARCHAR(255) NOT NULL,
    `app` VARCHAR(100) NOT NULL,
    `content` JSON NOT NULL
) CHARACTER SET utf8mb4;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """


MODELS_STATE = (
    "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"
)
