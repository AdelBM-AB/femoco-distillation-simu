"""What one result file holds: its counts, read the one way every reader must read them.

Light on purpose -- standard library only at import -- so a reader of archived results (the Femoco
figures notebook and its release) can count failures, accepted shots and shots without the sweep
vocabulary, which imports sinter and a decoder at module scope. ``counts_schema(point)`` is the one
function here that needs that vocabulary, and imports it only when called.

A result file is one of three schemas, named as ``simulation_manifest.lock`` pins them
(``counts_schema``), and written by ``core/sinter_util.counts_for``:

| schema         | failures                           | accepted                      | shots            |
|----------------|------------------------------------|-------------------------------|------------------|
| ``preselection`` | ``preselected&accepted&fail[k]`` | ``preselected&accepted[k]``   | ``sum(shots_total)`` |
| ``modified``   | ``accepted&fail``                  | ``accepted``                  | ``batch_size``   |
| ``cnot``       | ``accepted&fail``                  | ``accepted``                  | ``batch_size``   |

<!> ``fail`` is **not** the failure count: it counts every shot whose magic observable came out
wrong, rejected shots included. The logical error rate is ``accepted&fail / accepted``.

A preselection file holds one list entry per preselection level, of which the run filled index
``k = preselection_rounds``; a level past the list's end contributes nothing. ``shots`` sums the
list, which is that one entry whatever level the file is read back at.
"""

from __future__ import annotations

from typing import Any, Mapping, NamedTuple, Optional

SCHEMAS = ("preselection", "modified", "cnot")


class JobCounts(NamedTuple):
    failures: int
    accepted: int
    shots: int


def schema_for_mode(mode: str) -> str:
    """The schema a point of protocol ``mode`` (``ProtocolModeType``'s value) writes."""
    if mode in ("preselection", "modified"):
        return mode
    if mode.startswith("cnot_"):
        return "cnot"
    raise ValueError(f"no result schema known for protocol mode {mode!r}")


def counts_schema(point) -> str:
    """The schema ``point`` writes, from its protocol's class -- what the lock pins."""
    from distillation_simu.core.parameters import (
        ACnotProtocolParams,
        RuizModifiedProtocolParams,
        RuizProtocolParams,
    )

    match point.protocol:
        case RuizProtocolParams():
            return "preselection"
        case RuizModifiedProtocolParams():
            return "modified"
        case ACnotProtocolParams():
            return "cnot"
    raise ValueError(f"no counts schema for {type(point.protocol).__name__}")


def _shot_field(counts: Mapping[str, Any], field: str, schema: str) -> Any:
    # Raises rather than defaulting to 0: a 0 here would claim the file is empty, which reads
    # downstream as a starved point -- a hard 0.0 with a 0.0 error bar.
    if field not in counts:
        raise ValueError(
            f"{schema} result file has no {field!r}; its keys are {sorted(counts)}. Every tree in "
            f"the archive records it, so this file was either written by something else or truncated."
        )
    return counts[field]


def shots_in(counts: Mapping[str, Any], schema: str) -> int:
    """How many shots a result payload holds, discarded ones included."""
    if schema == "preselection":
        return int(sum(_shot_field(counts, "shots_total", schema)))
    if schema in ("modified", "cnot"):
        return int(_shot_field(counts, "batch_size", schema))
    raise ValueError(f"no result schema {schema!r}; known: {SCHEMAS}")


def job_counts(counts: Mapping[str, Any], schema: str,
               preselection_rounds: Optional[int] = None) -> JobCounts:
    """One result file's ``(failures, accepted, shots)``.

    ``preselection_rounds`` is the level a preselection file is read at, and is required for that
    schema only.
    """
    shots = shots_in(counts, schema)
    if schema == "preselection":
        if preselection_rounds is None:
            raise ValueError("a preselection result is read at a level: pass preselection_rounds")
        k = preselection_rounds
        if k < len(counts["preselected&accepted&fail"]):
            return JobCounts(int(counts["preselected&accepted&fail"][k]),
                             int(counts["preselected&accepted"][k]), shots)
        return JobCounts(0, 0, shots)
    return JobCounts(int(counts["accepted&fail"]), int(counts["accepted"]), shots)
