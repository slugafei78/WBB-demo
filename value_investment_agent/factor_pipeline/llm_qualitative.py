"""
定性因子：调用大模型输出 0–20 分；默认 auto 优先 Gemini，其次 OpenAI。
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Literal

from pydantic import BaseModel, Field

from value_investment_agent.factors.llm_schemas import default_qualitative_factor_names
from value_investment_agent.llm.json_completion import (
    complete_json_gemini as _complete_json_gemini,
    complete_json_openai as _complete_json_openai,
)
from value_investment_agent.llm.llm_provider import LLMProvider, gemini_api_key, resolve_llm_provider


class QualFactor0To20(BaseModel):
    name: str
    score_0_to_20: int = Field(..., ge=0, le=20)
    brief_reason: str | None = Field(default=None, max_length=500)


class QualitativeScore0To20Output(BaseModel):
    factors: list[QualFactor0To20]
    summary: str | None = None


def ensure_all_factors_0_20(out: QualitativeScore0To20Output) -> QualitativeScore0To20Output:
    have = {f.name for f in out.factors}
    names = default_qualitative_factor_names()
    extra = [
        QualFactor0To20(name=n, score_0_to_20=10, brief_reason="imputed_missing")
        for n in names
        if n not in have
    ]
    return QualitativeScore0To20Output(factors=list(out.factors) + extra, summary=out.summary)


def scores_0_20_to_synthesizer_1_10(scores: dict[str, float]) -> dict[str, float]:
    out: dict[str, float] = {}
    for k, v in scores.items():
        x = max(0.0, min(20.0, float(v)))
        out[k] = 1.0 + (x / 20.0) * 9.0
    return out


def _mock_scores_for_period(context_key: str) -> QualitativeScore0To20Output:
    names = default_qualitative_factor_names()
    factors: list[QualFactor0To20] = []
    for n in names:
        h = int(hashlib.sha256((context_key + n).encode()).hexdigest()[:8], 16)
        score = 8 + (h % 9)
        factors.append(QualFactor0To20(name=n, score_0_to_20=score, brief_reason="mock"))
    return QualitativeScore0To20Output(factors=factors, summary="mock offline scoring")


def _qualitative_prompts(
    *,
    company_name: str,
    symbol: str,
    asof_date: str,
    business_summary: str,
    quantitative_snippet: str,
    news_excerpt: str,
) -> tuple[str, str]:
    names = default_qualitative_factor_names()
    system = (
        "You are a conservative value analyst. Output a single JSON object with keys: "
        "factors (array of {name, score_0_to_20, brief_reason}), summary. "
        f"Each name must be one of: {names}. "
        "score_0_to_20 is integer 0-20 (20=excellent moat/governance etc., 0=severe concern). "
        "Base scores only on the provided text; if insufficient evidence, use mid scores ~10."
    )
    user = (
        f"Company: {company_name}\nSymbol slug: {symbol}\nAs-of: {asof_date}\n\n"
        f"Business summary:\n{business_summary[:6000]}\n\n"
        f"Quantitative snapshot:\n{quantitative_snippet[:4000]}\n\n"
        f"News / headlines (may be incomplete historically):\n{news_excerpt[:4000]}\n"
    )
    return system, user


def run_llm_qualitative_0_20(
    *,
    company_name: str,
    symbol: str,
    asof_date: str,
    business_summary: str,
    quantitative_snippet: str,
    news_excerpt: str,
    llm_provider: LLMProvider = "auto",
    use_openai: bool | None = None,
) -> QualitativeScore0To20Output:
    if use_openai is False:
        resolved: Literal["gemini", "openai", "mock"] = "mock"
    elif use_openai is True:
        resolved = "openai"
    else:
        resolved = resolve_llm_provider(llm_provider)

    if resolved == "mock":
        return _mock_scores_for_period(f"{symbol}|{asof_date}")

    system, user = _qualitative_prompts(
        company_name=company_name,
        symbol=symbol,
        asof_date=asof_date,
        business_summary=business_summary,
        quantitative_snippet=quantitative_snippet,
        news_excerpt=news_excerpt,
    )

    raw = "{}"
    try:
        if resolved == "gemini":
            raw = _complete_json_gemini(system, user)
        else:
            raw = _complete_json_openai(system, user)
    except Exception:
        raw = "{}"

    try:
        data = json.loads(raw)
        out = QualitativeScore0To20Output.model_validate(data)
    except Exception:
        out = _mock_scores_for_period(f"llm_json_fallback|{asof_date}")
    return ensure_all_factors_0_20(out)
