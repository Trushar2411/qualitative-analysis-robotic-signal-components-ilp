# Processed Data

This folder stores per-joint CSV files generated from raw pick-and-place runs.
Each processed run keeps the original run name and appends a processing
timestamp.

## Current Structure

```text
Processed data/<raw_run_name>_processed_YYYYMMDD_HHMMSS/
|-- joint_1.csv
|-- joint_2.csv
|-- joint_3.csv
|-- joint_4.csv
|-- joint_5.csv
`-- joint_6.csv
```

Each joint CSV contains:

```text
joint,bag_time_ns,bag_time_sec,header_stamp_sec,position,velocity,effort,phase
```

These files are the input to the qualitative analysis scripts in
`scripts/analysis/`.
