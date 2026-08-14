# -*- coding: utf-8 -*-
import contextvars

CTX_USER_ID: contextvars.ContextVar[int] = contextvars.ContextVar("user_id", default=0)
