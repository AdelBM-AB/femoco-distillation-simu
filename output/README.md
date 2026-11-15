# The simulation results behind the |i⟩-distillation figures

Every Monte-Carlo result that `figures/femoco_paper/femoco_figures.ipynb` reads, and the circuits its tables
describe. Licensed under [CC BY 4.0](../LICENSES/CC-BY-4.0.txt).

## What was simulated

Every point is the transversal-CNOT |i⟩ distillation (`code_type=IStateCnot`) on the dense symmetric schedule
(`mode=cnot_dense_two_step_symmetric`): a triangular colour code of distance d_c coupled to an output repetition
code of distance d_r, with one Stab_Z round whose Bell-pair flags are measured and selected on
(`dstl_Zflag_selec=True`), under biased circuit-level noise of phase-flip probability p_z, decoded with
tesseract. k (`rep_prep_cycles`) is the number of repetition-code cycles run before the coupling; `None`, in
folders written before k was a parameter, means the derived count, which is 1 here.

## Layout

Each folder of `Results/` is one sweep:

- `simulation_manifest.json`: the parameters every point of the folder shares (`fixed_parameters`), what each
  parameter means (`parameter_descriptions`), and the templates that spell the others in each result's path
  (`sweep_file_structure`).
- `simulation_manifest.lock`: per point, a fingerprint of what was simulated (the detector error model, the
  postselection mask, the decoder), how its counts are read (`counts_schema`), and the versions of the code and
  packages that resolved it.
- `results.pack.json`: every result file of the folder, as one JSON tree (`pack_format: tree/1`). Directory keys
  end in `/`; the files `result_job=N.json` of a directory are one CSV table under the key `result_job=*.json`, a
  header row and one row per job. `distillation_simu.simu_lab.result_counts.load_counts` reads a folder into
  pooled counts per point; `paramsweep.packing.read_pack` gives back every file's original text.

One job's counts are `batch_size` shots, of which `accepted` passed every acceptance check and `accepted&fail`
were accepted with the distilled state wrong. The logical error rate is `accepted&fail / accepted`, the acceptance
`accepted / batch_size`. ⚠️ `fail` counts every shot with the distilled state wrong, rejected ones included: it is
not the failure count. `discards` are the shots the Bell flags rejected before decoding.

`261023 - rep bell pairs d_color 5` holds only its `rep_bell_pair_stabs=none` points here, in its pack and its
lock: the circuit every other d_c=5 folder ran. Its manifest describes the folder's whole layout.

`figures/femoco_paper/circuits/dc{d_c}_dr{d_r}.stim` are the noiseless k=1 circuits, in
[stim](https://github.com/quantumlib/Stim)'s format.

## Folders

Pooled over jobs; a point is one (d_c, d_r, k, p_z).

| folder | d_c | d_r | k | p_z | points | shots | accepted | failures |
|---|---|---|---|---|---|---|---|---|
| `261008 - rep prep cycles d_color 3` | 3 | 9 | 1, 2, 9 | 0.0005, 0.001, 0.0025, 0.005, 0.01 | 15 | 3.51e+10 | 3.41e+10 | 30304 |
| `261024 - rep code distance` | 3, 5 | 3, 5, 7, 9, 11 | 2, 4 | 0.0025 | 6 | 5.64e+10 | 4.08e+10 | 35236 |
| `260924 - dense with symmetric schedule/high pz` | 5 | 13 | – | 0.0025, 0.005, 0.01 | 3 | 3.22e+09 | 2.27e+09 | 589 |
| `260924 - dense with symmetric schedule/low pz` | 5 | 13 | – | 0.0005, 0.001, 0.0025 | 3 | 1.06e+11 | 9.84e+10 | 74 |
| `261002 - rep prep cycles d_color 5/high pz` | 5 | 13 | 2, 3, 4 | 0.001, 0.0025, 0.005, 0.01 | 12 | 2.83e+11 | 2.43e+11 | 1767 |
| `261002 - rep prep cycles d_color 5/pz 5e-4` | 5 | 13 | 4 | 0.0005 | 1 | 3.2e+12 | 3e+12 | 5 |
| `261002 - rep prep cycles d_color 5/high pz k 5-6` | 5 | 13 | 5, 6 | 0.0025, 0.005, 0.01 | 6 | 6.9e+10 | 4.87e+10 | 758 |
| `261002 - rep prep cycles d_color 5/high pz k 7` | 5 | 13 | 7 | 0.0025, 0.005, 0.01 | 3 | 4.34e+10 | 3.06e+10 | 411 |
| `261023 - rep bell pairs d_color 5` | 5 | 13 | 4 | 0.0025, 0.005, 0.01 | 3 | 2.56e+10 | 1.81e+10 | 441 |
| `260929 - dense with symmetric schedule d_color 7` | 7 | 19 | – | 0.0005, 0.001, 0.0025, 0.005, 0.01 | 5 | 2.94e+12 | 2.43e+12 | 1267 |
| `261002 - rep prep cycles d_color 7/high pz` | 7 | 19 | 3, 4, 5, 6 | 0.005, 0.0075, 0.01 | 12 | 1.68e+11 | 4.08e+10 | 1028 |
| `261002 - rep prep cycles d_color 7/high pz k 7-8` | 7 | 19 | 7, 8 | 0.005, 0.0075, 0.01 | 6 | 7.21e+11 | 1.88e+11 | 332 |
| `261002 - rep prep cycles d_color 7/high pz k 10` | 7 | 19 | 10 | 0.005, 0.0075, 0.01 | 3 | 5.44e+11 | 1.4e+11 | 175 |
| `261002 - rep prep cycles d_color 7/pz 2.5e-3 k 8` | 7 | 19 | 8 | 0.0025 | 1 | 1.06e+12 | 5.68e+11 | 0 |
| `261002 - rep prep cycles d_color 7/pz 2.5e-3 k 8 part 2` | 7 | 19 | 8 | 0.0025 | 1 | 9.4e+11 | 5.02e+11 | 1 |
| `261002 - rep prep cycles d_color 7/pz 5e-4` | 7 | 19 | 4 | 0.0005 | 1 | 3.6e+12 | 3.18e+12 | 0 |
| `261002 - rep prep cycles d_color 7/pz 1e-3` | 7 | 19 | 4 | 0.001 | 1 | 2e+12 | 1.56e+12 | 1 |
| `260930 - dense with symmetric schedule d_color 9` | 9 | 19 | – | 0.005, 0.0075, 0.01 | 3 | 8.5e+11 | 8.71e+10 | 324 |
| `261012 - rep prep cycles d_color 9/high pz` | 9 | 19 | 2, 3, 4 | 0.005, 0.0075, 0.01 | 9 | 3.28e+12 | 2.89e+11 | 1089 |
