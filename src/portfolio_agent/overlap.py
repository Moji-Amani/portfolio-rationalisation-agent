"""Step 3: find overlapping tools and score redundancy.

Tools that share the same ``capability`` are overlap candidates: the estate may
be paying for two things that do the same job. For each capability with more
than one tool we build an :class:`OverlapGroup` that ranks the members and marks
a likely *survivor* (keep) and *merge candidates* (the weaker peers).

Redundancy score
-----------------
This step produces only a **dimensionless score** and exposes the raw signals it
used. It never computes money — all financial figures are produced later by
``savings_range`` (step 5), per the steering rules.

For each tool in a group we compute a redundancy score in [0, 1]; a *higher*
score means the tool is a *stronger candidate to retire/merge away*. It combines
three signals (equal weight):

- low utilisation           -> ``1 - utilisation_pct/100``
- few users relative to the busiest peer in the group
                            -> ``1 - active_users / max_users_in_group``
- requirement coverage overlap: the share of this tool's requirements that are
  also covered by at least one peer in the same group
                            -> ``covered_elsewhere / total_requirements`` (1.0 if
  the tool maps to no requirements, i.e. nothing unique would be lost)

The tool with the *lowest* redundancy score is the suggested survivor; the
others are merge candidates. Missing signals (``None``) are treated
conservatively (as 0 contribution) and noted. Nothing here is a decision — it
feeds the recommendation step, which still routes through the approval gate.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ToolScore:
    tool_id: str
    name: str
    redundancy_score: float          # [0,1]; higher = stronger retire candidate
    utilisation_pct: int | None
    active_users: int | None
    requirement_ids: list[str]
    requirements_covered_elsewhere: list[str]  # reqs a peer also covers
    unique_requirements: list[str]              # reqs only this tool covers in-group
    note: str = ""


@dataclass
class OverlapGroup:
    capability: str
    tools: list[ToolScore] = field(default_factory=list)

    @property
    def survivor(self) -> ToolScore | None:
        """Suggested tool to keep: the lowest redundancy score."""
        if not self.tools:
            return None
        return min(self.tools, key=lambda t: t.redundancy_score)

    @property
    def merge_candidates(self) -> list[ToolScore]:
        """Everything except the survivor, highest redundancy first."""
        surv = self.survivor
        others = [t for t in self.tools if t is not surv]
        return sorted(others, key=lambda t: t.redundancy_score, reverse=True)


def _coverage_overlap(tool, peers) -> tuple[list[str], list[str]]:
    """Split a tool's requirement ids into (covered_elsewhere, unique_in_group)."""
    peer_reqs: set[str] = set()
    for p in peers:
        peer_reqs.update(p.requirement_ids)
    covered_elsewhere = [r for r in tool.requirement_ids if r in peer_reqs]
    unique = [r for r in tool.requirement_ids if r not in peer_reqs]
    return covered_elsewhere, unique


def _score_tool(tool, peers) -> ToolScore:
    notes: list[str] = []

    # Signal 1: low utilisation.
    if tool.utilisation_pct is None:
        util_component = 0.0
        notes.append("utilisation missing; treated as 0 contribution")
    else:
        util_component = 1.0 - (tool.utilisation_pct / 100.0)

    # Signal 2: few users relative to the busiest peer (incl. this tool).
    group = list(peers) + [tool]
    user_values = [t.active_users for t in group if t.active_users is not None]
    max_users = max(user_values) if user_values else 0
    if tool.active_users is None:
        users_component = 0.0
        notes.append("active_users missing; treated as 0 contribution")
    elif max_users == 0:
        users_component = 1.0  # nobody uses any of them -> all highly redundant
    else:
        users_component = 1.0 - (tool.active_users / max_users)

    # Signal 3: requirement coverage overlap.
    covered_elsewhere, unique = _coverage_overlap(tool, peers)
    if not tool.requirement_ids:
        coverage_component = 1.0  # maps to nothing unique -> nothing lost by merging
    else:
        coverage_component = len(covered_elsewhere) / len(tool.requirement_ids)

    score = (util_component + users_component + coverage_component) / 3.0

    return ToolScore(
        tool_id=tool.tool_id,
        name=tool.name,
        redundancy_score=round(score, 4),
        utilisation_pct=tool.utilisation_pct,
        active_users=tool.active_users,
        requirement_ids=list(tool.requirement_ids),
        requirements_covered_elsewhere=covered_elsewhere,
        unique_requirements=unique,
        note="; ".join(notes),
    )


def overlap_groups(inventory) -> list[OverlapGroup]:
    """Group tools by capability and score redundancy within each group.

    ``inventory`` is an iterable of ``Tool`` (e.g. ``read_inventory(...).rows``).
    Only capabilities with two or more tools are returned (a single tool is not
    an overlap). Groups are ordered by capability name for stable output.
    """
    by_cap: dict[str, list] = {}
    for tool in inventory:
        by_cap.setdefault(tool.capability, []).append(tool)

    groups: list[OverlapGroup] = []
    for capability in sorted(by_cap):
        members = by_cap[capability]
        if len(members) < 2:
            continue
        scored = []
        for tool in members:
            peers = [t for t in members if t is not tool]
            scored.append(_score_tool(tool, peers))
        groups.append(OverlapGroup(capability=capability, tools=scored))
    return groups
