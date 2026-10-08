# Per-joint xArm data

`create_joint_processed_data.py` creates a folder named
`<raw_run>_processed_<timestamp>/` containing `joint_1.csv` through `joint_6.csv`.
Each file contains:

```text
joint,bag_time_ns,bag_time_sec,header_stamp_sec,position,velocity,effort,phase
```

Existing historical processed runs are under `OLD/`. No current per-joint runs
were committed at the time of this cleanup. Create one from a September recording:

```bash
python scripts/preprocessing/create_joint_processed_data.py --raw-run "Raw data/pick_place_20260904_145823"
```

Run this from the repository root. Analysis scripts use immediate run folders by
default. Select an archived run explicitly with `--processed-run` when needed.
Processing timestamps identify an output version; signal timestamps identify
samples in the original recording.
