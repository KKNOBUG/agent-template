# -*- coding: utf-8 -*-
from applications.base.services.audit_crud import AuditCrud


async def get_audit_crud() -> AuditCrud:
    """获取审计日志 CRUD 服务实例"""
    return AuditCrud()
