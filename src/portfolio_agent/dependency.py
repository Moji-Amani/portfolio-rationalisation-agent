"""Step 4: dependency check.

``dependency_check`` answers the question "if we touch this tool, what
requirements are affected, and how badly?" For a given ``tool_id`` it returns
the requirements the tool is linked to, each with its priority, plus whether the
requirement would still be covered by *another* tool if this one were retired.

Critical rule (steering): ``evidence_level = "claimed only"`` **never** counts
as covering a requirement. A claimed-only link is reported as a *claimed* link,
not a *covering* one, and is excluded when deciding whether a requirement is
covered elsewhere.

This step reports facts only; it does not decide keep/retire (that is step 6)
and it computes no money (that is step 5).
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Evidence level that does not count as real coverage.
NON_COVERING_EVIDENCE = "claimed only"


@dataclass
class RequirementDependency:
    requirement_id: str
    priority: str | None                 # Must / Should / Could, or None if unknown
    covers: bool                         # does THIS tool actually cover it?
    covered_elsewhere: bool              # does another tool genuinely cover it?
    other_covering_tools: list[str] = field(default_factory=list)
    note: str = ""


@dataclass
class DependencyReport:
    tool_id: str
    found: bool                          # was the tool_id present in the inventory?
    dependencies: list[RequirementDependency] = field(default_factory=list)

    @property
    def must_dependencies(self) -> list[RequirementDependency]:
        return [d for d in self.dependencies if d.priority == "Must"]

    @property
    def blocking_dependencies(self) -> list[RequirementDependency]:
        """Must requirements this tool genuinely covers with no other coverage.

        Retiring the tool would leave these uncovered -> a hard dependency that
        must be flagged before any retire/decommission recommendation.
        """
        return [
            d for d in self.dependencies
            if d.priority == "Must" and d.covers and not d.covered_elsewhere
        ]


def _covers(tool, requirement_id: str) -> bool:
    """True if the tool is linked to the requirement with real evidence."""
    if requirement_id not in tool.requirement_ids:
        return False
    return tool.evidence_level != NON_COVERING_EVIDENCE


def dependency_check(tool_id: str, inventory, requirements=None) -> DependencyReport:
    """Report the requirements that rely on ``tool_id``.

    ``inventory`` is an iterable of ``Tool`` (e.g. ``read_inventory(...).rows``).
    ``requirements`` is an optional iterable of ``Requirement`` used to attach
    each requirement's priority; if omitted, priority is reported as ``None``.
    """
    inventory = list(inventory)
    priority_by_req: dict[str, str] = {}
    if requirements is not None:
        for r in requirements:
            priority_by_req[r.requirement_id] = r.priority

    tool = next((t for t in inventory if t.tool_id == tool_id), None)
    if tool is None:
        return DependencyReport(tool_id=tool_id, found=False)

    report = DependencyReport(tool_id=tool_id, found=True)

    for req_id in tool.requirement_ids:
        this_covers = tool.evidence_level != NON_COVERING_EVIDENCE

        # Which OTHER tools genuinely cover this requirement?
        others = [
            t.tool_id for t in inventory
            if t.tool_id != tool_id and _covers(t, req_id)
        ]

        note = ""
        if not this_covers:
            note = (f"{tool_id} links to {req_id} but evidence is "
                    f"'{NON_COVERING_EVIDENCE}' -> does not count as coverage")

        report.dependencies.append(RequirementDependency(
            requirement_id=req_id,
            priority=priority_by_req.get(req_id),
            covers=this_covers,
            covered_elsewhere=bool(others),
            other_covering_tools=others,
            note=note,
        ))

    return report
