from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


SUPPORTED_REVIEW_TABLE_CODES = frozenset({"FW038", "FW039"})
TARGET_APPROVAL_GROUP = "开发测试审批组"


def is_supported_review_table(table_code: Any) -> bool:
    """判断是否为当前支持预审的工单表。"""
    return str(table_code or "").strip().upper() in SUPPORTED_REVIEW_TABLE_CODES


def is_review_record(table_code: Any, record: Any) -> bool:
    """只接收FW038/FW039中属于开发测试审批组的记录。"""
    if not is_supported_review_table(table_code):
        return False

    if not isinstance(record, dict):
        return False

    approval_group = str(record.get("extra5") or "").strip()
    return approval_group == TARGET_APPROVAL_GROUP

class PushTicketItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    table_code: str = Field(alias="tableCode", min_length=1)
    table_name: str = Field(alias="tableName", min_length=1)
    records: list[dict[str, Any]] = Field(default_factory=list)


class PushTicketRequest(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    message_id: str = Field(alias="messageId", min_length=1, max_length=128)
    push_time: datetime = Field(alias="pushTime")
    items: list[PushTicketItem] = Field(default_factory=list)

    def raw_payload(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json", by_alias=True)
        payload["pushTime"] = self.push_time.strftime("%Y-%m-%d %H:%M:%S")
        return payload

    # def review_record_count(self) -> int:
    #     return sum(
    #         len(item.records)
    #         for item in self.items
    #         if item.table_code.upper() in {"FW038", "FW039"}
    #     )

    def review_record_count(self) -> int:
        return sum(
            1
            for item in self.items
            for record in item.records
            if is_review_record(item.table_code, record)
        )

    def received_record_count(self) -> int:
        return sum(len(item.records) for item in self.items)


class PushTicketAckData(BaseModel):
    messageId: str
    requestId: str
    status: str
    receivedRecords: int = Field(ge=0)
    acceptedRecords: int = Field(ge=0)
    ignoredRecords: int = Field(ge=0)


class PushTicketAck(BaseModel):
    code: str = "000000"
    message: str
    data: PushTicketAckData
