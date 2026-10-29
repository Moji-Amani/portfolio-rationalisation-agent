"""Step 1: input readers with validation.

`read_inventory` and `read_requirements` load the CSV inputs, coerce types and
validate every row against the schema. A duplicate tool_id is *blocking* (the
whole read fails); every other problem is *reported* as a row-level issue while
the valid rows are still returned.

Validation rules (from the spec and the data generator):
  - types: numeric fields must parse as int; ids/text are non-empty strings
  - dates: contract_end must be a real calendar date in ISO YYYY-MM-DD form
  - ranges: utilisation_pct in 0-100 inclusive
  - evidence levels: one of the allowed set
  - taxonomy membership: capability must appear in taxonomy.csv
  - unique ids: tool_id / requirement_id unique (duplicate tool_id is blocking)

Nothing here computes savings or makes recommendations; it only reads and checks.
"""
from __future__ import annotations

import csv
import datetime as _dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

# Allowed controlled vocabularies (from the data generator / steering rules).
ALLOWED_EVIDENCE = ("tested", "demonstrated", "documented", "claimed only")
ALLOWED_TYPE = ("software", "hardware")
ALLOWED_COST_TYPE = ("opex", "capex")
ALLOWED_PRIORITY = ("Must", "Should", "Could")

INVENTORY_COLS = [
    "tool_id", "name", "capability", "vendor", "type", "cost_type",
    "annual_cost_gbp", "contract_end", "licence_qty", "active_users",
    "utilisation_pct", "owner", "requirement_ids", "evidence_level",
]
REQUIREMENT_COLS = ["requirement_id", "text", "priority", "threshold", "owner"]


class BlockingValidationError(Exception):
    """Raised when a read cannot proceed (e.g. a duplicate primary key)."""


@dataclass
class Issue:
    """A single reported (non-blocking) validation problem."""
    row_id: str
    field: str
    message: str

    def __str__(self) -> str:  # pragma: no cover - convenience only
        loc = self.row_id if not self.field else f"{self.row_id}.{self.field}"
        return f"{loc}: {self.message}"


@dataclass
class Tool:
    tool_id: str
    name: str
    capability: str
    vendor: str
    type: str
    cost_type: str
    annual_cost_gbp: int | None
    contract_end: _dt.date | None
    licence_qty: int | None
    active_users: int | None
    utilisation_pct: int | None
    owner: str
    requirement_ids: list[str]
    evidence_level: str


@dataclass
class Requirement:
    requirement_id: str
    text: str
    priority: str
    threshold: str
    owner: str


@dataclass
class ReadResult:
    """Return value for the readers: clean rows plus any reported issues."""
    rows: list = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _load_taxonomy(path: str | Path) -> set[str]:
    caps: set[str] = set()
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            cap = (r.get("capability") or "").strip()
            if cap:
                caps.add(cap)
    return caps


def _parse_int(value: str) -> int | None:
    value = (value or "").strip()
    if value == "":
        return None
    return int(value)  # raises ValueError on non-numeric


def _parse_date(value: str) -> _dt.date:
    """Parse strict ISO date; raise ValueError for anything else."""
    value = (value or "").strip()
    return _dt.date.fromisoformat(value)


def _check_header(got: list[str], expected: list[str], path: str | Path) -> None:
    if [c.strip() for c in got] != expected:
        raise BlockingValidationError(
            f"{path}: unexpected header {got!r}; expected {expected!r}"
        )


# --------------------------------------------------------------------------- #
# Public readers
# --------------------------------------------------------------------------- #
def read_inventory(
    path: str | Path,
    taxonomy_path: str | Path | None = None,
) -> ReadResult:
    """Read and validate the inventory CSV.

    A duplicate tool_id raises ``BlockingValidationError``. All other problems
    are collected as :class:`Issue` records; rows with issues are still returned
    (with the offending field left as ``None``/raw) so downstream steps can see
    them, but the problem is reported.
    """
    path = Path(path)
    if taxonomy_path is None:
        taxonomy_path = path.parent / "taxonomy.csv"
    taxonomy = _load_taxonomy(taxonomy_path)

    result = ReadResult()
    seen_ids: set[str] = set()

    with open(path, newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header is None:
            raise BlockingValidationError(f"{path}: file is empty")
        _check_header(header, INVENTORY_COLS, path)

        for raw in reader:
            if not raw or all(c.strip() == "" for c in raw):
                continue
            row = dict(zip(INVENTORY_COLS, raw))
            tool_id = (row["tool_id"] or "").strip()

            # Blocking: duplicate primary key.
            if tool_id in seen_ids:
                raise BlockingValidationError(
                    f"{path}: duplicate tool_id {tool_id!r} (blocking)"
                )
            if tool_id:
                seen_ids.add(tool_id)
            else:
                result.issues.append(Issue("<row>", "tool_id", "missing tool_id"))

            rid = tool_id or "<row>"

            # type / cost_type / evidence_level controlled vocabularies.
            if row["type"].strip() not in ALLOWED_TYPE:
                result.issues.append(
                    Issue(rid, "type", f"type {row['type']!r} not in {ALLOWED_TYPE}"))
            if row["cost_type"].strip() not in ALLOWED_COST_TYPE:
                result.issues.append(
                    Issue(rid, "cost_type",
                          f"cost_type {row['cost_type']!r} not in {ALLOWED_COST_TYPE}"))
            if row["evidence_level"].strip() not in ALLOWED_EVIDENCE:
                result.issues.append(
                    Issue(rid, "evidence_level",
                          f"evidence_level {row['evidence_level']!r} not allowed"))

            # owner must be present.
            if (row["owner"] or "").strip() == "":
                result.issues.append(Issue(rid, "owner", "missing owner"))

            # capability taxonomy membership.
            cap = row["capability"].strip()
            if cap not in taxonomy:
                result.issues.append(
                    Issue(rid, "capability",
                          f"capability {cap!r} not in taxonomy"))

            # numeric fields.
            annual_cost = licence_qty = active_users = util = None
            try:
                annual_cost = _parse_int(row["annual_cost_gbp"])
                if annual_cost is None:
                    result.issues.append(
                        Issue(rid, "annual_cost_gbp", "missing annual_cost_gbp"))
            except ValueError:
                result.issues.append(
                    Issue(rid, "annual_cost_gbp",
                          f"non-numeric annual_cost_gbp {row['annual_cost_gbp']!r}"))

            try:
                licence_qty = _parse_int(row["licence_qty"])
            except ValueError:
                result.issues.append(
                    Issue(rid, "licence_qty",
                          f"non-numeric licence_qty {row['licence_qty']!r}"))

            try:
                active_users = _parse_int(row["active_users"])
            except ValueError:
                result.issues.append(
                    Issue(rid, "active_users",
                          f"non-numeric active_users {row['active_users']!r}"))

            # utilisation range 0-100.
            try:
                util = _parse_int(row["utilisation_pct"])
                if util is not None and not (0 <= util <= 100):
                    result.issues.append(
                        Issue(rid, "utilisation_pct",
                              f"utilisation_pct {util} out of range 0-100"))
            except ValueError:
                result.issues.append(
                    Issue(rid, "utilisation_pct",
                          f"non-numeric utilisation_pct {row['utilisation_pct']!r}"))

            # contract_end date.
            contract_end = None
            try:
                contract_end = _parse_date(row["contract_end"])
            except ValueError:
                result.issues.append(
                    Issue(rid, "contract_end",
                          f"invalid contract_end {row['contract_end']!r}"))

            req_ids = [r for r in (row["requirement_ids"] or "").split(";") if r.strip()]

            result.rows.append(Tool(
                tool_id=tool_id,
                name=row["name"].strip(),
                capability=cap,
                vendor=row["vendor"].strip(),
                type=row["type"].strip(),
                cost_type=row["cost_type"].strip(),
                annual_cost_gbp=annual_cost,
                contract_end=contract_end,
                licence_qty=licence_qty,
                active_users=active_users,
                utilisation_pct=util,
                owner=row["owner"].strip(),
                requirement_ids=[r.strip() for r in req_ids],
                evidence_level=row["evidence_level"].strip(),
            ))

    return result


def read_requirements(path: str | Path) -> ReadResult:
    """Read and validate the requirements CSV.

    A duplicate requirement_id raises ``BlockingValidationError``. Other
    problems (bad priority, missing owner or threshold) are reported.
    """
    path = Path(path)
    result = ReadResult()
    seen_ids: set[str] = set()

    with open(path, newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header is None:
            raise BlockingValidationError(f"{path}: file is empty")
        _check_header(header, REQUIREMENT_COLS, path)

        for raw in reader:
            if not raw or all(c.strip() == "" for c in raw):
                continue
            row = dict(zip(REQUIREMENT_COLS, raw))
            req_id = (row["requirement_id"] or "").strip()

            if req_id in seen_ids:
                raise BlockingValidationError(
                    f"{path}: duplicate requirement_id {req_id!r} (blocking)")
            if req_id:
                seen_ids.add(req_id)
            else:
                result.issues.append(Issue("<row>", "requirement_id", "missing requirement_id"))

            rid = req_id or "<row>"

            if row["priority"].strip() not in ALLOWED_PRIORITY:
                result.issues.append(
                    Issue(rid, "priority",
                          f"priority {row['priority']!r} not in {ALLOWED_PRIORITY}"))
            if (row["owner"] or "").strip() == "":
                result.issues.append(Issue(rid, "owner", "missing owner"))
            if (row["threshold"] or "").strip() == "":
                result.issues.append(Issue(rid, "threshold", "missing measurable threshold"))

            result.rows.append(Requirement(
                requirement_id=req_id,
                text=row["text"].strip(),
                priority=row["priority"].strip(),
                threshold=row["threshold"].strip(),
                owner=row["owner"].strip(),
            ))

    return result
