# Raw Data

This folder stores the original pick-and-place recordings before preprocessing.
Each run is kept in its own folder so the source data remains traceable.

## Current Runs

- `pick_place_No_object_1` through `pick_place_No_object_5`
- `pick_place_Object_1` through `pick_place_Object_5`

## Expected Run Structure

```text
Raw data/<run_name>/
|-- csv/
|   |-- full_motion_joint_states.csv
|   |-- phase_timestamps.csv
|   |-- home_joint_states.csv
|   |-- gripper_opening_joint_states.csv
|   |-- pick_joint_states.csv
|   |-- gripper_closing_joint_states.csv
|   |-- lift_joint_states.csv
|   |-- place_joint_states.csv
|   |-- retract_joint_states.csv
|   `-- return_home_joint_states.csv
`-- rosbag/
    `-- metadata.yaml
```

`full_motion_joint_states.csv` is the main input for preprocessing. The
phase-specific CSV files are useful for inspection and presentation examples.
