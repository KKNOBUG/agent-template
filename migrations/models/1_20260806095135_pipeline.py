from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS `rag_pipeline_history` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    `message` LONGTEXT NOT NULL COMMENT '历史消息内容',
    `created_time` DATETIME(6)   COMMENT '消息时间',
    KEY `idx_rag_pipelin_created_8024b4` (`created_time`)
) CHARACTER SET utf8mb4 COMMENT='RAG 流水线历史消息表';
        CREATE TABLE IF NOT EXISTS `rag_pipeline_state` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    `start_time` DATETIME(6)   COMMENT '流水线启动时间（空闲为 NULL）',
    `updated_time` DATETIME(6) NOT NULL COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)
) CHARACTER SET utf8mb4 COMMENT='RAG 流水线运行状态表（单行）';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS `rag_pipeline_history`;
        DROP TABLE IF EXISTS `rag_pipeline_state`;"""


MODELS_STATE = (
    "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"
)
