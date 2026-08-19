# Scripts

This folder contains the runnable Python workflow for turning xArm pick-and-place
recordings into qualitative signal descriptions.

## Folder Layout

```text
scripts/
|-- data_collection/
|   |-- real_robot_pick_and_place_recorder.py
|   `-- simulated_pick_and_place_recorder.py
|-- preprocessing/
|   `-- create_joint_processed_data.py
`-- analysis/
    |-- piecewise_linear_approximation_velocity.py
    |-- pla_joint_position.py
    `-- sliding_window_effort_energy.py
```

## Typical Order

1. Record or prepare raw data in `Raw data/<run>/csv/full_motion_joint_states.csv`.
2. Split the raw full-motion CSV into per-joint files:

   ```bash
   python3 scripts/preprocessing/create_joint_processed_data.py --raw-run "Raw data/pick_place_Object_1"
   ```

3. Run qualitative analysis on processed joint files:

   ```bash
   python3 scripts/analysis/piecewise_linear_approximation_velocity.py
   python3 scripts/analysis/pla_joint_position.py
   python3 scripts/analysis/sliding_window_effort_energy.py
   ```

The velocity PLA and SWEE scripts default to the latest processed run. The
position PLA script processes all valid processed runs unless `--processed-run`
is provided.
