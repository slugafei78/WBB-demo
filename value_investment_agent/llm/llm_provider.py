"""Resolve which LLM backend to use (Gemini preferred when keys are set)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

LLMProvider = Literal["auto", "gemini", "openai", "mock"]


def repo_root_from_here() -> Path:
    """本文件位于 value_investment_agent/llm/，仓库根为其上三级。"""
    return Path(__file__).resolve().parent.parent.parent


def _dotenv_candidate_paths() -> list[Path]:
    """返回待尝试的环境文件路径（按顺序）。

    除 ``.env`` 外也尝试 ``.env.txt``（Windows 记事本常保存成此扩展名，资源管理器仍显示为「.env」）。
    """
    out: list[Path] = []
    seen: set[str] = set()

    def add(p: Path) -> None:
        try:
            key = str(p.resolve())
        except OSError:
            key = str(p)
        if key not in seen:
            seen.add(key)
            out.append(p)

    dotenv_path = (os.environ.get("DOTENV_PATH") or "").strip()
    if dotenv_path:
        add(Path(dotenv_path).expanduser())

    cur = Path.cwd().resolve()
    for _ in range(16):
        add(cur / ".env")
        add(cur / ".env.txt")
        nxt = cur.parent
        if nxt == cur:
            break
        cur = nxt

    pkg = repo_root_from_here()
    add(pkg / ".env")
    add(pkg / ".env.txt")
    return out


def load_dotenv_from_repo_root(*, override: bool = True) -> None:
    """加载第一个存在的 ``.env`` / ``.env.txt`` 文件（见 `_dotenv_candidate_paths`）。"""
    for p in _dotenv_candidate_paths():
        if not p.is_file():
            continue
        try:
            from dotenv import load_dotenv as _ld  # noqa: PLC0415

            _ld(p, override=override)
        except ImportError:
            _parse_env_file(p, override=override)
        return


def _parse_env_file(path: Path, *, override: bool) -> None:
    raw = path.read_text(encoding="utf-8-sig")
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if not k:
            continue
        if not override and k in os.environ and os.environ.get(k):
            continue
        if v or override:
            os.environ[k] = v


# 导入时加载（cwd 向上查找，兼容非 editable 安装）
load_dotenv_from_repo_root(override=True)


def gemini_api_key() -> str | None:
    k = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not k:
        return None
    k = str(k).strip()
    return k or None


def dotenv_load_hint_for_error() -> str:
    """供报错时打印：已尝试的路径。"""
    paths = _dotenv_candidate_paths()
    parts = [str(p) for p in paths[:10]]
    extra = len(paths) > 10
    msg = (
        "尝试过的 .env / .env.txt 路径（节选）:\n  "
        + "\n  ".join(parts)
        + "\n\n若使用记事本保存，文件名可能是 `.env.txt` 而非 `.env`，现已同时支持。"
    )
    if extra:
        msg += "\n  …（路径较多已省略）"
    return msg


def resolve_llm_provider(explicit: LLMProvider) -> Literal["gemini", "openai", "mock"]:
    if explicit == "mock":
        return "mock"
    if explicit == "gemini":
        return "gemini"
    if explicit == "openai":
        return "openai"
    if gemini_api_key():
        return "gemini"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    return "mock"
