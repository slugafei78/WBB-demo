"""
将 `data/macro/raw/` 下自下载的宏观 CSV（宽表：国家×指标×年份列）转换为
`factors/macro/series/` 下的**季度**时间序列（每季一行 `period_end`, `value`）。

默认适配 World Bank「Macro-indicators.csv」样式：列名形如 `2005 [YR2005]`。
年度指标在四个季度末**重复同一数值**（`repeat_annual_value`），便于与季报对齐。

  python -m value_investment_agent.ingestion.macro_raw_to_factors

配置：`config/macro_raw_to_factors.json`
"""

from __future__ import annotations

import argparse
import io
import json
import re
from pathlib import Path

import pandas as pd

_YEAR_COL = re.compile(r"^(\d{4})\s+\[YR\d{4}\]$")

# Windows / Excel 导出的 CSV 常为 GBK；World Bank 英文版多为 UTF-8
_CSV_ENCODINGS = ("utf-8-sig", "utf-8", "gbk", "cp936", "gb18030", "latin-1")


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _config() -> dict:
    p = repo_root() / "config" / "macro_raw_to_factors.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _read_csv_flexible(path: Path, *, encoding: str | None = None) -> tuple[pd.DataFrame, str]:
    """尝试多种编码读取 CSV（避免 GBK 文件用 UTF-8 解码失败）。"""
    blob = path.read_bytes()
    encodings = (encoding,) if encoding else _CSV_ENCODINGS
    last: Exception | None = None
    for enc in encodings:
        try:
            text = blob.decode(enc)
            df = pd.read_csv(io.StringIO(text))
            return df, enc
        except (UnicodeDecodeError, UnicodeError) as e:
            last = e
            continue
        except Exception as e:
            last = e
            continue
    raise ValueError(f"无法解码或解析 CSV: {path} ({last})") from last


def _read_text_flexible(path: Path, *, encoding: str | None = None) -> tuple[str, str]:
    blob = path.read_bytes()
    encodings = (encoding,) if encoding else _CSV_ENCODINGS
    last: Exception | None = None
    for enc in encodings:
        try:
            return blob.decode(enc), enc
        except (UnicodeDecodeError, UnicodeError) as e:
            last = e
            continue
    raise ValueError(f"无法解码文本: {path} ({last})") from last


def _parse_year_columns(columns: list[str]) -> list[tuple[str, int]]:
    """返回 (原始列名, 年份 int)。"""
    out: list[tuple[str, int]] = []
    for c in columns:
        m = _YEAR_COL.match(str(c).strip())
        if m:
            out.append((c, int(m.group(1))))
    return out


def _annual_to_quarterly_repeat(
    year: int,
    value: float,
) -> list[dict[str, object]]:
    """一年四个季度末，同一数值。"""
    ends = [
        f"{year:04d}-03-31",
        f"{year:04d}-06-30",
        f"{year:04d}-09-30",
        f"{year:04d}-12-31",
    ]
    return [{"period_end": pd.Timestamp(d), "value": value} for d in ends]


def _parse_cell(v: object) -> float | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip()
    if s in ("", "..", "…"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _safe_stem(country_code: str, series_code: str) -> str:
    cc = str(country_code).strip().upper()
    sc = str(series_code).strip().replace(".", "_")
    return f"macro_{cc}_{sc}"


def load_indicator_catalog(metadata_path: Path, *, encoding: str | None = None) -> pd.DataFrame | None:
    """解析带「说明表」的 Metadata CSV（从首个 Code, 开头的行起读；字段内可含换行）。"""
    if not metadata_path.exists():
        return None
    text, enc_used = _read_text_flexible(metadata_path, encoding=encoding)
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith("Code,"):
            start = i
            break
    if start is None:
        return None
    try:
        return pd.read_csv(io.StringIO("\n".join(lines[start:])))
    except Exception:
        return None


def convert(
    *,
    data_csv: Path | None = None,
    metadata_csv: Path | None = None,
    output_dir: Path | None = None,
    quarterly_mode: str = "repeat_annual_value",
) -> dict[str, object]:
    cfg = _config()
    root = repo_root()
    data_csv = root / (data_csv or cfg["input_data_csv"])
    metadata_csv = root / (metadata_csv or cfg.get("input_metadata_csv") or "")
    output_dir = root / (output_dir or cfg["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    enc_override = cfg.get("input_encoding")  # 可选：强制 "gbk" 等
    df, enc_data = _read_csv_flexible(data_csv, encoding=enc_override)
    year_cols = _parse_year_columns(list(df.columns))
    if not year_cols:
        raise ValueError("未识别到年份列（期望形如 2005 [YR2005]）")

    meta_df = (
        load_indicator_catalog(metadata_csv, encoding=enc_override)
        if metadata_csv.exists()
        else None
    )
    catalog: dict[str, dict[str, str]] = {}
    if meta_df is not None and "Code" in meta_df.columns:
        for _, r in meta_df.iterrows():
            code = str(r.get("Code", "")).strip()
            if not code or code == "nan":
                continue
            catalog[code] = {
                "indicator_name": str(r.get("Indicator Name", "")),
                "unit": str(r.get("Unit of measure", "")),
                "periodicity": str(r.get("Periodicity", "")),
                "long_definition": (str(r.get("Long definition", ""))[:500] if pd.notna(r.get("Long definition")) else ""),
            }

    written: list[str] = []
    skipped: list[str] = []

    for _, row in df.iterrows():
        cc = row.get("Country Code")
        sc = row.get("Series Code")
        if pd.isna(cc) or pd.isna(sc) or str(cc).strip() == "" or str(sc).strip() == "":
            continue
        cc_s, sc_s = str(cc).strip(), str(sc).strip()

        rows_q: list[dict[str, object]] = []
        for col_name, year in year_cols:
            val = _parse_cell(row.get(col_name))
            if val is None:
                continue
            if quarterly_mode == "repeat_annual_value":
                rows_q.extend(_annual_to_quarterly_repeat(year, val))
            else:
                raise ValueError(f"未知 quarterly_mode: {quarterly_mode}")

        if not rows_q:
            skipped.append(f"{cc_s}/{sc_s} (无有效年度值)")
            continue

        out = pd.DataFrame(rows_q)
        out = out.sort_values("period_end").drop_duplicates(subset=["period_end"], keep="last")
        stem = _safe_stem(cc_s, sc_s)
        out_path = output_dir / f"{stem}.csv"
        out.to_csv(out_path, index=False, encoding="utf-8-sig")
        written.append(stem)

        side = {
            "country_code": cc_s,
            "country_name": str(row.get("Country Name", "")),
            "series_code": sc_s,
            "series_name": str(row.get("Series Name", "")),
            "source_file": str(data_csv.relative_to(root)),
            "quarterly_mode": quarterly_mode,
            "catalog": catalog.get(sc_s),
        }
        (output_dir / f"{stem}.meta.json").write_text(
            json.dumps(side, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    catalog_out = output_dir / "macro_indicator_catalog.json"
    catalog_out.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {
        "output_dir": str(output_dir.relative_to(root)),
        "encoding_used_data_csv": enc_data,
        "series_written": len(written),
        "stems": sorted(set(written)),
        "skipped": skipped,
        "indicator_catalog_codes": len(catalog),
    }
    (output_dir / "run_convert_meta.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    return summary


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="data/macro/raw → factors/macro/series (quarterly)")
    p.add_argument("--data-csv", type=Path, default=None)
    p.add_argument("--output-dir", type=Path, default=None)
    args = p.parse_args(argv)
    try:
        s = convert(data_csv=args.data_csv, output_dir=args.output_dir)
        print(json.dumps(s, ensure_ascii=False, indent=2))
    except Exception as e:
        raise SystemExit(f"macro_raw_to_factors failed: {e}") from e


if __name__ == "__main__":
    main()
