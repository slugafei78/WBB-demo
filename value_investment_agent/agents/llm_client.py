"""Mock / Gemini / OpenAI 的 JSON 客户端。"""

from __future__ import annotations

import json
import os
from typing import Protocol

from value_investment_agent.factors.llm_schemas import (
    KernelRouterOutput,
    QualitativeCitation,
    QualitativeFactorScore,
    QualitativeScoringOutput,
    default_qualitative_factor_names,
)


class LLMClient(Protocol):
    def complete_json(self, system: str, user: str) -> str: ...


class MockLLMClient:
    def complete_json(self, system: str, user: str) -> str:
        if "router" in system.lower() or "kernel" in system.lower():
            out = KernelRouterOutput(
                business_model_summary="Mock: mature dividend-paying consumer franchise.",
                kernel="dcf",
                primary_quantitative_drivers=["fcf_margin", "revenue_growth"],
                peer_tickers_suggested=["PEP"],
            )
            return out.model_dump_json()
        names = default_qualitative_factor_names()
        factors = [
            QualitativeFactorScore(
                name=n,
                score_1_to_10=6,
                citations=[
                    QualitativeCitation(
                        source_type="other",
                        reference="mock",
                        excerpt="offline placeholder",
                    )
                ],
            )
            for n in names[:20]
        ]
        out = QualitativeScoringOutput(factors=factors, narrative="Mock qualitative pass.")
        return out.model_dump_json()


class GeminiJsonClient:
    """
    Google Gemini JSON；GEMINI_API_KEY 或 GOOGLE_API_KEY；GEMINI_MODEL 默认见 gemini_call.DEFAULT_GEMINI_MODEL。
    """

    def __init__(self, model: str | None = None):
        from value_investment_agent.llm.gemini_call import DEFAULT_GEMINI_MODEL

        key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key:
            raise ValueError("Set GEMINI_API_KEY or GOOGLE_API_KEY")
        self.model_name = model or os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)

    def complete_json(self, system: str, user: str) -> str:
        from value_investment_agent.llm.gemini_call import gemini_generate_json

        return gemini_generate_json(system, user, model_name=self.model_name)


class OpenAIJsonClient:
    def __init__(self, model: str | None = None):
        try:
            from openai import OpenAI
        except ImportError as e:
            raise ImportError("pip install openai for OpenAIJsonClient") from e
        self._client = OpenAI()
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    def complete_json(self, system: str, user: str) -> str:
        resp = self._client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
        )
        return resp.choices[0].message.content or "{}"


def parse_router_json(raw: str) -> KernelRouterOutput:
    return KernelRouterOutput.model_validate(json.loads(raw))


def parse_qualitative_json(raw: str) -> QualitativeScoringOutput:
    return QualitativeScoringOutput.model_validate(json.loads(raw))
