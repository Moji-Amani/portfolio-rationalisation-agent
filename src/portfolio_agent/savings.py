"""Step 5: savings_range — the single place numbers are computed.

Per the steering rules, **all** arithmetic lives here and **every** figure is a
``(low, base, high)`` range with its assumptions stated. The model/agent never
does sums; it calls these functions and quotes the ranges.

Two kinds of figure are produced:

1. ``retire_saving`` — the net annual saving from retiring/merging a redundant
   tool into a surviving one. It is::

       recoverable_share * annual_cost  -  migration_cost  -  surviving_uplift

   Each term has a low/base/high value. The ranges are paired *conservatively*:
   the LOW (worst-case) saving combines the smallest recoverable share with the
   largest migration cost and the largest uplift; the HIGH combines the largest
   recoverable share with the smallest migration and uplift.

2. ``licence_shortfall_cost`` — the annual cost to close a licence gap when a
   tool has more active users than licences::

       gap = active_users - licence_qty
       unit_price = annual_cost / licence_qty
       base = gap * unit_price
       low  = base * (1 - volume_discount)     # buy in volume
       high = base * (1 + mid_term_premium)    # buy mid-term at a premium

All monetary outputs are rounded to whole pounds.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Range:
    """A low/base/high money range (whole pounds) with its assumptions."""
    low: float
    base: float
    high: float
    assumptions: str = ""

    def rounded(self) -> "Range":
        return Range(round(self.low), round(self.base), round(self.high), self.assumptions)


@dataclass(frozen=True)
class RetireAssumptions:
    """Assumptions for a retire/merge saving.

    Each tuple is (low, base, high). Recoverable share is a fraction 0-1; the
    costs are absolute pounds. Low/base/high of *recoverable* is smallest-first;
    low/base/high of *migration* and *uplift* is largest-first, so that the
    pessimistic saving (low) is correctly paired with the costliest assumptions.
    """
    recoverable_share: tuple[float, float, float] = (0.60, 0.80, 0.95)
    migration_cost: tuple[float, float, float] = (50000, 30000, 15000)
    surviving_uplift: tuple[float, float, float] = (35000, 20000, 10000)


@dataclass(frozen=True)
class ShortfallAssumptions:
    """Assumptions for a licence-shortfall cost."""
    volume_discount: float = 0.20     # low end: buy in volume
    mid_term_premium: float = 0.10    # high end: buy mid-term at a premium
    # Optional explicit unit price; if None it is derived from annual_cost/licence_qty.
    unit_price: float | None = None


def retire_saving(annual_cost: float, assumptions: RetireAssumptions | None = None) -> Range:
    """Net annual saving range from retiring/merging a tool costing ``annual_cost``.

    low  = min_recoverable*cost - max_migration - max_uplift
    base = base_recoverable*cost - base_migration - base_uplift
    high = max_recoverable*cost - min_migration - min_uplift
    """
    a = assumptions or RetireAssumptions()
    rec_low, rec_base, rec_high = a.recoverable_share
    mig_low, mig_base, mig_high = a.migration_cost       # largest-first
    upl_low, upl_base, upl_high = a.surviving_uplift     # largest-first

    low = rec_low * annual_cost - mig_low - upl_low
    base = rec_base * annual_cost - mig_base - upl_base
    high = rec_high * annual_cost - mig_high - upl_high

    note = (
        f"recoverable {rec_low:.0%}/{rec_base:.0%}/{rec_high:.0%} of "
        f"£{annual_cost:,.0f}; migration £{mig_low:,.0f}/£{mig_base:,.0f}/£{mig_high:,.0f}; "
        f"surviving-tool uplift £{upl_low:,.0f}/£{upl_base:,.0f}/£{upl_high:,.0f}"
    )
    return Range(low, base, high, note).rounded()


def licence_shortfall_cost(
    annual_cost: float,
    licence_qty: int,
    active_users: int,
    assumptions: ShortfallAssumptions | None = None,
) -> Range:
    """Annual cost range to close a licence shortfall.

    Returns a zero range if there is no shortfall (active_users <= licence_qty).
    Raises ValueError if licence_qty is not positive and no unit price is given
    (we cannot derive a unit price by dividing by zero).
    """
    a = assumptions or ShortfallAssumptions()

    gap = active_users - licence_qty
    if gap <= 0:
        return Range(0, 0, 0, "no shortfall: active users within licensed quantity")

    if a.unit_price is not None:
        unit_price = a.unit_price
    else:
        if licence_qty <= 0:
            raise ValueError("cannot derive unit price: licence_qty must be > 0")
        unit_price = annual_cost / licence_qty

    base = gap * unit_price
    low = base * (1 - a.volume_discount)
    high = base * (1 + a.mid_term_premium)

    note = (
        f"{gap} licence shortfall ({active_users} active, {licence_qty} owned); "
        f"unit price £{unit_price:,.2f}; "
        f"{a.volume_discount:.0%} volume discount / list / +{a.mid_term_premium:.0%} mid-term premium"
    )
    return Range(low, base, high, note).rounded()


@dataclass
class SavingsResult:
    kind: str                      # "retire_saving" or "licence_shortfall"
    tool_id: str
    amount: Range
    inputs: dict = field(default_factory=dict)


def savings_range(rows, assumptions=None) -> list[SavingsResult]:
    """Compute money ranges for a list of request ``rows``.

    Each row is a dict describing one calculation, so the caller (step 6) decides
    *what* to compute while this module decides *how*. Supported shapes::

        {"kind": "retire_saving", "tool_id": "T001", "annual_cost": 180000}
        {"kind": "licence_shortfall", "tool_id": "T028",
         "annual_cost": 50000, "licence_qty": 200, "active_users": 260}

    ``assumptions`` may be a dict mapping kind -> (RetireAssumptions |
    ShortfallAssumptions) to override the defaults.
    """
    assumptions = assumptions or {}
    results: list[SavingsResult] = []

    for row in rows:
        kind = row["kind"]
        tool_id = row.get("tool_id", "")
        if kind == "retire_saving":
            amt = retire_saving(row["annual_cost"], assumptions.get("retire_saving"))
            results.append(SavingsResult(kind, tool_id, amt, inputs=dict(row)))
        elif kind == "licence_shortfall":
            amt = licence_shortfall_cost(
                row["annual_cost"], row["licence_qty"], row["active_users"],
                assumptions.get("licence_shortfall"),
            )
            results.append(SavingsResult(kind, tool_id, amt, inputs=dict(row)))
        else:
            raise ValueError(f"unknown savings kind {kind!r}")

    return results
