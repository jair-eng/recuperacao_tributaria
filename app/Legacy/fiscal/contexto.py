from __future__ import annotations

from typing import Optional, Dict, Any, List, Tuple
from decimal import Decimal
from contextvars import ContextVar


_CTX_DB: ContextVar[Any] = ContextVar("_CTX_DB", default=None)
_CTX_EMPRESA_ID: ContextVar[Optional[int]] = ContextVar("_CTX_EMPRESA_ID", default=None)


def dec_any(v: Any) -> Decimal:
    s = str(v or "").strip()
    if not s:
        return Decimal("0")

    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
        return Decimal(s)

    if "," in s:
        s = s.replace(".", "").replace(",", ".")
        return Decimal(s)

    return Decimal(s)


def get_fiscal_db() -> Any:
    return _CTX_DB.get()

def get_fiscal_empresa_id() -> Optional[int]:
    return _CTX_EMPRESA_ID.get()





