"""A results folder read back without its point class: parameters as plain values, files as text.

``SweepManifest.discover_points`` turns every result into a typed point, which needs the code that
declares the point class -- and with it whatever that code imports. This module reads the same
folder through the manifest *file* alone: each experiment type's recorded ``experiment_type`` and
``fixed_parameters``, plus whatever its templates encode in the result's path. No vocabulary is
checked, so a value is only as typed as JSON (for recorded values) or ``coerce`` (for path text)
makes it, and a parameter renamed since the folder was written comes back under its old name.

Use it where a reader must stand on its own -- a published dataset's notebook, a script outside the
project. Inside the project, prefer ``discover_points``: it validates.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, Mapping, Optional

from paramsweep.manifest_format import read_manifest_json
from paramsweep.naming import ResultNamingConvention
from paramsweep.packing import PackEntry, iter_result_paths
from paramsweep.values import to_path_str


def coerce(text: str) -> Any:
    """A path field's text as the value it most plausibly spells: None, a bool, an int, a float, or
    the text itself. ``to_path_str`` is what wrote it, so ``None``, ``True`` and ``False`` are
    Python's spellings.

    <!> A guess, by construction: without the point class nothing says which type a parameter has,
    so a string parameter whose value reads as a number (``"1"``, ``"1e-3"``) comes back as that
    number. Compare such parameters through ``to_path_str``, which spells both the same."""
    if text == "None":
        return None
    if text in ("True", "False"):
        return text == "True"
    for parse in (int, float):
        try:
            return parse(text)
        except ValueError:
            pass
    return text


@dataclass(frozen=True)
class RawResult:
    """One result file: every parameter it was produced at, where it is, and how to read it."""

    parameters: Mapping[str, Any]
    rel_path: str
    folder: Path
    pack: Optional[PackEntry]

    def read_text(self) -> str:
        if self.pack is not None:
            return self.pack.read_text()
        return (self.folder / self.rel_path).read_text(encoding="utf-8")


def iter_raw_results(folder: Path, manifest_filename: str) -> Iterator[RawResult]:
    """Every result under ``folder``, from every experiment type its manifest describes.

    ``manifest_filename`` is the adopter's ``SweepManifest.FILENAME``: the file at the folder's root.

    A result's ``parameters`` are its type's ``experiment_type`` and ``fixed_parameters`` (as
    recorded, JSON-typed) and every field of its path (``coerce``d), path-only ones such as a job
    index included. A path that a type's templates do not parse, or that names another type's
    discriminator values, is not that type's.
    """
    folder = Path(folder)
    manifest = read_manifest_json(folder / manifest_filename)
    for entry in manifest["experiment_types"]:
        experiment_type: Dict[str, Any] = dict(entry["experiment_type"])
        fixed: Dict[str, Any] = dict(entry.get("fixed_parameters", {}))
        structure = entry["sweep_file_structure"]
        convention = ResultNamingConvention(structure["dir_template"], structure["file_template"])
        placeholders = set(convention.fields_in_templates())
        # Pinning the discriminators keeps the walk inside this type's own directories.
        pinned = {name: value for name, value in experiment_type.items() if name in placeholders}
        for rel_path, pack in iter_result_paths(folder, convention.glob(**pinned)):
            fields = convention.parse(rel_path)
            if fields is None or any(fields[name] != to_path_str(value) for name, value in pinned.items()):
                continue
            parameters = {**experiment_type, **fixed,
                          **{name: coerce(text) for name, text in fields.items() if name not in pinned}}
            yield RawResult(parameters=parameters, rel_path=rel_path, folder=folder, pack=pack)
