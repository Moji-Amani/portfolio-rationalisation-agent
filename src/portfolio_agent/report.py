"""Step 8: one-page memo + step-by-step log of every tool call.

The agent writes **only** these two artefacts. It never edits the inventory; it
reads the inputs, runs the analysis pipeline (steps 1–7), and emits:

- a **tool-call log** — an ordered, timestamped record of every agent tool call
  with a short summary of its inputs and result (the audit trail);
- a **one-page memo** — a concise, human-readable brief of the estate, the
  actionable recommendations (with the low/base/high ranges already computed by
  ``savings_range``), key flags, and the approval outcome.

Money in the memo is only ever a range produced earlier by ``savings_range``;
nothing is recomputed here. ``needs_human_review`` items are never presented as
decided.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from pathlib import Path

from .approval import APPROVED, approval_gate, format_summary
from .classify import classify_tools, load_taxonomy, low_confidence
from .overlap import overlap_groups
from .recommend import recommend
from .validate import read_inventory, read_requirements

_ACTIONABLE = ("retire", "merge", "do_not_renew", "procure", "needs_human_review")


@dataclass
class LogEntry:
    seq: int
    timestamp: str
    tool: str
    inputs: str
    result: str


@dataclass
class Logger:
    """Records every agent tool call in order."""
    entries: list[LogEntry] = field(default_factory=list)
    _clock: object = None  # optional callable returning a datetime (for tests)

    def log(self, tool: str, inputs: str, result: str) -> None:
        now = (self._clock() if self._clock else _dt.datetime.now())
        self.entries.append(LogEntry(
            seq=len(self.entries) + 1,
            timestamp=now.isoformat(timespec="seconds"),
            tool=tool,
            inputs=inputs,
            result=result,
        ))

    def render(self) -> str:
        lines = ["# Tool-call log", ""]
        lines.append(f"{len(self.entries)} tool call(s), in order:")
        lines.append("")
        for e in self.entries:
            lines.append(f"{e.seq:>2}. [{e.timestamp}] {e.tool}")
            lines.append(f"    in : {e.inputs}")
            lines.append(f"    out: {e.result}")
        return "\n".join(lines)


@dataclass
class AgentRun:
    recommendations: list
    gate_result: object
    issues: list
    low_confidence_maps: list
    log: Logger


def _fmt_range(rng) -> str:
    if rng is None:
        return "—"
    return f"£{rng.low:,.0f} / £{rng.base:,.0f} / £{rng.high:,.0f}"


def run_agent(
    inventory_path,
    requirements_path,
    taxonomy_path=None,
    reference_date: _dt.date | None = None,
    input_fn=None,
    output=None,
    logger: Logger | None = None,
) -> AgentRun:
    """Drive steps 1–7 through a logger. Reads inputs only; writes nothing to disk.

    Returns an :class:`AgentRun` holding the recommendations, the approval-gate
    result, any validation issues, low-confidence classifications, and the log.
    """
    inventory_path = Path(inventory_path)
    if taxonomy_path is None:
        taxonomy_path = inventory_path.parent / "taxonomy.csv"
    log = logger or Logger()

    # Step 1: read + validate.
    inv_result = read_inventory(inventory_path, taxonomy_path)
    log.log("read_inventory", f"path={inventory_path.name}",
            f"{len(inv_result.rows)} tools, {len(inv_result.issues)} issue(s)")
    req_result = read_requirements(requirements_path)
    log.log("read_requirements", f"path={Path(requirements_path).name}",
            f"{len(req_result.rows)} requirements, {len(req_result.issues)} issue(s)")

    # Step 2: classify.
    taxonomy = load_taxonomy(taxonomy_path)
    classifications = classify_tools(inv_result.rows, taxonomy)
    flagged = low_confidence(classifications)
    log.log("classify_tools", f"{len(inv_result.rows)} tools",
            f"{len(flagged)} low-confidence mapping(s)")

    # Step 3: overlap (logged for the audit trail; recommend recomputes as needed).
    groups = overlap_groups(inv_result.rows)
    log.log("overlap_groups", f"{len(inv_result.rows)} tools",
            f"{len(groups)} overlap group(s)")

    # Steps 4–6: recommendations (composes dependency + savings internally).
    kwargs = {}
    if reference_date is not None:
        kwargs["reference_date"] = reference_date
    recs = recommend(inv_result.rows, req_result.rows, **kwargs)
    actionable = [r for r in recs if r.decision in _ACTIONABLE]
    log.log("recommend", f"{len(inv_result.rows)} tools, {len(req_result.rows)} reqs",
            f"{len(recs)} recommendations ({len(actionable)} actionable)")

    # Step 7: approval gate.
    gate_kwargs = {}
    if input_fn is not None:
        gate_kwargs["input_fn"] = input_fn
    if output is not None:
        gate_kwargs["output"] = output
    gate = approval_gate(recs, **gate_kwargs)
    log.log("approval_gate", f"{len(recs)} recommendations presented",
            f"outcome={gate.outcome}, {len(gate.approved_recommendations)} approved")

    return AgentRun(
        recommendations=recs,
        gate_result=gate,
        issues=list(inv_result.issues) + list(req_result.issues),
        low_confidence_maps=flagged,
        log=log,
    )


def write_memo(run: AgentRun, reference_date: _dt.date | None = None) -> str:
    """Render the one-page memo for a completed :class:`AgentRun`."""
    recs = run.recommendations
    counts: dict[str, int] = {}
    for r in recs:
        counts[r.decision] = counts.get(r.decision, 0) + 1

    ref = reference_date.isoformat() if reference_date else _dt.date.today().isoformat()
    approved = run.gate_result.outcome == APPROVED

    lines: list[str] = []
    lines.append("# Portfolio rationalisation — decision memo")
    lines.append(f"_Reference date: {ref}. Synthetic data; figures are ranges "
                 "(low/base/high) with stated assumptions._")
    lines.append("")

    # Estate at a glance.
    lines.append("## Estate at a glance")
    lines.append(f"- Tools assessed: {len(recs)}")
    glance = ", ".join(f"{counts[d]} {d.replace('_', ' ')}"
                       for d in list(_ACTIONABLE) + ["keep"] if d in counts)
    lines.append(f"- Decisions: {glance}")
    if run.issues:
        lines.append(f"- Data advisories raised at validation: {len(run.issues)} "
                     "(see tool-call log / validation output)")
    if run.low_confidence_maps:
        lines.append(f"- Low-confidence capability mappings: "
                     f"{len(run.low_confidence_maps)}")
    lines.append("")

    # Actionable recommendations.
    order = {d: i for i, d in enumerate(_ACTIONABLE)}
    actionable = sorted(
        [r for r in recs if r.decision in _ACTIONABLE],
        key=lambda r: (order[r.decision], r.tool_id))
    lines.append("## Recommended actions (not final until approved)")
    if not actionable:
        lines.append("- None; all tools recommended to keep.")
    for r in actionable:
        lines.append(
            f"- **{r.decision.replace('_', ' ').upper()}** — {r.tool_id} "
            f"{r.name} · {r.door_type} · confidence {r.confidence}")
        lines.append(f"  - savings/cost (low/base/high): {_fmt_range(r.savings)}")
        if r.cited_tool_ids:
            lines.append(f"  - cited tools: {', '.join(r.cited_tool_ids)}")
        if r.cited_requirement_ids:
            lines.append(f"  - cited requirements: {', '.join(r.cited_requirement_ids)}")
        for flag in r.flags:
            lines.append(f"  - ⚠ {flag}")
    lines.append("")

    # Kept tools (summarised, not listed).
    kept = counts.get("keep", 0)
    lines.append("## Kept")
    lines.append(f"- {kept} tool(s) recommended to keep (status quo). "
                 "Hardware/perpetual assets carry a One-Way-Door note if ever "
                 "decommissioned.")
    lines.append("")

    # Approval outcome.
    lines.append("## Approval")
    if approved:
        lines.append(f"- Status: **APPROVED** by human "
                     f"({len(run.gate_result.approved_recommendations)} items). "
                     "Actions may proceed.")
    else:
        lines.append("- Status: **NOT APPROVED** (rejected or not yet decided). "
                     "No action is taken; recommendations remain proposals.")
    lines.append("")
    lines.append("_Nothing in this memo was actioned by the agent. The agent only "
                 "reads inputs and writes this memo and the tool-call log._")
    return "\n".join(lines)


def write_artifacts(run: AgentRun, out_dir, reference_date: _dt.date | None = None) -> dict:
    """Persist the memo and log under ``out_dir``. Returns the written paths."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    memo_path = out_dir / "memo.md"
    log_path = out_dir / "tool_call_log.md"
    memo_path.write_text(write_memo(run, reference_date))
    log_path.write_text(run.log.render())
    return {"memo": memo_path, "log": log_path}
