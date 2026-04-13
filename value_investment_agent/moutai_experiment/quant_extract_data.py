"""
moutai 定量长表：多数据源合并（本地 CSV 优先，其次可选 akshare，再次 Yahoo）。

说明：yfinance 对 600519.SS 等 A 股季报往往只返回最近约 4 个季度列，无法单独满足「完整约 5 年」；
若需与 PDF 一致，请使用 data/moutai/raw/financials/ 下本地表（见 factors/moutai/config/quant_extract.json）。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

import pandas as pd
import yfinance as yf

from value_investment_agent.config.symbols import SYMBOL_MOUTAI, yahoo_ticker

# 数字越小优先级越高（同 period、同 factor_id 时保留一条）
SOURCE_PRIORITY: dict[str, int] = {
    "manual_quarterly_csv": 0,
    "net_profit_quarterly_csv": 1,
    "eastmoney_quarterly": 2,
    "akshare": 3,
    "yahoo_quarterly": 5,
    "yahoo_quarterly_proxy": 6,
}


def _prio(source: str) -> int:
    return SOURCE_PRIORITY.get(source, 99)


def _find_row(df: pd.DataFrame, needles: list[str]) -> pd.Series | None:
    if df is None or df.empty:
        return None
    idx = [str(x).lower() for x in df.index.astype(str)]
    for needle in needles:
        nd = needle.lower()
        for i, name in enumerate(idx):
            if nd in name:
                return df.iloc[i]
    return None


def _col_series_to_quarterly(row: pd.Series) -> pd.Series:
    s = pd.Series(dtype=float)
    for c in row.index:
        try:
            ts = pd.Timestamp(c)
            s[ts.normalize()] = float(row[c])
        except Exception:
            continue
    return s.sort_index()


def _yahoo_quarterly_bundle(t: yf.Ticker) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    inc = t.quarterly_income_stmt
    if inc is None or inc.empty:
        inc = t.quarterly_financials
    bs = t.quarterly_balance_sheet
    cf = t.quarterly_cashflow
    if inc is None:
        inc = pd.DataFrame()
    if bs is None:
        bs = pd.DataFrame()
    if cf is None:
        cf = pd.DataFrame()
    return inc, bs, cf


def rows_from_yahoo(
    *,
    symbol: str = SYMBOL_MOUTAI,
    cutoff: pd.Timestamp,
) -> tuple[list[dict[str, object]], dict[str, str]]:
    """从 Yahoo 季报抽取行（列数通常很少，仅作补充）。"""
    t = yf.Ticker(yahoo_ticker(symbol))
    inc, bs, cf = _yahoo_quarterly_bundle(t)
    notes: dict[str, str] = {
        "net_income": "quarterly_income_stmt Net Income 类行",
        "net_profit_attributable": "与 net_income 同源行（Yahoo 口径）",
        "gross_profit": "Gross Profit / 毛利类行",
        "operating_profit": "Operating Income / EBIT 类行",
        "debt_to_equity": "Total Debt / Total Stockholder Equity",
        "free_cash_flow": "Operating Cash Flow - |CapEx| 近似",
        "capex": "Capital Expenditure / PPE 等（绝对值）",
    }

    ni = _find_row(
        inc,
        [
            "net income",
            "net income common",
            "net income attributable",
            "净利润",
        ],
    )
    gp = _find_row(
        inc,
        [
            "gross profit",
            "gross income",
            "毛利",
        ],
    )
    op = _find_row(
        inc,
        [
            "operating income",
            "income from operations",
            "operating earnings",
            "ebit",
            "营业利润",
        ],
    )
    td = _find_row(bs, ["total debt"])
    if td is None:
        td = _find_row(bs, ["long term debt"])
    eq = _find_row(bs, ["stockholders equity", "total stockholder equity", "total equity"])
    ocf = _find_row(
        cf,
        [
            "operating cash flow",
            "cash from operations",
            "cash flow from operations",
            "net cash provided by operating",
        ],
    )
    capex_row = _find_row(
        cf,
        [
            "capital expenditure",
            "purchase of ppe",
            "purchase of property",
            "purchases of property",
            "investments in property",
        ],
    )

    rows: list[dict[str, object]] = []

    def add_factor(fid: str, s: pd.Series | None, transform: Callable[[float], float] | None = None) -> None:
        if s is None or s.empty:
            return
        qs = _col_series_to_quarterly(s)
        for dt, v in qs.items():
            if dt < cutoff:
                continue
            val = float(v)
            if transform:
                val = transform(val)
            if val != val:
                continue
            rows.append(
                {
                    "period_end": dt.strftime("%Y-%m-%d"),
                    "factor_id": fid,
                    "value": val,
                    "source": "yahoo_quarterly",
                }
            )

    add_factor("net_income", ni)
    add_factor("net_profit_attributable", ni)
    add_factor("gross_profit", gp)
    add_factor("operating_profit", op)

    if td is not None and eq is not None:
        tds = _col_series_to_quarterly(td)
        eqs = _col_series_to_quarterly(eq)
        for dt in tds.index.union(eqs.index):
            if dt < cutoff:
                continue
            if dt not in tds.index or dt not in eqs.index:
                continue
            d, e = float(tds[dt]), float(eqs[dt])
            if e == 0:
                continue
            rows.append(
                {
                    "period_end": dt.strftime("%Y-%m-%d"),
                    "factor_id": "debt_to_equity",
                    "value": d / e,
                    "source": "yahoo_quarterly",
                }
            )

    if ocf is not None and capex_row is not None:
        oc = _col_series_to_quarterly(ocf)
        cx = _col_series_to_quarterly(capex_row)
        for dt in oc.index.union(cx.index):
            if dt < cutoff:
                continue
            if dt not in oc.index:
                continue
            o = float(oc[dt])
            c = float(cx[dt]) if dt in cx.index else 0.0
            capex_abs = abs(c)
            rows.append(
                {
                    "period_end": dt.strftime("%Y-%m-%d"),
                    "factor_id": "free_cash_flow",
                    "value": o - capex_abs,
                    "source": "yahoo_quarterly_proxy",
                }
            )
            rows.append(
                {
                    "period_end": dt.strftime("%Y-%m-%d"),
                    "factor_id": "capex",
                    "value": capex_abs,
                    "source": "yahoo_quarterly",
                }
            )

    return rows, notes


def _norm_header(c: str) -> str:
    return re.sub(r"\s+", "_", str(c).strip().lower())


def rows_from_net_profit_csv(path: Path, cutoff: pd.Timestamp) -> list[dict[str, object]]:
    if not path.exists():
        return []
    df = pd.read_csv(path, encoding="utf-8")
    if "period_end" not in df.columns or "net_profit" not in df.columns:
        return []
    df["period_end"] = pd.to_datetime(df["period_end"], errors="coerce")
    df = df.dropna(subset=["period_end"])
    df = df[df["period_end"] >= cutoff]
    rows: list[dict[str, object]] = []
    for _, r in df.iterrows():
        try:
            v = float(r["net_profit"])
        except Exception:
            continue
        if v != v:
            continue
        rows.append(
            {
                "period_end": pd.Timestamp(r["period_end"]).strftime("%Y-%m-%d"),
                "factor_id": "net_profit_attributable",
                "value": v,
                "source": "net_profit_quarterly_csv",
            }
        )
    return rows


# manual 宽表：列名（归一化后）→ factor_id
_MANUAL_COL_MAP: dict[str, str] = {
    "net_income": "net_income",
    "net_profit_attributable": "net_profit_attributable",
    "net_profit": "net_profit_attributable",
    "gross_profit": "gross_profit",
    "operating_profit": "operating_profit",
    "operating_income": "operating_profit",
    "capex": "capex",
    "capital_expenditure": "capex",
    "free_cash_flow": "free_cash_flow",
    "fcf": "free_cash_flow",
    "debt_to_equity": "debt_to_equity",
    "debt_equity_ratio": "debt_to_equity",
    "d_e": "debt_to_equity",
}


def rows_from_manual_wide_csv(path: Path, cutoff: pd.Timestamp) -> list[dict[str, object]]:
    """宽表：period_end + 各指标列（英文蛇形列名为主）。"""
    if not path.exists():
        return []
    df = pd.read_csv(path, encoding="utf-8")
    colmap = {_norm_header(c): c for c in df.columns}
    if "period_end" not in colmap:
        return []
    df["period_end"] = pd.to_datetime(df[colmap["period_end"]], errors="coerce")
    df = df.dropna(subset=["period_end"])
    df = df[df["period_end"] >= cutoff]
    rows: list[dict[str, object]] = []
    for _, r in df.iterrows():
        pend = pd.Timestamp(r["period_end"]).strftime("%Y-%m-%d")
        for norm_name, fid in _MANUAL_COL_MAP.items():
            if norm_name not in colmap:
                continue
            raw = r[colmap[norm_name]]
            try:
                v = float(raw)
            except Exception:
                continue
            if v != v:
                continue
            rows.append(
                {
                    "period_end": pend,
                    "factor_id": fid,
                    "value": v,
                    "source": "manual_quarterly_csv",
                }
            )
    return rows


def _parse_sina_report_date(col: str) -> pd.Timestamp | None:
    s = str(col).strip()
    try:
        return pd.Timestamp(s).normalize()
    except Exception:
        pass
    digits = re.sub(r"\D", "", s)
    if len(digits) >= 8:
        try:
            return pd.Timestamp(digits[:8]).normalize()
        except Exception:
            return None
    return None


def _em_match_column(columns: pd.Index, patterns: list[str]) -> str | None:
    """在 DataFrame 列名中找第一个匹配 patterns 的列（不区分大小写）。

    优先匹配较长 pattern，避免 ``NETPROFIT`` 误匹配 ``PARENT_NETPROFIT``。
    """
    cols = [str(c) for c in columns]
    flat = sorted({p.upper() for p in patterns}, key=len, reverse=True)
    for pu in flat:
        for c in cols:
            cu = c.upper()
            if pu == cu or pu in cu:
                return c
    return None


def _em_match_metric_column(columns: pd.Index, patterns: list[str]) -> str | None:
    """匹配财报「金额」列，排除同比/环比 *_QOQ、*_YOY 等派生列。"""
    skip = ("_QOQ", "_YOY", "_TZ", "同比", "环比")
    filtered = [str(c) for c in columns if not any(s in str(c).upper() for s in skip)]
    return _em_match_column(pd.Index(filtered), patterns)


def _em_date_column(df: pd.DataFrame) -> str | None:
    """东财报表常见报告期列名。"""
    for patterns in (
        ["REPORT_DATE", "REPORTDATE"],
        ["END_DATE", "ENDDATE"],
        ["NOTICE_DATE", "ANNOUNCE_DATE"],
        ["报告期", "公告日期", "报表日期"],
    ):
        c = _em_match_column(df.columns, patterns)
        if c is not None:
            return c
    # 启发式：哪一列前 20 行里能解析成日期的最多
    best_c, best_n = None, 0
    for c in df.columns:
        if str(c).upper() in ("SECUCODE", "SECURITY_CODE", "SECURITY_NAME", "SECURITY_NAME_ABBR"):
            continue
        n = 0
        for v in df[c].head(30):
            if _parse_sina_report_date(str(v)) is not None:
                n += 1
        if n > best_n:
            best_n, best_c = n, c
    if best_n >= 3 and best_c is not None:
        return best_c
    return None


def _em_sheet_to_rows(
    df: pd.DataFrame | None,
    kind: str,
    cutoff: pd.Timestamp,
    source_tag: str,
    meta: dict[str, object],
) -> list[dict[str, object]]:
    """单张东财表 → 长表行（不含 FCF 合成）。"""
    out: list[dict[str, object]] = []
    if df is None or df.empty:
        meta[f"{kind}_empty"] = True
        return out
    meta[f"{kind}_shape"] = getattr(df, "shape", None)
    dcol = _em_date_column(df)
    if dcol is None:
        meta[f"{kind}_columns_preview"] = [str(x) for x in df.columns[:40]]
        return out
    meta[f"{kind}_date_col"] = dcol

    has_gross_col = False
    inc_col = cost_col = None
    if kind == "profit":
        pairs = []
        c = _em_match_metric_column(
            df.columns,
            ["PARENT_NETPROFIT", "PARENT_HOLDER_NETPROFIT", "HOLDER_NETPROFIT", "HOLDER_NET_PROFIT"],
        )
        if c:
            pairs.append((c, "net_profit_attributable"))
        for col in df.columns:
            cs = str(col).upper()
            if "_QOQ" in cs or "_YOY" in cs:
                continue
            if "NETPROFIT" not in cs or "PARENT" in cs or "HOLDER" in cs:
                continue
            if c and str(col) == c:
                continue
            pairs.append((str(col), "net_income"))
            break
        for patterns, fid in (
            (["GROSS_PROFIT"], "gross_profit"),
            (["TOTAL_OPERATE_PROFIT", "OPERATE_PROFIT", "OPER_PROFIT"], "operating_profit"),
        ):
            cc = _em_match_metric_column(df.columns, patterns)
            if cc:
                pairs.append((cc, fid))
        has_gross_col = any(fid == "gross_profit" for _, fid in pairs)
        inc_col = _em_match_metric_column(df.columns, ["TOTAL_OPERATE_INCOME", "OPERATE_INCOME"])
        cost_col = _em_match_metric_column(df.columns, ["OPERATE_COST", "TOTAL_OPERATE_COST"])
    elif kind == "cashflow":
        pairs = []
        for patterns, fid in (
            (["NETCASH_OPERATE", "NET_OPERATE_CASH", "OPERATE_NET_CASH", "NETCASHOPERATE"], "operating_cash_flow_raw"),
            (
                [
                    "CONSTRUCT_LONG_ASSET",
                    "CONSTRUCT_FIXED",
                    "PAY_CASH_FIXED",
                    "PAY_CONSTRUCT",
                    "FIXED_ASSET",
                    "CONSTRUCT_LONG",
                    "购建固定资产",
                ],
                "capex",
            ),
        ):
            c = _em_match_metric_column(df.columns, patterns)
            if c:
                pairs.append((c, fid))
        if len(pairs) < 2:
            for col in df.columns:
                cs = str(col).upper()
                if "_QOQ" in cs or "_YOY" in cs:
                    continue
                if "CONSTRUCT" in cs and ("ASSET" in cs or "LONG" in cs) and not any(p[0] == str(col) for p in pairs):
                    pairs.append((str(col), "capex"))
                    break
    else:
        pairs = []

    for _, row in df.iterrows():
        raw = row[dcol]
        ts = _parse_sina_report_date(str(raw))
        if ts is None or ts < cutoff:
            continue
        pend = ts.strftime("%Y-%m-%d")
        for col, fid in pairs:
            try:
                v = float(row[col])
            except Exception:
                continue
            if v != v:
                continue
            out.append(
                {
                    "period_end": pend,
                    "factor_id": fid,
                    "value": v,
                    "source": source_tag,
                }
            )
        # 东财单季利润表常无 GROSS_PROFIT 列：用 营业总收入 − 营业成本 近似毛利润
        if kind == "profit" and not has_gross_col and inc_col and cost_col:
            try:
                gp = float(row[inc_col]) - float(row[cost_col])
                if gp == gp:
                    out.append(
                        {
                            "period_end": pend,
                            "factor_id": "gross_profit",
                            "value": gp,
                            "source": source_tag,
                        }
                    )
            except Exception:
                pass
    return out


def _em_append_fcf_and_drop_raw(rows: list[dict[str, object]], source_tag: str) -> list[dict[str, object]]:
    """OCF − capex → FCF；去掉 operating_cash_flow_raw 中间行。"""
    ocf_by: dict[str, float] = {}
    capex_by: dict[str, float] = {}
    for r in rows:
        if r["factor_id"] == "operating_cash_flow_raw":
            ocf_by[str(r["period_end"])] = float(r["value"])
        elif r["factor_id"] == "capex":
            capex_by[str(r["period_end"])] = abs(float(r["value"]))
    existing_capex_pe = {str(r["period_end"]) for r in rows if r.get("factor_id") == "capex"}
    extra: list[dict[str, object]] = []
    for pe in set(ocf_by) | set(capex_by):
        o = ocf_by.get(pe)
        if o is None:
            continue
        c = capex_by.get(pe)
        cx = abs(c) if c is not None else 0.0
        extra.append(
            {
                "period_end": pe,
                "factor_id": "free_cash_flow",
                "value": o - cx,
                "source": source_tag,
            }
        )
        if c is not None and pe not in existing_capex_pe:
            extra.append(
                {
                    "period_end": pe,
                    "factor_id": "capex",
                    "value": cx,
                    "source": source_tag,
                }
            )
    drop_ids = {"operating_cash_flow_raw"}
    rows = [r for r in rows if r["factor_id"] not in drop_ids]
    rows.extend(extra)
    return rows


def _em_balance_df_to_rows(
    df: pd.DataFrame | None,
    cutoff: pd.Timestamp,
    source_tag: str,
    meta: dict[str, object],
) -> list[dict[str, object]]:
    """资产负债表 → debt_to_equity = 负债合计 / 归属母公司权益（或股东权益合计）。"""
    out: list[dict[str, object]] = []
    if df is None or df.empty:
        meta["balance_empty"] = True
        return out
    meta["balance_shape"] = getattr(df, "shape", None)
    dcol = _em_date_column(df)
    if dcol is None:
        meta["balance_columns_preview"] = [str(x) for x in df.columns[:30]]
        return out
    meta["balance_date_col"] = dcol
    liab_c = _em_match_metric_column(df.columns, ["TOTAL_LIABILITIES", "LIAB_TOTAL", "负债合计"])
    eq_c = _em_match_metric_column(
        df.columns,
        [
            "PARENT_EQUITY",
            "TOTAL_EQUITY_ATTR_P",
            "TOTAL_EQUITY_ATTR_PARENT",
            "SHAREHOLDER_EQUITY",
            "股东权益合计",
            "归属于母公司所有者权益合计",
        ],
    )
    if not liab_c or not eq_c:
        meta["balance_missing_liab_eq"] = {"liab": liab_c, "equity": eq_c}
        return out
    meta["balance_liab_col"], meta["balance_equity_col"] = liab_c, eq_c
    for _, row in df.iterrows():
        raw = row[dcol]
        ts = _parse_sina_report_date(str(raw))
        if ts is None or ts < cutoff:
            continue
        pend = ts.strftime("%Y-%m-%d")
        try:
            liab = float(row[liab_c])
            eq = float(row[eq_c])
        except Exception:
            continue
        if eq == 0 or liab != liab or eq != eq:
            continue
        out.append(
            {
                "period_end": pend,
                "factor_id": "debt_to_equity",
                "value": liab / eq,
                "source": source_tag,
            }
        )
    return out


def rows_from_eastmoney_dataframes(
    *,
    profit_df: pd.DataFrame | None,
    cf_df: pd.DataFrame | None,
    balance_df: pd.DataFrame | None = None,
    cutoff: pd.Timestamp,
    source_tag: str = "eastmoney_quarterly",
    meta: dict[str, object] | None = None,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """由已加载的东财利润表/现金流量表/资产负债表 DataFrame 生成长表行（与下载落地 CSV 再读入等价）。"""
    meta = meta if meta is not None else {}
    rows: list[dict[str, object]] = []
    rows.extend(_em_sheet_to_rows(profit_df, "profit", cutoff, source_tag, meta))
    rows.extend(_em_sheet_to_rows(cf_df, "cashflow", cutoff, source_tag, meta))
    rows.extend(_em_balance_df_to_rows(balance_df, cutoff, source_tag, meta))
    rows = _em_append_fcf_and_drop_raw(rows, source_tag)
    meta["eastmoney_row_count"] = len(rows)
    return rows, meta


def rows_from_eastmoney_csv_paths(
    *,
    profit_csv: Path,
    cashflow_csv: Path,
    cutoff: pd.Timestamp,
    balance_csv: Path | None = None,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """读取已下载到 data/ 下的东财原始 CSV（utf-8-sig）。"""
    meta: dict[str, object] = {
        "load_mode": "data_csv",
        "profit_csv": str(profit_csv),
        "cashflow_csv": str(cashflow_csv),
    }
    if not profit_csv.exists() or not cashflow_csv.exists():
        meta["skipped"] = "missing_csv"
        return [], meta
    profit_df = pd.read_csv(profit_csv, encoding="utf-8-sig")
    cf_df = pd.read_csv(cashflow_csv, encoding="utf-8-sig")
    balance_df = None
    if balance_csv is not None and balance_csv.is_file():
        balance_df = pd.read_csv(balance_csv, encoding="utf-8-sig")
        meta["balance_csv"] = str(balance_csv)
    return rows_from_eastmoney_dataframes(
        profit_df=profit_df,
        cf_df=cf_df,
        balance_df=balance_df,
        cutoff=cutoff,
        source_tag="eastmoney_quarterly",
        meta=meta,
    )


def rows_from_eastmoney_quarterly(
    *,
    em_symbol: str,
    cutoff: pd.Timestamp,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """东方财富-按单季度 API 拉取（原始宽表应先用 download 脚本落盘到 data/）。"""
    meta: dict[str, object] = {"load_mode": "api"}
    try:
        import akshare as ak  # noqa: PLC0415
    except ImportError:
        meta["skipped"] = "akshare_not_installed"
        return [], meta

    profit_df = None
    cf_df = None
    try:
        profit_df = ak.stock_profit_sheet_by_quarterly_em(symbol=em_symbol)
    except Exception as e:  # noqa: BLE001
        meta["profit_em_error"] = str(e)
    try:
        cf_df = ak.stock_cash_flow_sheet_by_quarterly_em(symbol=em_symbol)
    except Exception as e:  # noqa: BLE001
        meta["cashflow_em_error"] = str(e)

    balance_df = None
    try:
        balance_df = ak.stock_balance_sheet_by_report_em(symbol=em_symbol)
    except Exception as e:  # noqa: BLE001
        meta["balance_em_error"] = str(e)

    return rows_from_eastmoney_dataframes(
        profit_df=profit_df,
        cf_df=cf_df,
        balance_df=balance_df,
        cutoff=cutoff,
        source_tag="eastmoney_quarterly",
        meta=meta,
    )


def _akshare_find_metric_row(df: pd.DataFrame, substrings: list[str]) -> pd.Series | None:
    """旧版新浪宽表：指标名可能在首列或行索引上。"""
    if df is None or df.empty:
        return None
    for sub in substrings:
        sub_l = sub.lower()
        for i in range(len(df.index)):
            if sub_l in str(df.index[i]).lower():
                return df.iloc[i]
    first = df.columns[0]
    names = df[first].astype(str)
    for sub in substrings:
        sub_l = sub.lower()
        for i in range(len(df)):
            if sub_l in str(names.iloc[i]).lower():
                return df.iloc[i]
    return None


def _akshare_date_column(df: pd.DataFrame) -> str | None:
    """新版新浪：每行一个报告期，存在「报表日期」类列；否则启发式找日期列。"""
    for c in df.columns:
        cs = str(c).strip()
        if any(
            k in cs
            for k in (
                "报表日期",
                "报告期",
                "报告日",
                "截止日期",
                "日期",
                "报告日期",
            )
        ):
            return str(c)
    best_c, best_n = None, 0
    for c in df.columns:
        n = sum(
            1
            for v in df[c].head(40)
            if _parse_sina_report_date(str(v)) is not None
        )
        if n > best_n:
            best_n, best_c = n, c
    if best_n >= 3 and best_c is not None:
        return str(best_c)
    return None


def _akshare_cell(row: pd.Series, col: str | int) -> object:
    v = row[col]
    if isinstance(v, pd.Series):
        return v.iloc[0]
    return v


def _factor_from_profit_colname(name: str) -> str | None:
    """利润表列名 → factor_id（绝对额；跳过纯比率列）。"""
    s = str(name).strip()
    if s.endswith("率") or "同比增长" in s or "同比" in s:
        return None
    if "归属于母公司" in s and "净利润" in s:
        return "net_profit_attributable"
    if s == "净利润":
        return "net_income"
    if "营业利润" in s:
        return "operating_profit"
    if "毛利润" in s or "营业毛利" in s:
        return "gross_profit"
    return None


def _factor_from_cashflow_colname(name: str) -> str | None:
    s = str(name).strip()
    if "经营活动" in s and "现金流量" in s and "净额" in s:
        return "operating_cash_flow_raw"
    if "经营活动产生的现金流量净额" in s:
        return "operating_cash_flow_raw"
    if "购建固定资产" in s or "购建固定资产、无形资产" in s:
        return "capex"
    return None


def _factor_from_balance_colname(name: str) -> str | None:
    s = str(name).strip()
    if s == "负债合计":
        return "total_liabilities_raw"
    if "所有者权益" in s and "合计" in s and "少数" not in s:
        return "equity_raw"
    if s in ("股东权益合计", "归属于母公司所有者权益合计"):
        return "equity_raw"
    return None


def _rows_from_sina_df_rowwise(
    df: pd.DataFrame,
    cutoff: pd.Timestamp,
    sheet_kind: str,
) -> list[dict[str, object]]:
    """每行=一个报告期，列名=指标（akshare 当前主流格式）。"""
    date_col = _akshare_date_column(df)
    if date_col is None:
        return []
    rows: list[dict[str, object]] = []
    for _, row in df.iterrows():
        raw = _akshare_cell(row, date_col)
        ts = _parse_sina_report_date(str(raw))
        if ts is None or ts < cutoff:
            continue
        pend = ts.strftime("%Y-%m-%d")
        for col in df.columns:
            if str(col) == date_col:
                continue
            cs = str(col).strip()
            if cs in ("单位", "币种", "类型"):
                continue
            fid: str | None = None
            if sheet_kind == "利润表":
                fid = _factor_from_profit_colname(cs)
            elif sheet_kind == "现金流量表":
                fid = _factor_from_cashflow_colname(cs)
            elif sheet_kind == "资产负债表":
                fid = _factor_from_balance_colname(cs)
            if fid is None:
                continue
            try:
                v = float(_akshare_cell(row, col))
            except Exception:
                continue
            if v != v:
                continue
            rows.append(
                {
                    "period_end": pend,
                    "factor_id": fid,
                    "value": v,
                    "source": "akshare",
                }
            )
    return rows


def _rows_from_sina_df_colwise(
    df: pd.DataFrame,
    cutoff: pd.Timestamp,
    mapping: list[tuple[list[str], str]],
) -> list[dict[str, object]]:
    """每行=指标、列=报告期（旧版宽表）。遍历所有列名，能解析成日期的列视为报告期。"""
    rows: list[dict[str, object]] = []
    for col in df.columns:
        ts = _parse_sina_report_date(str(col))
        if ts is None or ts < cutoff:
            continue
        pend = ts.strftime("%Y-%m-%d")
        for needles, fid in mapping:
            mrow = _akshare_find_metric_row(df, needles)
            if mrow is None:
                continue
            try:
                v = float(mrow[col])
            except Exception:
                continue
            if v != v:
                continue
            rows.append(
                {
                    "period_end": pend,
                    "factor_id": fid,
                    "value": v,
                    "source": "akshare",
                }
            )
    return rows


def rows_from_akshare_sina(
    *,
    stock_code: str,
    cutoff: pd.Timestamp,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """新浪财经三大表（需安装 akshare）。

    akshare 返回多为「每行一个报告期、列名为科目」；旧实现误当作「列=日期」导致 0 行。
    """
    meta: dict[str, object] = {}
    try:
        import akshare as ak  # noqa: PLC0415
    except ImportError:
        meta["skipped"] = "akshare_not_installed"
        return [], meta

    rows: list[dict[str, object]] = []

    def load_sheet(symbol_name: str, sheet_kind: str, legacy_mapping: list[tuple[list[str], str]]) -> None:
        try:
            df = ak.stock_financial_report_sina(stock=stock_code, symbol=symbol_name)
        except Exception as e:  # noqa: BLE001
            meta[f"{symbol_name}_error"] = str(e)
            return
        if df is None or df.empty:
            meta[f"{symbol_name}_empty"] = True
            return
        meta[f"{symbol_name}_shape"] = getattr(df, "shape", None)
        rw = _rows_from_sina_df_rowwise(df, cutoff, sheet_kind)
        if rw:
            meta[f"{symbol_name}_parse"] = "row_per_period"
            rows.extend(rw)
            return
        cw = _rows_from_sina_df_colwise(df, cutoff, legacy_mapping)
        meta[f"{symbol_name}_parse"] = "col_per_period_legacy"
        rows.extend(cw)

    legacy_profit = [
        (["归属于母公司所有者的净利润"], "net_profit_attributable"),
        (["归属于母公司股东的净利润"], "net_profit_attributable"),
        (["营业利润"], "operating_profit"),
        (["毛利润", "营业毛利"], "gross_profit"),
    ]
    legacy_cf = [
        (["经营活动产生的现金流量净额", "经营活动产生的现金流量"], "operating_cash_flow_raw"),
        (["购建固定资产", "购建固定资产、无形资产和其他长期资产"], "capex"),
    ]
    legacy_bs = [
        (["负债合计"], "total_liabilities_raw"),
        (["归属于母公司所有者权益合计", "所有者权益合计", "股东权益合计"], "equity_raw"),
    ]

    load_sheet("利润表", "利润表", legacy_profit)
    load_sheet("现金流量表", "现金流量表", legacy_cf)
    load_sheet("资产负债表", "资产负债表", legacy_bs)

    # 由 OCF 与 capex 推导 FCF
    ocf_by: dict[str, float] = {}
    capex_by: dict[str, float] = {}
    for r in rows:
        if r["factor_id"] == "operating_cash_flow_raw":
            ocf_by[str(r["period_end"])] = float(r["value"])
        elif r["factor_id"] == "capex":
            capex_by[str(r["period_end"])] = abs(float(r["value"]))
    existing_capex_pe = {str(r["period_end"]) for r in rows if r.get("factor_id") == "capex"}
    extra: list[dict[str, object]] = []
    for pe in set(ocf_by) | set(capex_by):
        o = ocf_by.get(pe)
        c = capex_by.get(pe)
        if o is None:
            continue
        cx = c if c is not None else 0.0
        extra.append(
            {
                "period_end": pe,
                "factor_id": "free_cash_flow",
                "value": o - cx,
                "source": "akshare",
            }
        )
        if c is not None and pe not in existing_capex_pe:
            extra.append(
                {
                    "period_end": pe,
                    "factor_id": "capex",
                    "value": cx,
                    "source": "akshare",
                }
            )

    liq: dict[str, float] = {}
    eq: dict[str, float] = {}
    for r in rows:
        if r["factor_id"] == "total_liabilities_raw":
            liq[str(r["period_end"])] = float(r["value"])
        elif r["factor_id"] == "equity_raw":
            eq[str(r["period_end"])] = float(r["value"])
    de_rows: list[dict[str, object]] = []
    for pe in set(liq) & set(eq):
        e = eq[pe]
        if e == 0:
            continue
        de_rows.append(
            {
                "period_end": pe,
                "factor_id": "debt_to_equity",
                "value": liq[pe] / e,
                "source": "akshare",
            }
        )

    drop_ids = {"operating_cash_flow_raw", "total_liabilities_raw", "equity_raw"}
    rows = [r for r in rows if r["factor_id"] not in drop_ids]
    rows.extend(extra)
    rows.extend(de_rows)
    meta["akshare_row_count"] = len(rows)

    return rows, meta


def merge_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """同 (period_end, factor_id) 保留优先级最高的一条。"""
    best: dict[tuple[str, str], tuple[dict[str, object], int]] = {}
    for r in rows:
        key = (str(r["period_end"]), str(r["factor_id"]))
        p = _prio(str(r["source"]))
        if key not in best or p < best[key][1]:
            best[key] = (r, p)
    out = [t[0] for t in best.values()]
    out.sort(key=lambda x: (x["period_end"], x["factor_id"]))  # type: ignore[arg-type, return-value]
    return out


def rows_to_dataframe(rows: list[dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(rows)
