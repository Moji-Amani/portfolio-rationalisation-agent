"""Step 2: classify tools against the capability taxonomy.

The inventory already carries a ``capability`` string. Classification here is
about judging *how confidently* that string maps to the controlled taxonomy, so
weak or ambiguous mappings are surfaced for human review rather than trusted
silently. This follows the steering rule: flag low-confidence mappings, never
guess a capability.

Confidence levels
-----------------
- ``exact``        : the capability is a member of the taxonomy. High confidence;
                     the domain is taken straight from the taxonomy.
- ``domain_only``  : the full capability is not in the taxonomy, but its domain
                     prefix (text before the first "/") is a known domain. We can
                     place the tool in a domain but not a specific capability.
                     Low confidence -> flagged.
- ``unknown``      : neither the capability nor its domain prefix is recognised.
                     Lowest confidence -> flagged.

Only ``exact`` is considered a confident mapping. Anything else is returned with
``needs_review = True`` so downstream steps and the human reviewer can see it.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

# Confidence ordering, highest first.
CONFIDENCE_EXACT = "exact"
CONFIDENCE_DOMAIN_ONLY = "domain_only"
CONFIDENCE_UNKNOWN = "unknown"


@dataclass
class Classification:
    tool_id: str
    capability: str
    domain: str | None          # resolved domain, or None if unknown
    confidence: str             # one of the CONFIDENCE_* constants
    needs_review: bool          # True for anything below an exact match
    note: str = ""              # human-readable reason when flagged


def load_taxonomy(path: str | Path) -> dict[str, str]:
    """Return a mapping of ``capability -> domain`` from taxonomy.csv."""
    mapping: dict[str, str] = {}
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cap = (row.get("capability") or "").strip()
            dom = (row.get("domain") or "").strip()
            if cap:
                mapping[cap] = dom
    return mapping


def classify_capability(capability: str, taxonomy: dict[str, str]) -> tuple[str | None, str, str]:
    """Classify a single capability string.

    Returns ``(domain, confidence, note)``.
    """
    cap = (capability or "").strip()
    if cap in taxonomy:
        return taxonomy[cap], CONFIDENCE_EXACT, ""

    # Try the domain prefix (text before the first "/").
    prefix = cap.split("/", 1)[0] if "/" in cap else cap
    known_domains = set(taxonomy.values())
    if prefix and prefix in known_domains:
        return (
            prefix,
            CONFIDENCE_DOMAIN_ONLY,
            f"capability {cap!r} not in taxonomy; matched domain {prefix!r} only",
        )

    return (
        None,
        CONFIDENCE_UNKNOWN,
        f"capability {cap!r} not recognised in taxonomy",
    )


def classify_tools(tools, taxonomy: dict[str, str]) -> list[Classification]:
    """Classify an iterable of :class:`~portfolio_agent.validate.Tool` objects.

    ``tools`` may be the ``.rows`` from :func:`read_inventory`.
    """
    results: list[Classification] = []
    for tool in tools:
        domain, confidence, note = classify_capability(tool.capability, taxonomy)
        results.append(Classification(
            tool_id=tool.tool_id,
            capability=tool.capability,
            domain=domain,
            confidence=confidence,
            needs_review=(confidence != CONFIDENCE_EXACT),
            note=note,
        ))
    return results


def low_confidence(classifications) -> list[Classification]:
    """Return only the classifications that need human review."""
    return [c for c in classifications if c.needs_review]
