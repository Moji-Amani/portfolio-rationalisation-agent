"""Step 7: the human approval gate.

Nothing the agent proposes is finalised without a human decision. This module
renders the recommendations as a scannable summary, then **stops and waits** for
one of three responses:

- **approve** — proceed with the recommendations as shown;
- **edit**    — the human amends the set (via an ``edit`` callback) and is then
                asked to approve the amended set;
- **reject**  — abandon; nothing is actioned.

The gate actions nothing itself; it only decides whether downstream steps may
proceed. It takes its input source and output stream as injectable callables so
it can be driven deterministically in tests (no real stdin required).
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Callable

from .recommend import Recommendation

APPROVED = "approved"
REJECTED = "rejected"

# Decisions that represent an action (shown first in the summary).
_ACTIONABLE_ORDER = [
    "retire", "merge", "do_not_renew", "procure", "needs_human_review", "keep",
]


@dataclass
class GateResult:
    outcome: str                                   # APPROVED or REJECTED
    approved_recommendations: list = field(default_factory=list)
    note: str = ""


def _fmt_money(rec: Recommendation) -> str:
    if rec.savings is None:
        return "—"
    s = rec.savings
    return f"£{s.low:,.0f} / £{s.base:,.0f} / £{s.high:,.0f}"


def format_summary(recommendations: list[Recommendation]) -> str:
    """Return the human-readable summary as a string (no I/O)."""
    order = {d: i for i, d in enumerate(_ACTIONABLE_ORDER)}
    rows = sorted(
        recommendations,
        key=lambda r: (order.get(r.decision, len(order)), r.tool_id),
    )

    lines: list[str] = []
    lines.append("=" * 72)
    lines.append("PORTFOLIO RATIONALISATION — RECOMMENDATIONS FOR APPROVAL")
    lines.append("=" * 72)

    # Counts by decision.
    counts: dict[str, int] = {}
    for r in recommendations:
        counts[r.decision] = counts.get(r.decision, 0) + 1
    summary_bits = [f"{counts[d]} {d}" for d in _ACTIONABLE_ORDER if d in counts]
    lines.append("Summary: " + (", ".join(summary_bits) if summary_bits else "none"))
    lines.append("")

    for r in rows:
        lines.append(
            f"[{r.decision.upper()}] {r.tool_id} {r.name}  "
            f"(confidence: {r.confidence}; {r.door_type})")
        lines.append(f"    savings (low/base/high): {_fmt_money(r)}")
        if r.cited_tool_ids:
            lines.append(f"    cited tools: {', '.join(r.cited_tool_ids)}")
        if r.cited_requirement_ids:
            lines.append(f"    cited requirements: {', '.join(r.cited_requirement_ids)}")
        for reason in r.reasoning:
            lines.append(f"    - {reason}")
        for flag in r.flags:
            lines.append(f"    ! {flag}")
        lines.append(f"    blast radius: {r.blast_radius}")
        lines.append("")

    lines.append("-" * 72)
    lines.append("Nothing will be actioned until you approve.")
    lines.append("Type: approve / edit / reject")
    return "\n".join(lines)


def approval_gate(
    recommendations: list[Recommendation],
    input_fn: Callable[[str], str] = input,
    output=None,
    edit_fn: Callable[[list[Recommendation]], list[Recommendation]] | None = None,
    max_prompts: int = 10,
) -> GateResult:
    """Print the summary, then stop and wait for approve / edit / reject.

    ``input_fn``  — supplies the human's response (default: builtin ``input``).
    ``output``    — stream to write to (default: ``sys.stdout``).
    ``edit_fn``   — called when the human chooses "edit"; receives the current
                    recommendations and returns the amended list. If not provided,
                    "edit" is unavailable and the user is re-prompted.
    ``max_prompts`` — guard against an infinite re-prompt loop.
    """
    out = output or sys.stdout
    current = list(recommendations)

    print(format_summary(current), file=out)

    prompts = 0
    while prompts < max_prompts:
        prompts += 1
        try:
            raw = input_fn("approve / edit / reject > ")
        except EOFError:
            # No input available: fail safe to reject (never auto-approve).
            return GateResult(REJECTED, [], note="no input (EOF); treated as reject")

        choice = (raw or "").strip().lower()

        if choice in ("approve", "a", "yes", "y"):
            return GateResult(APPROVED, current, note="approved by human")

        if choice in ("reject", "r", "no", "n"):
            return GateResult(REJECTED, [], note="rejected by human")

        if choice in ("edit", "e"):
            if edit_fn is None:
                print("Edit is not available in this session. "
                      "Please approve or reject.", file=out)
                continue
            current = list(edit_fn(current))
            print(format_summary(current), file=out)
            print("Amended set shown above. Approve to proceed, or edit again.",
                  file=out)
            continue

        # Unrecognised input: re-prompt rather than guess.
        print(f"Unrecognised response {raw!r}. "
              "Please type approve, edit, or reject.", file=out)

    # Too many invalid attempts: fail safe to reject.
    return GateResult(REJECTED, [], note="too many invalid responses; treated as reject")
