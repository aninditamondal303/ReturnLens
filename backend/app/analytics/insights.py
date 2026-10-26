"""
Data-driven business insights. Every sentence is built from calculated values for the
CURRENT filter selection; rules that do not apply (too little data, no signal) are
skipped, so an insight never contradicts the numbers on screen.
"""
from __future__ import annotations

import pandas as pd

from . import config
from .metrics import aggregate, safe_div
from .scenario import preset_params, simulate


def _inr(v: float) -> str:
    """Indian-style compact currency (L = lakh, Cr = crore)."""
    a = abs(v)
    sign = "-" if v < 0 else ""
    if a >= 1e7:
        return f"{sign}INR {a / 1e7:.2f} Cr"
    if a >= 1e5:
        return f"{sign}INR {a / 1e5:.1f} L"
    return f"{sign}INR {a:,.0f}"


def generate(lines: pd.DataFrame, summary: dict, months: int) -> list[dict]:
    out: list[dict] = []
    if lines.empty or not summary.get("units"):
        return out
    target = config.RETURN_RATE_TARGET
    cats = aggregate(lines, "category")
    cats = cats[cats["units"] > 0]

    # 1. categories above the illustrative target
    above = cats[cats["unit_return_rate"] > target].sort_values("return_leakage", ascending=False)
    if len(above):
        top = above.iloc[0]
        out.append({
            "id": "category_above_target", "tone": "risk",
            "title": f"{len(above)} of {len(cats)} categories exceed the {target:.0%} example target",
            "detail": (f"{top['category']} leaks the most: {top['unit_return_rate']:.1%} unit return rate and "
                       f"{_inr(top['return_leakage'])} of return profit leakage."),
            "metric": "unit_return_rate",
        })

    # 2. leakage concentration
    total_leak = float(cats["return_leakage"].sum())
    if total_leak > 0 and len(cats) >= 3:
        top2 = cats.sort_values("return_leakage", ascending=False).head(2)
        share = float(top2["return_leakage"].sum()) / total_leak
        gmv_share = float(top2["gmv"].sum()) / float(cats["gmv"].sum())
        if share > gmv_share * 1.15:
            out.append({
                "id": "leakage_concentration", "tone": "risk",
                "title": f"Two categories cause {share:.0%} of return leakage",
                "detail": (f"{' and '.join(top2['category'])} generate {gmv_share:.0%} of GMV but {share:.0%} "
                           f"of the {_inr(total_leak)} contribution lost to returns."),
                "metric": "return_leakage",
            })

    # 3. region disproportionate reverse logistics
    reg = aggregate(lines, "shipping_region")
    reg = reg[reg["gmv"] > 0]
    rl_total = float(reg["reverse_logistics"].sum())
    if rl_total > 0 and len(reg) >= 3:
        reg = reg.assign(rl_share=reg["reverse_logistics"] / rl_total, gmv_share=reg["gmv"] / reg["gmv"].sum())
        reg = reg.assign(ratio=reg["rl_share"] / reg["gmv_share"])
        worst = reg.sort_values("ratio", ascending=False).iloc[0]
        if worst["ratio"] >= 1.25:
            out.append({
                "id": "region_logistics", "tone": "risk",
                "title": f"{worst['shipping_region']} carries outsized reverse-logistics cost",
                "detail": (f"{worst['rl_share']:.1%} of reverse-logistics spend against {worst['gmv_share']:.1%} of GMV "
                           f"({worst['ratio']:.1f}x its sales share)."),
                "metric": "reverse_logistics",
            })

    # 4. high-sales product with weak contribution
    prods = aggregate(lines, ["product_id", "product_name"])
    prods = prods[prods["units"] >= 15]
    if len(prods) >= 8:
        q75 = prods["gmv"].quantile(0.75)
        big = prods[prods["gmv"] >= q75].sort_values("contribution_margin")
        if len(big):
            p = big.iloc[0]
            portfolio_margin = summary.get("contribution_margin") or 0
            if p["contribution_margin"] is not None and p["contribution_margin"] < portfolio_margin * 0.5:
                out.append({
                    "id": "weak_product", "tone": "risk",
                    "title": f"{p['product_name']} sells well but barely contributes",
                    "detail": (f"Top-quartile GMV of {_inr(p['gmv'])} but an estimated contribution margin of "
                               f"{p['contribution_margin']:.1%} after return costs "
                               f"(portfolio: {portfolio_margin:.1%}); return rate {p['unit_return_rate']:.1%}."),
                    "metric": "contribution_margin",
                })

    # 5. month-over-month change
    monthly = aggregate(lines, "month").sort_values("month")
    monthly = monthly[monthly["units"] >= 200]
    if len(monthly) >= 2:
        last, prev = monthly.iloc[-1], monthly.iloc[-2]
        delta = last["unit_return_rate"] - prev["unit_return_rate"]
        if abs(delta) >= 0.005:
            out.append({
                "id": "mom_change", "tone": "risk" if delta > 0 else "positive",
                "title": (f"Return rate {'rose' if delta > 0 else 'fell'} {abs(delta) * 100:.1f} pts in "
                          f"{pd.Period(last['month']).strftime('%b %Y')}"),
                "detail": (f"{last['unit_return_rate']:.1%} vs {prev['unit_return_rate']:.1%} in "
                           f"{pd.Period(prev['month']).strftime('%b %Y')} (orders placed in each month)."),
                "metric": "unit_return_rate",
            })

    # 6. scenario teaser (moderate preset)
    if summary.get("incremental_costs"):
        params = preset_params("moderate", summary["incremental_costs"])
        res = simulate(cats, params, months)
        if res["net_improvement"] > 0:
            out.append({
                "id": "scenario", "tone": "positive",
                "title": f"Moderate scenario: about {_inr(res['net_improvement'])} net improvement (hypothetical)",
                "detail": (f"Avoiding {params.return_reduction:.0%} of returns with {params.logistics_reduction:.0%} "
                           f"cheaper reverse logistics saves {_inr(res['gross_cost_savings'])} in return costs and "
                           f"retains {_inr(res['retained_margin'])} margin after {_inr(params.prevention_spend)} spend."),
                "metric": "scenario",
            })
    return out[:5]
