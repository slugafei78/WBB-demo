"""Gemini / OpenAI JSON completion — standalone to avoid importing factor_pipeline (torch)."""

from __future__ import annotations

import os

from value_investment_agent.llm.llm_provider import dotenv_load_hint_for_error, load_dotenv_from_repo_root

# 若本文件先于 llm_provider 被导入，仍保证加载仓库根 `.env`
load_dotenv_from_repo_root(override=True)


def complete_json_gemini(system: str, user: str) -> str:
    from value_investment_agent.llm.gemini_call import gemini_generate_json

    try:
        text = gemini_generate_json(system, user)
    except ValueError as e:
        if "缺少 GEMINI" in str(e):
            raise ValueError(
                str(e) + "\n\n" + dotenv_load_hint_for_error()
            ) from e
        raise
    return text or "{}"


def complete_json_openai(system: str, user: str) -> str:
    try:
        from openai import OpenAI
    except ImportError as e:
        raise ImportError("请 pip install openai 并设置 OPENAI_API_KEY") from e
    client = OpenAI()
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    resp = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
    )
    return resp.choices[0].message.content or "{}"
