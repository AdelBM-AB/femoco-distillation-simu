"""Sweeping over parameterised dataclasses, and keeping the results readable afterwards.

Three things, in order:

1. **Describe a unit of work.** A *point* is a frozen dataclass composed of *slots*; each slot is
   filled by one of several interchangeable ``ParameterGroup`` *variants*, which need not accept the
   same parameters. Every field declares its own description and string parser via ``parameter()``,
   which is the single source of truth everything below reads.
2. **Sweep.** ``grid()`` is the cartesian product at a fixed *shape* (the variant filling each slot);
   sweeping a slot's *discriminator* sweeps over variants, so an uneven parameter space comes out as
   the union of even sub-grids.
3. **Materialise it, reversibly.** A naming convention turns a point into a path; a manifest records
   what a results folder was produced from, so a directory of files stays interpretable without the
   code that wrote it -- and ``discover_points`` walks it back into typed points. The convention can
   be written out or derived from the sweep (``naming_from_sweep``), which is what lets a new axis be
   swept without a template being hand-written to encode it.

Modules, in dependency order -- import them directly, this package deliberately re-exports nothing:

- ``paramsweep.values``     -- ``jsonable``, ``to_path_str``, ``parse_bool``, ``optional``: how a
  value is stored, and the parsers that read it back
- ``paramsweep.parameters`` -- ``parameter``, ``ParameterGroup``, ``ParameterSlot``
- ``paramsweep.points``     -- ``AbstractSweepPoint``
- ``paramsweep.packing``    -- ``write_pack``, ``read_pack``, ``iter_result_paths``, ``atomic_open``,
  ``RESULTS_PACK`` -- many small result files kept as one JSON tree, and atomic writes
- ``paramsweep.naming``     -- ``ResultNamingConvention`` (format and parse a path),
  ``make_convention``, ``make_derived_convention``, ``naming_from_sweep``, ``as_factory``
- ``paramsweep.manifest_format`` -- ``upgrade_format``, ``read_manifest_json``: a manifest file's JSON,
  read without a point class
- ``paramsweep.raw_results`` -- ``iter_raw_results``: a results folder read back without its point
  class, parameters as plain values -- for readers that must stand on their own
- ``paramsweep.manifest``   -- ``SweepManifest`` and its generated ``ExperimentType``,
  ``DiscoveredResult``
- ``paramsweep.migration``  -- bringing a folder written under an older vocabulary or layout up to
  date: the reforms (``rename``, ``recode``, ``drop``, ``set_default``, ``custom``),
  ``plan_migration``, ``apply_migration``

Depends on nothing but the standard library and numpy; ``paramsweep/tests/test_independence.py``
enforces that, and ``paramsweep/tests/toy.py`` is a worked example of adopting it.
"""
