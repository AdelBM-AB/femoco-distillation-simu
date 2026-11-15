"""Path layouts: where each result of a sweep lives, written down so it can be read back.

A ``ResultNamingConvention`` is two ``str.format`` templates, a directory and a filename, plus what
each placeholder means. Plain templates rather than code, so a manifest can store them in the results
folder itself. A convention formats a relative path from field values and parses one back. It does
no I/O: walking a folder is ``ExperimentTypeManifest.discover_points``.

Conventions are written out (``make_convention``), generated from a list of fields
(``make_derived_convention``), or derived from what a sweep varies (``naming_from_sweep``). Anything
that accepts a layout takes a ``Naming``: one convention, a mapping from discriminator value to
convention, or a factory. ``as_factory`` reduces all three to the factory.
"""

from __future__ import annotations

import functools
import glob
import re
from dataclasses import dataclass, field
from string import Formatter
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Union,
)

from paramsweep.values import to_path_str

if TYPE_CHECKING:  # only for annotations: this module needs nothing of a point but parameters()
    from paramsweep.points import AbstractSweepPoint


def placeholders_in(*templates: str) -> List[str]:
    """The ``{placeholder}`` names appearing in the given templates, in order, without repeats."""
    seen: List[str] = []
    for template in templates:
        for _, name, _, _ in Formatter().parse(template):
            if name and name not in seen:
                seen.append(name)
    return seen


def is_collection(value: Any) -> bool:
    """Whether a filter value lists several allowed values rather than being one."""
    return isinstance(value, (list, tuple, set, frozenset))


@functools.lru_cache(maxsize=256)
def _compile(template: str) -> Tuple[re.Pattern, Tuple[Tuple[str, Tuple[str, ...]], ...]]:
    """The regex capturing each placeholder of ``template``, and the regex groups of each field.

    A field used twice gets a group per occurrence; ``_match`` reconciles them.
    """
    parts: List[str] = []
    groups: Dict[str, List[str]] = {}
    for literal, name, _, _ in Formatter().parse(template):
        parts.append(re.escape(literal))
        if not name:
            continue
        occurrences = groups.setdefault(name, [])
        group = name if not occurrences else f"{name}__{len(occurrences) + 1}"
        occurrences.append(group)
        parts.append(f"(?P<{group}>[^/]+?)")
    return re.compile("".join(parts)), tuple((k, tuple(v)) for k, v in groups.items())


def _match(template: str, text: str) -> Optional[Dict[str, str]]:
    """Every placeholder's value in ``text``, or None if ``text`` does not follow ``template``."""
    pattern, groups = _compile(template)
    match = pattern.fullmatch(text)
    if match is None:
        return None
    fields: Dict[str, str] = {}
    for name, group_names in groups:
        values = {match.group(group) for group in group_names}
        if len(values) > 1:
            raise ValueError(
                f"field {name!r} appears more than once in {template!r}, with conflicting values "
                f"{sorted(values)} in {text!r}"
            )
        fields[name] = values.pop()
    return fields


@dataclass(frozen=True)
class ResultNamingConvention:
    """Where a result lives: a directory template and a filename template, plus what each
    placeholder means.

    Field values are not checked against any parameter here -- ``ExperimentTypeManifest.path_for``
    formats from a point, which is the safe way to build a result's path.
    """

    dir_template: str
    file_template: str
    field_descriptions: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        missing = [name for name in self.fields_in_templates() if name not in self.field_descriptions]
        if self.field_descriptions and missing:
            raise ValueError(f"no description given for placeholder(s) {missing}")

    def fields_in_templates(self) -> List[str]:
        """Every placeholder appearing in either template, directory template first."""
        return placeholders_in(self.dir_template, self.file_template)

    @property
    def template(self) -> str:
        """The whole relative path, directory and filename, as one template."""
        return f"{self.dir_template}/{self.file_template}"

    def format(self, **fields: Any) -> str:
        """The relative path of a result with these field values."""
        return self.template.format(**{k: to_path_str(v) for k, v in fields.items()})

    def format_dir(self, **fields: Any) -> str:
        """The relative directory of a result with these field values."""
        return self.dir_template.format(**{k: to_path_str(v) for k, v in fields.items()})

    def parse(self, rel_path: str) -> Optional[Dict[str, str]]:
        """Every placeholder's value in a relative result path, as text; None if it is not one."""
        return _match(self.template, rel_path)

    def parse_dir(self, rel_dir: str) -> Optional[Dict[str, str]]:
        """Every directory placeholder's value in a relative directory, as text."""
        return _match(self.dir_template, rel_dir)

    def glob(self, **pinned: Any) -> str:
        """A glob matching every result path, narrowed to the fields ``pinned`` to one value.

        Looser than ``parse``: it is what keeps a walk inside the right directories, and ``parse``
        is what decides.
        """
        parts: List[str] = []
        for literal, name, _, _ in Formatter().parse(self.template):
            parts.append(glob.escape(literal))
            if name:
                parts.append(glob.escape(to_path_str(pinned[name])) if name in pinned else "*")
        return "".join(parts)


def make_convention(
    *, dir_template: str, file_template: str, known: Mapping[str, str]
) -> ResultNamingConvention:
    """Build a naming convention whose ``field_descriptions`` come from ``known``.

    Every placeholder must be a name ``known`` describes, so a typo like ``{round}`` fails here
    rather than producing results nobody can read back. ``known`` is normally every parameter some
    point may carry plus the path-only fields; whether a placeholder is right *for a given
    experiment type* is ``ExperimentTypeManifest.validate``'s job.
    """
    placeholders = placeholders_in(dir_template, file_template)
    unknown = sorted(set(placeholders) - set(known))
    if unknown:
        raise ValueError(
            f"template placeholder(s) {unknown} are not known parameters; known: {sorted(known)}"
        )
    return ResultNamingConvention(
        dir_template=dir_template,
        file_template=file_template,
        field_descriptions={name: known[name] for name in placeholders},
    )


def make_derived_convention(
    *,
    dir_fields: Sequence[str],
    file_fields: Sequence[str],
    known: Mapping[str, str],
    stem: str = "result",
    suffix: str = ".json",
) -> ResultNamingConvention:
    """Build a convention from a *list of fields* rather than hand-written templates.

    One ``name=value`` directory level per name in ``dir_fields``, and a filename of
    ``stem`` followed by one ``_name=value`` part per name in ``file_fields``::

        dir_fields=["kind", "rows"], file_fields=["repeat"]
        -> "kind={kind}/rows={rows}", "result_repeat={repeat}.json"

    Each field is labelled with its own name, so a path says what it means on its own -- which is
    what lets a layout follow whatever a sweep varies, where an unlabelled positional layout like
    ``run_{momentum}_{repeat}.json`` needs its field list known in advance.
    """
    if not dir_fields:
        raise ValueError(
            "dir_fields is empty, which would make an empty directory template; name at least one "
            "field to put a level under (an experiment type's discriminator, say)"
        )
    if not file_fields:
        raise ValueError(
            "file_fields is empty, so every point of a directory would write to one filename; name "
            "at least one per-file field (a repetition index, say)"
        )
    names = (*dir_fields, *file_fields)
    repeated = sorted({name for name in names if names.count(name) > 1})
    if repeated:
        raise ValueError(
            f"field(s) {repeated} appear more than once across dir_fields and file_fields; a "
            f"placeholder used twice cannot be parsed back out of a path"
        )
    return make_convention(
        dir_template="/".join(f"{name}={{{name}}}" for name in dir_fields),
        file_template=stem + "".join(f"_{name}={{{name}}}" for name in file_fields) + suffix,
        known=known,
    )


# ---------------------------------------------------------------------------- layouts of a sweep

# Builds an experiment type's convention from the type itself and the points swept over it.
ConventionFactory = Callable[
    [Mapping[str, Any], Sequence["AbstractSweepPoint"]], ResultNamingConvention
]

# What a layout may be given as: one convention for every experiment type, one per discriminator
# value, or a factory deriving one per experiment type.
Naming = Union[ResultNamingConvention, Mapping[Any, ResultNamingConvention], ConventionFactory]


def as_factory(naming: Naming) -> ConventionFactory:
    """``naming`` in its one general form: a factory from an experiment type and its points.

    A single convention names every type; a mapping is keyed by a discriminator value, e.g.
    ``{OptimiserKind.ADAM: ADAM_CONVENTION}``, and must select exactly one convention per type.
    """
    if isinstance(naming, ResultNamingConvention):
        return lambda experiment_type, points: naming
    if callable(naming):
        return naming
    by_value = dict(naming)

    def lookup(
        experiment_type: Mapping[str, Any], points: Sequence["AbstractSweepPoint"]
    ) -> ResultNamingConvention:
        spelled = {to_path_str(value) for value in experiment_type.values()}
        matches = [key for key in by_value if to_path_str(key) in spelled]
        if len(matches) != 1:
            raise ValueError(
                f"experiment type {dict(experiment_type)} matches {len(matches)} naming "
                f"conventions ({sorted(map(to_path_str, matches))}); a mapping keyed by "
                f"{sorted(map(to_path_str, by_value))} must select exactly one"
            )
        return by_value[matches[0]]

    return lookup


def varying_in(points: Sequence["AbstractSweepPoint"]) -> List[str]:
    """The parameters that take more than one value across ``points`` -- exactly the ones a result
    path has to encode, since points agreeing on all the others would otherwise share a file.

    In the points' own parameter order (slot, then field declaration), so a layout derived from it
    depends on the sweep alone.
    """
    if not points:
        return []
    per_point = [point.parameters() for point in points]
    return [name for name in per_point[0] if len({p[name] for p in per_point}) > 1]


def naming_from_sweep(
    *,
    known: Mapping[str, str],
    per_file: Sequence[str] = (),
    also: Sequence[str] = (),
    stem: str = "result",
    suffix: str = ".json",
) -> ConventionFactory:
    """A ``naming`` that derives each experiment type's convention from what its sweep varies::

        SweepManifest.from_points(points, naming=naming_from_sweep(known=..., per_file=["repeat"]))

    One ``name=value`` directory level per field, in this order:

    - every discriminator of the experiment type -- constant within a type, but what keeps two
      *types* from colliding on one filename whenever their varying parameters coincide;
    - every parameter that varies across the sweep;
    - anything named in ``also``: a parameter constant in this sweep pinned into the path anyway,
      which is how the trees of two runs stay mergeable. Like a ``grid`` axis, it applies to the
      experiment types that carry it, and is left out of the others' paths.

    ``per_file`` names the fields that go in the filename instead (a repetition index, say).
    """
    unknown = sorted(set(also) - set(known))
    if unknown:
        raise ValueError(f"also names {unknown}, which are not known parameters")

    def factory(
        experiment_type: Mapping[str, Any], points: Sequence["AbstractSweepPoint"]
    ) -> ResultNamingConvention:
        carried = points[0].parameters() if points else {}
        wanted = [*varying_in(points), *(name for name in also if name in carried)]
        return make_derived_convention(
            dir_fields=[
                *experiment_type,
                *dict.fromkeys(
                    name for name in wanted if name not in experiment_type and name not in per_file
                ),
            ],
            file_fields=list(per_file),
            known=known,
            stem=stem,
            suffix=suffix,
        )

    return factory
