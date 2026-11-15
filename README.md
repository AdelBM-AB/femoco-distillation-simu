# femoco-distillation-simu

The simulation results behind the |i⟩-state distillation appendix of

> L. Kroell, H. Jacinto, V. Hertz, A. Pappalardo, A. Ben Moussa, M. Rispler, P. Shanahan, É. Gouzien, C. Vuillot,
> V. Londe, *Ground-state energy estimation compiled on cat qubits: 7 164 qubits for FeMoco-54 in 23.5 hours*,
> [arXiv:2610.37840](https://arxiv.org/abs/2610.37840) (2026).

and the notebook that turns them into that appendix's figures and tables.

> [!NOTE]
> This first release holds only the raw Monte-Carlo simulation results and the code that reads them.
> The code that builds the circuits, the postselection masks and runs the simulations will be included **in a later release**.
> We will also probably take this occasion to simplify some parameter names.

## Contents

```
output/figures/femoco_paper/
├── femoco_figures.ipynb       every figure and table of the appendix, from the data below
├── circuits/*.stim            the noiseless short-protocol circuits from Table II/a
├── statistical_hypotheses.md  the statistical assumptions behind every interpretation we make of the Monte-Carlo simulation results, with references
└── *.pdf, *.tex               the notebook's outputs, as they appear in the paper
output/Results/                the Monte-Carlo results, one folder per sweep; see output/README.md
distillation_simu/             the code the notebook imports: reading the results, Poisson confidence limits, power-law fits
paramsweep/                    the generic code taking care of result packs and manifests
```

The (human) reader interested in knowing a bit more about the simulation results used in the Femoco paper is encouraged to read `statistical_hypotheses.md` and `femoco_figures.ipynb`.

## Running the notebook

With [pixi](https://pixi.sh), from the repository root:

```bash
pixi install       # Python 3.13 from conda-forge, the dependencies, this package (editable)
pixi run figures   # executes the notebook in place
pixi run lab       # or opens it in JupyterLab
```

Or with pip, Python 3.11 or later:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
jupyter nbconvert --to notebook --execute --inplace output/figures/femoco_paper/femoco_figures.ipynb
```

or open it with `jupyter lab`. Either way, it rewrites the `.pdf` and `.tex` files next to it. They should come out identical
to the ones committed here, up to the PDFs' creation timestamps.

## Reading the data

[`output/README.md`](output/README.md) describes what was simulated, the file formats and every folder. 
In short, to have Python read raw results from the folder "261008 - rep prep cycles d_color 3", use:

```python
from distillation_simu.paths import OUTPUT_DIR
from distillation_simu.simu_lab.result_counts import load_counts

counts = load_counts(OUTPUT_DIR / "Results" / "261008 - rep prep cycles d_color 3")
for key, (failures, accepted, shots) in counts.items():
    point = dict(key)  # d_color, d, rep_prep_cycles, pz, ...
    print(point["d_color"], point["rep_prep_cycles"], point["pz"], failures / accepted, accepted / shots)
```

[`statistical_hypotheses.md`](output/figures/femoco_paper/statistical_hypotheses.md) explains how we turned such counts into
estimates, confidence intervals (exact Poisson, or the bound for zero failures) and power-law fits. The functions
doing it are in
[`distillation_simu/common/statistics.py`](distillation_simu/common/statistics.py).

## Citing

If you use these results or this code, please cite the paper above. [`CITATION.cff`](CITATION.cff) has the
details, and GitHub's "Cite this repository" button reads it.

## Licence
This repository's code is distributed under the MIT license.
Raw data and figures are protected by Creative Commons. 
More specifically:

| what | licence |
|---|---|
| code: `distillation_simu/`, `paramsweep/`, the notebook | [MIT](LICENSES/MIT.txt) |
| data and figures: `output/Results/`, `output/README.md`, `output/figures/femoco_paper/circuits/`, `*.pdf`, `*.tex`, `*.md` | [CC BY 4.0](LICENSES/CC-BY-4.0.txt) |

[`REUSE.toml`](REUSE.toml) states the same per path, in the [REUSE](https://reuse.software) format.
