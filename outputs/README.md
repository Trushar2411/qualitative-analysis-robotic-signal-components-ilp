# xArm analysis results

Historical results are retained in `OLD/`. New analyses write separate timestamped
runs or batches under the following folders:

| Folder | Generator | Results |
|---|---|---|
| `PLA/` | `piecewise_linear_approximation_velocity.py` | Velocity PLA CSVs and per-joint plots |
| `PLA_position/` | `pla_joint_position.py` | Position PLA CSVs, per-joint plots, and joint overview |
| `SWEE/` | `sliding_window_effort_energy.py` | Effort energy CSVs and plots |
| `PLA_velocity_effort/` | `pla_velocity_effort_all_runs.py` | Combined batches of velocity/effort PLA and phase-shaded plots |

The generators are in `scripts/analysis/` and read per-joint files in
`Processed data/`. The default searches do not recurse into `OLD/`; pass
`--processed-run` to analyze a specific archived run.

PLA labels a fitted signal change as `ramp_up`, `ramp_down`, or `constant`.
SWEE labels effort-window energy using its configured thresholds. Effort energy
and effort trend are different features. Preserve the script parameters and
source run when comparing their Popper rules. A phase summary can conceal
mixed trends within a phase; inspect the window CSVs alongside summaries.

Franka results are stored separately under `FrankaReplay/outputs/`.
