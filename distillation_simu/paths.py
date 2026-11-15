"""Package-anchored paths for the package's data files, and for everything it writes.

Anchoring to this module's own location (rather than a script's SCRIPT_DIR or
the process cwd) keeps these paths valid no matter where a script, notebook,
or test imports distillation_simu.core from.

Note the two anchors. Inputs sit under PACKAGE_DIR, inside the package. Output goes to
OUTPUT_DIR, which hangs off REPO_ROOT and is a *sibling* of the package -- see RESULTS_DIR.
"""

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
CORE_DIR = PACKAGE_DIR / "core"
REPO_ROOT = PACKAGE_DIR.parent
OUTPUT_DIR = REPO_ROOT / "output"
ASSETS_DIR = OUTPUT_DIR / "assets"

# Script-generated figures -- kept separate from ASSETS_DIR, whose existing occupants are inputs
# the code reads, not output it writes.
FIGURES_DIR = OUTPUT_DIR / "figures"

# The results archive: one folder per run, named "YYMMDD - what the run is for", each holding its
# own simulation_manifest.json, a read_results.ipynb and a README.md saying what it is.
#
# Anchored off OUTPUT_DIR, never off PACKAGE_DIR, and that is the whole point: `output/` is a git
# repository of its own (gitlab.int.alice-bob.com/adel.benmoussa/distillation_simu_output), ignored
# wholesale by this repo's .gitignore. Runs are versioned and shared there. Every sweep before
# 2026-09-10 anchored its output off PACKAGE_DIR instead, so a bare name typed in simu_lab/simu_input.py
# landed inside the code tree -- which is how ten Results* trees came to live in distillation_simu/.
RESULTS_DIR = OUTPUT_DIR / "Results"

# Where the circuit-level diagnostics write their reports -- `simu_lab/count_fatal_paths.py` today.
# Under `output/`, which is the results repo, rather than beside the code: a report is a
# measurement of a circuit, same as a sweep, and belongs where measurements are versioned.
# (`simu_lab/explain_errors.py` predates this and still defaults to PACKAGE_DIR / "ErrorAnalysis";
# moving its nine existing reports is a separate, deliberate change.)
ERROR_ANALYSIS_DIR = OUTPUT_DIR / "error_analysis"

SAT_GENERATED_QEC_DIR = ASSETS_DIR / "SAT_generated_qec"

UNFOLDED_CODE_D9_JSON = SAT_GENERATED_QEC_DIR / "UnfoldedCode_d=9.json"
UNFOLDED_CODE_D11_JSON = SAT_GENERATED_QEC_DIR / "UnfoldedCode_d=11.json"
MEAN_ROUNDS_NPY = ASSETS_DIR / "Mean_rounds.npy"

# Mean-number-of-rounds tables written by `simu_lab/mean_number_of_rounds.py`, one .npy per parameter
# set, named after it. Kept apart from MEAN_ROUNDS_NPY, Diego's single table, which is never
# overwritten.
MEAN_NUMBER_RESULTS_DIR = OUTPUT_DIR / "Mean_number_results"

# The color-code-stim submodule, checked out beside this package rather than installed.
# core/color_code.py is the only importer; see its import_tanner_graph_builder for why the
# path is anchored here instead of being handled by PYTHONPATH.
COLOR_CODE_STIM_SRC = REPO_ROOT / "color-code-stim" / "src"


def sweep_dir(name: str) -> Path:
    """The folder ONE sweep writes into: a single named child of RESULTS_DIR.

    Takes a *name*, not a path, so a sweep's output directory cannot be re-anchored somewhere
    else by accident. Follow the archive convention: "260910 - what this run is for".
    """
    if not name or name in (".", "..") or "/" in name or "\\" in name:
        raise ValueError(
            f"a sweep folder name is one path segment under {RESULTS_DIR}, got {name!r}"
        )
    return RESULTS_DIR / name


def check_sweep_dir(path: Path) -> Path:
    """Raise unless *path* is one sweep's folder under RESULTS_DIR. Returns *path* unchanged.

    Two failures, one check. A tree written outside the archive is invisible to the output repo
    and pollutes the code tree. And RESULTS_DIR *itself* is the archive root, not a run folder --
    writing a sweep there would drop its simulation_manifest.json and its whole result tree in
    among every other run's folder.
    """
    resolved = Path(path).resolve()
    root = RESULTS_DIR.resolve()
    if resolved == root or not resolved.is_relative_to(root):
        raise ValueError(
            f"{path} is not a sweep folder under {RESULTS_DIR}. Results belong in the archive, "
            f"one folder per run: use paths.sweep_dir('260910 - what this run is for')."
        )
    return path
