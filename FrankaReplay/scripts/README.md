# Franka scripts

The [Franka workflow guide](../README.md) documents setup, input schemas, and
commands. All scripts accept `--help`.

| Script | Purpose |
|---|---|
| `franka_replay.py` | Replay recorded arm and object positions in PyBullet |
| `hdf5_csv.py` | Export numeric HDF5 observations to per-demo CSVs |
| `extract_robot_joints.py` | Select arm/finger signals and recover elapsed control time |
| `plot_robot_joints_with_time.py` | Plot one extracted joint CSV |
| `segment_franka_phases_reduced.py` | Estimate five phases using finger motion |
| `pla_franka_batch.py` | Fit phase-contained position/velocity windows |
| `run_pipeline.py` | Run conversion through PLA in a fresh output folder |

Data and generated plots belong in `../data/` and `../outputs/`. Extraction,
segmentation, and PLA return a nonzero status when a batch contains rejected
files, while retaining valid outputs for inspection.
