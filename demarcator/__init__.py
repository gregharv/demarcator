from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SRC_PACKAGE = _ROOT / "src" / "demarcator"

if _SRC_PACKAGE.exists():
    __path__.append(str(_SRC_PACKAGE))

from .bootstrap import create_seeded_service

__all__ = ["create_seeded_service"]
