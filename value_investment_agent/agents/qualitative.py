"""定性子流程：估值 kernel 路由 + 基于语料的 1–10 因子（多轮 JSON）。"""

from __future__ import annotations

import hashlib
from typing import Any

from value_investment_agent.agents.llm_client import (
    GeminiJsonClient,
    MockLLMClient,
    OpenAIJsonClient,
    parse_qualitative_json,
    parse_router_json,
)
from value_investment_agent.agents.retrieval import EdgarSnapshotRetriever
from value_investment_agent.factors.llm_schemas import KernelRouterOutput, QualitativeScoringOutput
from value_investment_agent.factors.schemas import AuditLogEntry, PITKey


class QualitativeSubAgent:
    """调用 SOTA LLM 完成两回合结构化输出（路由 + 定性打分）。"""

    def __init__(
        self,
        retriever: EdgarSnapshotRetriever | None = None,
        llm: Any | None = None,
    ):
        self.retriever = retriever or EdgarSnapshotRetriever()
        self.llm = llm if llm is not None else make_llm_from_env()

    @staticmethod
    def _hash_prompt(system: str, user: str) -> str:
        h = hashlib.sha256()
        h.update(system.encode("utf-8"))
        h.update(b"\n")
        h.update(user.encode("utf-8"))
        return h.hexdigest()[:24]

    def turn1_router(self, key: PITKey, company_blurb: str) -> tuple[KernelRouterOutput, AuditLogEntry]:
        system = (
            "You are a value investing analyst. Output strict JSON for kernel routing: "
            "business_model_summary, kernel (dcf|price_to_sales|pb_roe), "
            "primary_quantitative_drivers (list of short snake_case names), "
            "peer_tickers_suggested (list of tickers)."
        )
        user = f"Symbol slug {key.symbol} asof {key.asof_date.isoformat()}.\nContext:\n{company_blurb}\n"
        raw = self.llm.complete_json(system, user)
        parsed = parse_router_json(raw)
        audit = AuditLogEntry(
            key=key,
            event="turn1_router",
            payload={"prompt_hash": self._hash_prompt(system, user), "raw_json": raw[:8000]},
        )
        return parsed, audit

    def turn2_qualitative(
        self,
        key: PITKey,
        router: KernelRouterOutput,
    ) -> tuple[QualitativeScoringOutput, list[AuditLogEntry]]:
        chunks = self.retriever.retrieve(key.symbol, key.asof_date.isoformat())
        corpus = "\n\n".join(c.text[:4000] for c in chunks) if chunks else "(no local filing text)"
        system = (
            "Score qualitative fundamental factors from 1-10 using only the provided corpus. "
            "Output JSON: factors[{name, score_1_to_10, citations[{source_type, reference, excerpt}]}], "
            "narrative. Use snake_case names."
        )
        user = (
            f"Symbol slug {key.symbol} asof {key.asof_date.isoformat()}.\n"
            f"Kernel choice: {router.kernel}.\nBusiness: {router.business_model_summary}\n\n"
            f"Corpus:\n{corpus}"
        )
        raw = self.llm.complete_json(system, user)
        parsed = parse_qualitative_json(raw)
        audits: list[AuditLogEntry] = [
            AuditLogEntry(
                key=key,
                event="turn2_qualitative",
                payload={
                    "prompt_hash": self._hash_prompt(system, user),
                    "chunk_ids": [c.chunk_id for c in chunks],
                    "raw_json": raw[:8000],
                },
            )
        ]
        return parsed, audits

    def qualitative_to_map(self, q: QualitativeScoringOutput) -> dict[str, float]:
        return {f.name: float(f.score_1_to_10) for f in q.factors}


def make_llm_from_env() -> Any:
    import os

    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        try:
            return GeminiJsonClient()
        except Exception:
            pass
    if os.environ.get("OPENAI_API_KEY"):
        return OpenAIJsonClient()
    return MockLLMClient()


# 兼容旧名称
ValueAgentPipeline = QualitativeSubAgent
