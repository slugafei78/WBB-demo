"""
简单 PE 估值的**可复用**数学片段：宏观利率 → PE 带，以及定性分数乘积 → PE 乘子。

业务规则会迭代时，优先改调用方传入的参数或 JSON 配置，而非硬改公式本身；
若公式变更，请在本模块 docstring 中补一句变更说明与日期。
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def pe_from_deposit_rate_linear(
    rate_pct: float,
    *,
    rate_hist_min: float,
    rate_hist_max: float,
    pe_when_rates_low: float = 22.0,
    pe_when_rates_high: float = 18.0,
) -> float:
    """
    存款利率（年化 %）与目标 PE 的**反向**线性映射：利率越高，估值倍数越低。

    在 ``[rate_hist_min, rate_hist_max]`` 上线性插值：
    - 利率处于历史区间**低端**时 → ``pe_when_rates_low``（默认 22，接近基准 20 的 +10%）；
    - 利率处于历史区间**高端**时 → ``pe_when_rates_high``（默认 18，约 -10%）。

    参数名中的 low/high 指**利率水平**，不是 PE 大小；PE 与利率单调递减。
    """
    if rate_hist_max <= rate_hist_min:
        return float(pe_when_rates_low + pe_when_rates_high) / 2.0
    t = (float(rate_pct) - float(rate_hist_min)) / (float(rate_hist_max) - float(rate_hist_min))
    t = max(0.0, min(1.0, t))
    return float(pe_when_rates_low + t * (pe_when_rates_high - pe_when_rates_low))


def qualitative_pe_multiplier_from_scores(
    scores: Sequence[float],
    *,
    score_floor: float = 1.0,
    score_cap: float = 10.0,
    mult_min: float = 0.5,
    mult_max: float = 1.2,
) -> float:
    """
    将 N 个定性分（默认 1–10）的**乘积**压缩为 PE 乘子，落在 ``[mult_min, mult_max]``。

    使用 ``sum(log10(s_i)) / (N * log10(score_cap))`` 作为 [0,1] 上的归一化位置：
    - 全为 ``score_floor``（默认 1）→ 乘子 ``mult_min``（相对基准 PE 约 -50%，若基准为 20 则约 PE 10）；
    - 全为 ``score_cap``（默认 10）→ 乘子 ``mult_max``（相对基准约 +20%，若基准为 20 则约 PE 24）。

    各分先裁剪到 ``[score_floor, score_cap]``，避免出现 0 或负数导致 log 无效。
    """
    if not scores:
        return float(mult_min + mult_max) / 2.0
    capped = [max(float(score_floor), min(float(score_cap), float(x))) for x in scores]
    log_sum = sum(math.log10(s) for s in capped)
    n = len(capped)
    denom = n * math.log10(float(score_cap))
    if denom <= 0:
        return float(mult_min + mult_max) / 2.0
    t = log_sum / denom
    t = max(0.0, min(1.0, t))
    return float(mult_min + t * (float(mult_max) - float(mult_min)))


def apply_pe_global_cap_floor(pe: float, *, pe_floor: float, pe_cap: float) -> float:
    """定性调整后再做一次绝对上下限裁剪（默认对应 PE 10～24 的讨论区间）。"""
    return max(float(pe_floor), min(float(pe_cap), float(pe)))
