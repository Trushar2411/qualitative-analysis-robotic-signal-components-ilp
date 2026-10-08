# xArm recordings

The current recordings are `pick_place_20260904_145823`,
`pick_place_20260904_150700`, `pick_place_20260904_151320`,
`pick_place_20260904_151638`, `pick_place_20260904_151910`, and
`pick_place_20260904_153331`. Earlier object/no-object recordings are in `OLD/`.

Each current run contains a `csv/` directory. Its
`full_motion_joint_states.csv` is the preprocessing input; other CSVs contain
phase intervals or phase-specific signals. ROS bag metadata may be present under
`rosbag/`; bag payloads are excluded by the repository's ignore rules and may
need to be obtained separately.

The full-motion CSV preserves joint position, velocity, effort, timing, and
phase labels. A phase label describes the programmed sequence; it does not
independently verify object contact or grasp success.

From the repository root:

```bash
python scripts/preprocessing/create_joint_processed_data.py --raw-run "Raw data/pick_place_20260904_145823"
```

Keep original recordings intact when comparing preprocessing methods. Generated
per-joint data belongs in `Processed data/` and analysis results in `outputs/`.
