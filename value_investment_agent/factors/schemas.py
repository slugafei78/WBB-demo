"""Point-in-time (PIT) data model and tri-categorical factor groups (I/II/III)."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class FactorGroup(str, Enum):
    """Horizon buckets from the research proposal."""

    FUNDAMENTAL = "I"  # ~3–5y intrinsic drivers
    RISK_PREMIUM = "II"  # ~1–3mo
    MACRO_MOMENTUM = "III"  # ~1y macro + momentum；磁盘上宏观时间序列见仓库 factors/macro/series/（不按 symbol 分目录）


class PITKey(BaseModel):
    """Join key for any observation: no feature without an as-of timestamp."""

    symbol: str = Field(..., description="Ticker or security identifier")
    asof_date: date = Field(..., description="Simulation date; features known by EOD this day")
    source_timestamp: datetime | None = Field(
        default=None,
        description="Vendor or filing acceptance time when stricter PIT is needed",
    )


class FactorObservation(BaseModel):
    """Single named factor value under PIT."""

    key: PITKey
    group: FactorGroup
    name: str
    value: float
    unit: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TriCategoryFactors(BaseModel):
    """Bundle of factor vectors for one (symbol, asof_date)."""

    key: PITKey
    group_i: dict[str, float] = Field(default_factory=dict, description="Fundamental")
    group_ii: dict[str, float] = Field(default_factory=dict, description="Risk premium")
    group_iii: dict[str, float] = Field(default_factory=dict, description="Macro & momentum")


class AuditLogEntry(BaseModel):
    """Audit trail for LLM / human review (prompt hashes, chunk ids)."""

    key: PITKey
    event: str
    payload: dict[str, Any] = Field(default_factory=dict)
