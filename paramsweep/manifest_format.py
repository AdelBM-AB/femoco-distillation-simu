"""A manifest file's JSON format, without the typed machinery that validates it against a point class.

Split out of ``paramsweep.manifest`` so that reading a results folder's layout -- the templates and
the recorded parameters, as ``paramsweep.raw_results`` does -- needs no point class and nothing but
the standard library. ``paramsweep.manifest`` re-exports all of it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping

# Spellings used early in version 4, before the rename: current name -> the name it replaced.
_V4_EARLY_KEYS = {"experiment_type": "shape", "experiment_types": "shapes"}


def _respelled(d: Mapping[str, Any]) -> Dict[str, Any]:
    renamed = dict(d)
    for current, early in _V4_EARLY_KEYS.items():
        if early in renamed and current not in renamed:
            renamed[current] = renamed.pop(early)
    return renamed


def upgrade_format(d: Mapping[str, Any]) -> Dict[str, Any]:
    """A manifest file's JSON, as written by any version, in the current format -- unvalidated.

    - version 3 and earlier: a single experiment type's manifest, with no envelope -- wrapped in one;
    - version 4, early: ``shapes``/``shape`` for ``experiment_types``/``experiment_type``.

    Only the file *format*. Parameters renamed since a folder was written are
    ``paramsweep.migration``'s business: the format reads without knowing the parameters.
    """
    d = _respelled(d)
    if "experiment_types" not in d:
        d = {"version": d["version"], "experiment_types": [d]}
    return {**d, "experiment_types": [_respelled(entry) for entry in d["experiment_types"]]}


def read_manifest_json(path: Path) -> Dict[str, Any]:
    """The manifest file at ``path``, in the current format (``upgrade_format``), not validated."""
    with open(path, encoding="utf-8") as f:
        return upgrade_format(json.load(f))
