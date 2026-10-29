"""Step 6: recommend keep / merge / retire (and related actions).

This composes the earlier steps into a per-tool recommendation. It decides
nothing the guardrails do not support:

- every recommendation cites the inventory rows it used and carries a confidence;
- it is tagged Two-Way Door (reversible) or One-Way Door (irreversible) with a
  blast radius;
- a tool a Must requirement depends on with no fallback is never retired — it is
  flagged;
- all money comes from ``savings_range`` (step 5); nothing is summed here;
- anything below the confidence threshold is "needs human review", not decided.

Nothing here is final — step 7 (the approval gate) still stands between this and
any action.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field

from .dependency import dependency_check
from .overlap import overlap_groups
from .savings import Range, savings_range

# Decisions.
KEEP = "keep"
MERGE = "merge"
RETIRE = "retire"
DO_NOT_RENEW = "do_not_renew"
PROCURE = "procure"
NEEDS_REVIEW = "needs_human_review"

# Door types.
TWO_WAY = "Two-Way Door"
ONE_WAY = "One-Way Door"

# Confidence levels.
HIGH = "high"
MEDIUM = "medium"
LOW = "low"

# Tunable thresholds.
RENEWAL_WINDOW_DAYS = 90      # contract ending within this window is a renewal decision
LOW_UTILISATION_PCT = 40      # at or below this, utilisation is considered low
REFERENCE_DATE = _dt.date(2026, 10, 27)


@dataclass
class Recommendation:
    tool_id: str
    name: str
    decision: str
    confidence: str
    door_type: str
    blast_radius: str
    reasoning: list[str] = field(default_factory=list)
    cited_tool_ids: list[str] = field(default_factory=list)
    cited_requirement_ids: list[str] = field(default_factory=list)
    savings: Range | None = None
    flags: list[str] = field(default_factory=list)


def _door_type_for_removal(tool) -> str:
    """Removing a hardware/capex asset is irreversible; software opex is not."""
    if tool.type == "hardware" or tool.cost_type == "capex":
        return ONE_WAY
    return TWO_WAY


def _days_to_contract_end(tool, reference_date: _dt.date) -> int | None:
    if tool.contract_end is None:
        return None
    return (tool.contract_end - reference_date).days


def _is_orphan(tool) -> bool:
    return (not tool.owner) or (tool.active_users == 0)


def recommend(
    inventory,
    requirements=None,
    reference_date: _dt.date = REFERENCE_DATE,
) -> list[Recommendation]:
    """Produce one :class:`Recommendation` per tool in ``inventory``."""
    inventory = list(inventory)

    # Pre-compute overlap membership: map tool_id -> (group, is_survivor).
    groups = overlap_groups(inventory)
    merge_candidate_of: dict[str, object] = {}
    survivor_of_group: dict[str, object] = {}
    for g in groups:
        surv = g.survivor
        if surv is not None:
            survivor_of_group[surv.tool_id] = g
        for cand in g.merge_candidates:
            merge_candidate_of[cand.tool_id] = g

    recs: list[Recommendation] = []
    for tool in inventory:
        recs.append(_recommend_one(
            tool, inventory, requirements, reference_date,
            merge_candidate_of, survivor_of_group,
        ))
    return recs


def _recommend_one(tool, inventory, requirements, reference_date,
                   merge_candidate_of, survivor_of_group) -> Recommendation:
    dep = dependency_check(tool.tool_id, inventory, requirements)
    blocking = dep.blocking_dependencies
    must_deps = dep.must_dependencies

    reasoning: list[str] = []
    cited_tools: list[str] = [tool.tool_id]
    cited_reqs: list[str] = list(tool.requirement_ids)
    flags: list[str] = []

    days_left = _days_to_contract_end(tool, reference_date)
    util = tool.utilisation_pct

    # ----- Safety first: a blocking Must dependency forbids retiring. --------
    if blocking:
        req_ids = [d.requirement_id for d in blocking]
        cited_reqs.extend(req_ids)
        flags.append(
            f"Must requirement(s) {', '.join(req_ids)} depend on this tool with no "
            f"fallback; do not retire without a replacement.")
        reasoning.append(
            "A Must requirement relies on this tool and nothing else covers it, "
            "so retiring it would break coverage.")
        door = _door_type_for_removal(tool)
        return Recommendation(
            tool_id=tool.tool_id, name=tool.name, decision=KEEP,
            confidence=HIGH, door_type=door,
            blast_radius=f"Must coverage of {', '.join(req_ids)}",
            reasoning=reasoning, cited_tool_ids=_dedupe(cited_tools),
            cited_requirement_ids=_dedupe(cited_reqs), flags=flags)

    # ----- Orphan: no owner or no users -> retire candidate, but review. -----
    if _is_orphan(tool):
        if not tool.owner:
            flags.append("No owner recorded; identify an owner before any action.")
        if tool.active_users == 0:
            reasoning.append("Zero active users.")
        reasoning.append(
            "No Must requirement depends on this tool." if not must_deps
            else "Review dependencies before acting.")
        door = _door_type_for_removal(tool)
        return Recommendation(
            tool_id=tool.tool_id, name=tool.name, decision=NEEDS_REVIEW,
            confidence=LOW, door_type=door,
            blast_radius="None identified (no active users)",
            reasoning=reasoning, cited_tool_ids=_dedupe(cited_tools),
            cited_requirement_ids=_dedupe(cited_reqs), flags=flags)

    # ----- Under-provisioned: more active users than licences -> procure. ----
    if (tool.licence_qty is not None and tool.active_users is not None
            and tool.active_users > tool.licence_qty):
        cost = None
        if tool.annual_cost_gbp is not None and tool.licence_qty > 0:
            cost = savings_range([{
                "kind": "licence_shortfall", "tool_id": tool.tool_id,
                "annual_cost": tool.annual_cost_gbp,
                "licence_qty": tool.licence_qty,
                "active_users": tool.active_users,
            }])[0].amount
        gap = tool.active_users - tool.licence_qty
        reasoning.append(
            f"{tool.active_users} active users exceed {tool.licence_qty} licences "
            f"(shortfall of {gap}).")
        if must_deps:
            cited_reqs.extend(d.requirement_id for d in must_deps)
            reasoning.append(
                f"Supports Must requirement(s) "
                f"{', '.join(d.requirement_id for d in must_deps)}.")
        return Recommendation(
            tool_id=tool.tool_id, name=tool.name, decision=PROCURE,
            confidence=HIGH, door_type=TWO_WAY,
            blast_radius=f"{gap} users over-deployed; compliance exposure",
            reasoning=reasoning, cited_tool_ids=_dedupe(cited_tools),
            cited_requirement_ids=_dedupe(cited_reqs), savings=cost, flags=flags)

    # ----- Merge candidate within an overlap group. --------------------------
    group = merge_candidate_of.get(tool.tool_id)
    if group is not None:
        surv = group.survivor
        cited_tools.append(surv.tool_id)
        score = next(t.redundancy_score for t in group.tools if t.tool_id == tool.tool_id)
        reasoning.append(
            f"Overlaps with {surv.name} ({surv.tool_id}) on capability "
            f"'{group.capability}'; redundancy score {score:.2f}.")
        reasoning.append(
            f"Its requirements are also covered by {surv.name}, so merging loses "
            "no unique coverage.")
        saving = None
        if tool.annual_cost_gbp is not None:
            saving = savings_range([{
                "kind": "retire_saving", "tool_id": tool.tool_id,
                "annual_cost": tool.annual_cost_gbp,
            }])[0].amount
        # Software opex merge is reversible at renewal -> Two-Way.
        door = _door_type_for_removal(tool)
        confidence = HIGH if (util is not None and util <= LOW_UTILISATION_PCT) else MEDIUM
        return Recommendation(
            tool_id=tool.tool_id, name=tool.name, decision=MERGE,
            confidence=confidence, door_type=door,
            blast_radius=f"Users of {tool.name} migrate to {surv.name}",
            reasoning=reasoning, cited_tool_ids=_dedupe(cited_tools),
            cited_requirement_ids=_dedupe(cited_reqs), savings=saving, flags=flags)

    # ----- Renewal decision: contract ending soon + low utilisation. ---------
    if (days_left is not None and 0 <= days_left <= RENEWAL_WINDOW_DAYS
            and util is not None and util <= LOW_UTILISATION_PCT):
        # Is everything it covers also covered elsewhere?
        covered_elsewhere = all(d.covered_elsewhere for d in dep.dependencies) \
            if dep.dependencies else True
        for d in dep.dependencies:
            cited_tools.extend(d.other_covering_tools)
        reasoning.append(
            f"Contract ends in {days_left} days and utilisation is {util}%.")
        if covered_elsewhere and not must_deps:
            reasoning.append("Its requirements are covered by other tools.")
            decision, confidence = DO_NOT_RENEW, HIGH
        elif covered_elsewhere:
            reasoning.append("Must requirements remain covered elsewhere.")
            decision, confidence = DO_NOT_RENEW, MEDIUM
        else:
            flags.append("Not all requirements are covered elsewhere; confirm before lapsing.")
            decision, confidence = NEEDS_REVIEW, LOW
        return Recommendation(
            tool_id=tool.tool_id, name=tool.name, decision=decision,
            confidence=confidence, door_type=TWO_WAY,
            blast_radius="Licence lapses at contract end",
            reasoning=reasoning, cited_tool_ids=_dedupe(cited_tools),
            cited_requirement_ids=_dedupe(cited_reqs), flags=flags)

    # ----- Claimed-only evidence note. Distinguish linked vs covered. --------
    if tool.evidence_level == "claimed only":
        linked_musts = [d.requirement_id for d in must_deps]
        detail = (f" (including Must requirement(s) {', '.join(linked_musts)})"
                  if linked_musts else "")
        flags.append(
            f"Capability evidence is 'claimed only'; it does NOT count as covering "
            f"any requirement{detail} until demonstrated.")

    # ----- Default: keep. ----------------------------------------------------
    reasoning.append(
        f"Utilisation {util}%." if util is not None else "Utilisation unknown.")
    # Only claim support for Must requirements this tool GENUINELY covers.
    covered_musts = [d.requirement_id for d in must_deps if d.covers]
    uncovered_musts = [d.requirement_id for d in must_deps if not d.covers]
    if covered_musts:
        reasoning.append(f"Supports Must requirement(s) {', '.join(covered_musts)}.")
    if uncovered_musts:
        reasoning.append(
            f"Linked to Must requirement(s) {', '.join(uncovered_musts)} but does "
            "not count as covering them (evidence insufficient).")

    # Hardware / capex assets cannot be rolled back if decommissioned later.
    removal_door = _door_type_for_removal(tool)
    if removal_door == ONE_WAY:
        flags.append(
            "If ever decommissioned, this is a One-Way Door (hardware/perpetual "
            "asset with no rollback).")

    confidence = HIGH if util is not None else LOW
    return Recommendation(
        tool_id=tool.tool_id, name=tool.name, decision=KEEP,
        confidence=confidence, door_type=TWO_WAY,
        blast_radius="None (status quo)",
        reasoning=reasoning, cited_tool_ids=_dedupe(cited_tools),
        cited_requirement_ids=_dedupe(cited_reqs), flags=flags)


def _dedupe(items) -> list[str]:
    seen: dict[str, None] = {}
    for it in items:
        if it:
            seen.setdefault(it, None)
    return list(seen)
