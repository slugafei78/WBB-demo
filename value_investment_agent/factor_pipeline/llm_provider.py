"""Backward-compatible re-export (implementation in value_investment_agent.llm.llm_provider)."""

from value_investment_agent.llm.llm_provider import LLMProvider, gemini_api_key, resolve_llm_provider

__all__ = ["LLMProvider", "gemini_api_key", "resolve_llm_provider"]
