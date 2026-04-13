"""Gemini 调用：优先使用新版 ``google-genai``，否则回退 ``google.generativeai``；429 时重试。"""

from __future__ import annotations

import os
import random
import re
import time

from value_investment_agent.llm.llm_provider import gemini_api_key, load_dotenv_from_repo_root

# 默认模型；可在 .env 设 GEMINI_MODEL 覆盖。
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"

_USE_NEW_SDK: bool | None = None


def resolved_gemini_model() -> str:
    return os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL


def _retry_delay_seconds(exc: BaseException, attempt: int) -> float:
    s = str(exc)
    m = re.search(r"retry in ([0-9.]+)\s*s", s, re.I)
    if m:
        return min(float(m.group(1)) + random.uniform(0.5, 2.0), 180.0)
    m2 = re.search(r"seconds:\s*(\d+)", s)
    if m2:
        return min(float(m2.group(1)) + random.uniform(0.5, 2.0), 180.0)
    base = float(os.environ.get("GEMINI_RETRY_BASE_SEC", "20"))
    return min(base * (2**attempt) + random.uniform(0, 3), 180.0)


def _is_quota_or_rate_limit(exc: BaseException) -> bool:
    name = type(exc).__name__
    if name in ("ResourceExhausted", "TooManyRequests"):
        return True
    msg = str(exc).lower()
    return any(
        x in msg
        for x in (
            "429",
            "resource exhausted",
            "quota",
            "rate limit",
            "too many requests",
            "exceeded your current quota",
        )
    )


def _extract_text_legacy(response: object) -> str:
    text = getattr(response, "text", None) or ""
    if not text.strip() and getattr(response, "candidates", None):
        try:
            parts = response.candidates[0].content.parts
            text = "".join(getattr(p, "text", "") or "" for p in parts)
        except Exception:
            text = ""
    return text


def _try_import_new_sdk() -> bool:
    global _USE_NEW_SDK
    if _USE_NEW_SDK is not None:
        return _USE_NEW_SDK
    try:
        from google import genai  # noqa: F401, PLC0415
        from google.genai import types  # noqa: F401, PLC0415

        _USE_NEW_SDK = True
    except ImportError:
        _USE_NEW_SDK = False
    return _USE_NEW_SDK


def _generate_once_new_sdk(
    *,
    key: str,
    mname: str,
    system_instruction: str,
    user_content: str,
    json_mode: bool,
    temperature: float,
) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=key)
    cfg_kw: dict = {
        "system_instruction": system_instruction,
        "temperature": 0 if json_mode else temperature,
    }
    if json_mode:
        cfg_kw["response_mime_type"] = "application/json"
    config = types.GenerateContentConfig(**cfg_kw)
    response = client.models.generate_content(
        model=mname,
        contents=user_content,
        config=config,
    )
    text = getattr(response, "text", None) or ""
    if not text and response is not None:
        # 部分版本结构不同
        try:
            c = response.candidates[0].content.parts
            text = "".join(getattr(p, "text", "") or "" for p in c)
        except Exception:
            text = ""
    return text


def _generate_once_legacy_sdk(
    *,
    key: str,
    mname: str,
    system_instruction: str,
    user_content: str,
    json_mode: bool,
    temperature: float,
) -> str:
    import google.generativeai as genai

    genai.configure(api_key=key)
    if json_mode:
        gen_cfg = genai.GenerationConfig(
            temperature=0,
            response_mime_type="application/json",
        )
    else:
        gen_cfg = genai.GenerationConfig(temperature=temperature)
    model = genai.GenerativeModel(
        model_name=mname,
        system_instruction=system_instruction,
        generation_config=gen_cfg,
    )
    response = model.generate_content(user_content)
    return _extract_text_legacy(response)


def gemini_generate(
    *,
    system_instruction: str,
    user_content: str,
    json_mode: bool,
    temperature: float = 0.2,
    model_name: str | None = None,
) -> str:
    """统一 Gemini 调用（新 SDK 优先），带 429 重试。"""
    load_dotenv_from_repo_root(override=True)
    key = gemini_api_key()
    if not key:
        raise ValueError("缺少 GEMINI_API_KEY 或 GOOGLE_API_KEY")

    mname = (model_name or resolved_gemini_model()).strip()
    max_retries = max(1, int(os.environ.get("GEMINI_MAX_RETRIES", "8")))

    use_new = _try_import_new_sdk()
    for attempt in range(max_retries):
        try:
            if use_new:
                return _generate_once_new_sdk(
                    key=key,
                    mname=mname,
                    system_instruction=system_instruction,
                    user_content=user_content,
                    json_mode=json_mode,
                    temperature=temperature,
                )
            return _generate_once_legacy_sdk(
                key=key,
                mname=mname,
                system_instruction=system_instruction,
                user_content=user_content,
                json_mode=json_mode,
                temperature=temperature,
            )
        except Exception as e:
            if not _is_quota_or_rate_limit(e) or attempt == max_retries - 1:
                raise
            time.sleep(_retry_delay_seconds(e, attempt))
    raise RuntimeError("gemini_generate: retry loop ended without return")


def gemini_generate_json(system: str, user: str, *, model_name: str | None = None) -> str:
    t = gemini_generate(
        system_instruction=system,
        user_content=user,
        json_mode=True,
        model_name=model_name,
    )
    return t or "{}"


def gemini_generate_text(
    system: str,
    user: str,
    *,
    temperature: float = 0.2,
    model_name: str | None = None,
) -> str:
    return gemini_generate(
        system_instruction=system,
        user_content=user,
        json_mode=False,
        temperature=temperature,
        model_name=model_name,
    )
