# Portfolio rationalisation agent: standing rules

- Synthetic or public data only. No real company inventory, prices, vendor or programme names.
- Every number is a range (low, base, high) with stated assumptions. All arithmetic is in code (`savings_range`), never by the model.
- Every recommendation cites the inventory rows it used and carries a confidence level.
- Tag each recommendation Two-Way Door (tier change, not renewing, licence reduction at renewal) or One-Way Door (hardware buy, multi-year commit, perpetual licence, decommissioning with no rollback), with blast radius.
- Never recommend retiring something a Must requirement depends on without flagging the dependency.
- evidence_level "claimed only" never counts as covering a requirement.
- Anything below the confidence threshold is "needs human review", not decided.
- Nothing is finalised without the human approval gate (step 7).
- The agent never edits the inventory; it only reads inputs and writes memo and log.
- A requirement with no owner or no measurable threshold is flagged, not guessed.
- The agent and its code must never read `answer_key/` (kept outside this folder).
- UK spelling, lean expert language.
