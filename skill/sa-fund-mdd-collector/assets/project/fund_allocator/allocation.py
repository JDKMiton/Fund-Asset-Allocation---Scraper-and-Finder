"""Look-through asset allocation for portfolios built from several funds."""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import Portfolio, Template


@dataclass
class LookThrough:
    portfolio: str
    allocation: dict[str, float]           # category -> % of portfolio
    contributions: dict[str, dict[str, float]]  # fund -> category -> % of portfolio
    weights: dict[str, float]              # fund -> normalised weight (%)
    warnings: list[str] = field(default_factory=list)


def normalise(allocation: dict[str, float]) -> dict[str, float]:
    """Scale an allocation so it sums to exactly 100%."""
    total = sum(allocation.values())
    if total == 0:
        return dict(allocation)
    return {k: v * 100 / total for k, v in allocation.items()}


def look_through(portfolio: Portfolio, fund_allocations: dict[str, dict[str, float]],
                 template: Template, rescale_funds: bool = True) -> LookThrough:
    """Weighted sum of each underlying fund's allocation.

    ``rescale_funds`` scales each fund's allocation to 100% first so rounding in
    the MDD doesn't leak into the portfolio total.
    """
    warnings = []
    total_weight = sum(h.weight for h in portfolio.holdings)
    if abs(total_weight - 100) > 0.01:
        warnings.append(f"holding weights sum to {total_weight:.2f}% - rescaled to 100%")

    result = {c: 0.0 for c in template.category_names}
    contributions: dict[str, dict[str, float]] = {}
    weights: dict[str, float] = {}
    for h in portfolio.holdings:
        w = h.weight * 100 / total_weight if total_weight else 0.0
        weights[h.fund] = w
        alloc = fund_allocations.get(h.fund)
        if not alloc:
            warnings.append(f"no allocation for '{h.fund}' ({w:.2f}% of portfolio) - shown as Unallocated")
            contributions[h.fund] = {"Unallocated": w}
            result["Unallocated"] = result.get("Unallocated", 0.0) + w
            continue
        if rescale_funds:
            alloc = normalise(alloc)
        contributions[h.fund] = {}
        for cat, pct in alloc.items():
            share = w * pct / 100
            contributions[h.fund][cat] = share
            result[cat] = result.get(cat, 0.0) + share

    return LookThrough(portfolio=portfolio.name, allocation=result, contributions=contributions,
                       weights=weights, warnings=warnings)
