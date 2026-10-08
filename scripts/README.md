# xArm scripts

Run the commands below from the repository root, with the analysis dependencies
installed. Collection scripts also require a running ROS2/xArm setup.

| Script | Input and behavior |
|---|---|
| `data_collection/real_robot_pick_and_place_recorder.py` | Executes the configured real-robot sequence and records ROS joint states and phases under `Raw data/` |
| `data_collection/simulated_pick_and_place_recorder.py` | Publishes trajectories to configured simulation controllers and records a ROS bag |
| `preprocessing/create_joint_processed_data.py` | Splits one raw full-motion CSV into six per-joint CSVs |
| `preprocessing/relabel_pick_place_csv.py` | Relabels exported gripper-width CSVs in place; separate from the xArm preprocessing pipeline |
| `analysis/piecewise_linear_approximation_velocity.py` | Velocity PLA for the latest processed run, or a selected run |
| `analysis/pla_joint_position.py` | Position PLA for all current processed runs, or a selected run |
| `analysis/sliding_window_effort_energy.py` | Effort energy windows for the latest processed run, or a selected run |
| `analysis/pla_velocity_effort_all_runs.py` | Velocity and effort PLA across current processed runs, with phase-shaded plots |

```bash
python scripts/preprocessing/create_joint_processed_data.py --raw-run "Raw data/pick_place_20260904_145823"
python scripts/analysis/piecewise_linear_approximation_velocity.py
python scripts/analysis/pla_joint_position.py
python scripts/analysis/sliding_window_effort_energy.py
python scripts/analysis/pla_velocity_effort_all_runs.py
```

Each analysis accepts `--processed-run` for an explicit per-joint run folder.
Use `--help` for its complete options. Current default discovery reads immediate
run folders in `Processed data/`; historical runs under `OLD/` need an explicit path.

`relabel_pick_place_csv.py` uses gripper-width threshold crossings and ten-sample
pick/place intervals. Supply `--directory` explicitly: its historical default
`pick_place_csv/` is not included in this branch. It requires `phase` as the final
CSV field and preserves the numeric signal fields while replacing labels. These
labels are estimates, separate from the Franka segmentation workflow.
