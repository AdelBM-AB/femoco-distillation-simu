"""Pooled counts per sweep point, read from results folders without the sweep vocabulary.

``read_simu.load_failure_counts`` / ``load_shot_counts`` give the same numbers keyed by typed
``SweepPoint``s, and importing them pulls in stim, sinter, a decoder and every construction. This
reads the folders through their manifest *files* (``paramsweep.raw_results``) and the result-file
schema (``core.result_schema``) alone -- standard library, ``paramsweep`` and nothing else -- which
is what lets the Femoco figures notebook run, and ship, without the simulation code.

A point is a plain ``dict`` of parameters, as recorded or as spelled in the path (see
``paramsweep.raw_results.coerce``). ``tests/test_result_counts.py`` holds both readers to the same
counts on every folder the Femoco notebook reads.
"""

from __future__ import annotations

import json
import warnings
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Tuple, Union

from distillation_simu.core.result_schema import JobCounts, job_counts, schema_for_mode
from paramsweep.raw_results import iter_raw_results

MANIFEST_FILENAME = "simulation_manifest.json"  # SweepManifest.FILENAME, without importing it

# The monte_carlo slot's fields: how a point was run, not what it simulates. Pooling drops them,
# as read_simu's ignore_runtime_only=True does, so jobs and folders of one point add up.
RUNTIME_ONLY = frozenset({"shots_per_task", "nb_jobs", "max_batch_size", "max_batch_seconds"})
# Path-only fields: which file of a point this is.
PATH_ONLY = frozenset({"job"})

PointKey = Tuple[Tuple[str, Any], ...]


def point_key(parameters: Mapping[str, Any]) -> PointKey:
    """A hashable, order-free key for a point: its parameters without the runtime-only ones."""
    return tuple(sorted((name, value) for name, value in parameters.items()
                        if name not in RUNTIME_ONLY | PATH_ONLY))


def load_counts(folders: Union[Path, Iterable[Path]]) -> Dict[PointKey, JobCounts]:
    """``(failures, accepted, shots)`` per point, pooled over jobs and folders.

    Keys are ``point_key``s; ``dict(key)`` gives the parameters back. A preselection point is read
    at the level it ran (its ``preselection_rounds``). Points with no shot at all are left out, and
    a file that does not parse -- fetched while still being written -- is skipped with a warning,
    as ``read_simu`` does.
    """
    folders = [Path(folders)] if isinstance(folders, (str, Path)) else [Path(f) for f in folders]
    pooled: Dict[PointKey, List[int]] = defaultdict(lambda: [0, 0, 0])
    unreadable: List[str] = []
    for folder in folders:
        for result in iter_raw_results(folder, MANIFEST_FILENAME):
            try:
                counts = json.loads(result.read_text())
            except ValueError:
                unreadable.append(f"{folder}/{result.rel_path}")
                continue
            parameters = result.parameters
            one = job_counts(counts, schema_for_mode(str(parameters["mode"])),
                             parameters.get("preselection_rounds"))
            entry = pooled[point_key(parameters)]
            for i, n in enumerate(one):
                entry[i] += n
    if unreadable:
        warnings.warn(
            f"skipped {len(unreadable)} unreadable result file(s), most likely fetched while the "
            f"sweep was still writing them; re-fetch once it has finished. e.g.\n  "
            + "\n  ".join(unreadable[:3]),
            stacklevel=2,
        )
    return {key: JobCounts(*entry) for key, entry in pooled.items() if entry[2] != 0}
