from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS `rag_conversation` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    `username` VARCHAR(64) NOT NULL  COMMENT '归属用户（当前阶段恒为 User, 预留真实用户体系）' DEFAULT 'User',
    `title` VARCHAR(255) NOT NULL  COMMENT '会话标题（首问自动截取）' DEFAULT '新对话',
    `pinned` BOOL NOT NULL  COMMENT '是否置顶' DEFAULT 0,
    `created_time` DATETIME(6) NOT NULL  COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(6),
    `updated_time` DATETIME(6)   COMMENT '最近活跃时间',
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
