# Analysis Output Structure

The `outputs/` folder stores qualitative analysis results generated from
timestamped folders in `Processed data/`. Each analysis creates a new timestamped
folder so multiple robot runs can be compared without overwriting older results.

The current output structure is:

```text
outputs/
|-- README.md
|-- PLA/
|   `-- <processed_run_name>_PLA_YYYYMMDD_HHMMSS/
|       |-- csv/
|       |   |-- joint_1_PLA.csv
|       |   |-- joint_2_PLA.csv
|       |   |-- joint_3_PLA.csv
|       |   |-- joint_4_PLA.csv
|       |   |-- joint_5_PLA.csv
|       |   `-- joint_6_PLA.csv
|       `-- plots/
|           |-- joint_1_PLA.png
|           |-- joint_2_PLA.png
|           |-- joint_3_PLA.png
|           |-- joint_4_PLA.png
|           |-- joint_5_PLA.png
|           `-- joint_6_PLA.png
`-- SWEE/
    `-- <processed_run_name>_SWEE_YYYYMMDD_HHMMSS/
        |-- csv/
        |   |-- joint_1_SWEE.csv
        |   |-- joint_2_SWEE.csv
        |   |-- joint_3_SWEE.csv
        |   |-- joint_4_SWEE.csv
        |   |-- joint_5_SWEE.csv
        |   `-- joint_6_SWEE.csv
        `-- plots/
            |-- joint_1_SWEE.png
            |-- joint_2_SWEE.png
            |-- joint_3_SWEE.png
            |-- joint_4_SWEE.png
            |-- joint_5_SWEE.png
            `-- joint_6_SWEE.png
```

## Input Data

Both analysis scripts read processed joint files:

```text
Processed data/<processed_run_name>/joint_1.csv
Processed data/<processed_run_name>/joint_2.csv
...
Processed data/<processed_run_name>/joint_6.csv
```

Each processed joint CSV contains:

```text
joint,bag_time_ns,bag_time_sec,header_stamp_sec,position,velocity,effort,phase
```

The analysis scripts use:

- `velocity` for PLA.
- `effort` for SWEE.
- `phase` to attach each qualitative output segment or window to the robot task
  phase that dominates that time range.

## PLA: Piecewise Linear Approximation

PLA is applied to the **velocity** signal of each joint.

The goal of PLA in this branch is to convert numeric joint velocity into a small
set of qualitative shape labels that are easier to use in logic learning. Rather
than giving Popper only raw floating-point values, PLA summarizes the local
behavior of a joint velocity signal as increasing, decreasing, or stable.

### How PLA Works in the Code

The script is:

```text
scripts/analysis/piecewise_linear_approximation_velocity.py
```

For each `joint_*.csv` file, the code:

1. Reads the processed joint CSV.
2. Keeps the columns `joint`, `bag_time_sec`, `velocity`, and `phase`.
3. Renames `bag_time_sec` to `time_sec`.
4. Normalizes time so the first sample starts at `0.0` seconds.
5. Splits the velocity signal into windows.
6. Splits each window into smaller PLA segments.
7. Fits a straight line to each segment using `numpy.polyfit`.
8. Uses the line slope to assign a qualitative label.
9. Saves one PLA CSV and one PLA plot per joint.

The main parameters are:

```text
WINDOW_SIZE = 20
STEP = 20
PLA_SEGMENTS = 4
DIRECTION_THRESHOLD = 0.02
```

The label logic is:

```text
if slope > DIRECTION_THRESHOLD:
    label = ramp_up
elif slope < -DIRECTION_THRESHOLD:
    label = ramp_down
else:
    label = constant
```

The phase for each PLA segment is selected using the most frequent phase label
inside that segment.

### PLA CSV Columns

Each `joint_N_PLA.csv` contains:

```text
segment_id
joint
start_time_sec
end_time_sec
duration_sec
phase
label
slope
intercept
start_velocity
end_velocity
mean_velocity
```

The most important columns for Popper-style logic facts are usually:

- `joint`
- `phase`
- `label`
- `start_time_sec`
- `end_time_sec`

Example fact direction:

```prolog
velocity_trend(run1, joint2, pick, ramp_up).
velocity_trend(run1, joint4, return_home, ramp_down).
```

## SWEE: Sliding Window Effort Energy

SWEE is applied to the **effort** signal of each joint.

The goal of SWEE in this branch is to measure how much the joint effort changes
within a moving window. A calm or stable effort signal has low centered energy.
A rapidly changing or high-variation effort signal has higher centered energy.
This is useful because effort changes can indicate load changes, contact,
resistance, or more demanding parts of the motion.

### How SWEE Works in the Code

The script is:

```text
scripts/analysis/sliding_window_effort_energy.py
```

For each `joint_*.csv` file, the code:

1. Reads the processed joint CSV.
2. Keeps the columns `joint`, `bag_time_sec`, `effort`, and `phase`.
3. Renames `bag_time_sec` to `time_sec`.
4. Normalizes time so the first sample starts at `0.0` seconds.
5. Moves a sliding window across the effort signal.
6. Computes the mean effort inside the window.
7. Centers the effort values by subtracting that mean.
8. Squares the centered values and sums them.
9. Labels each window as low, medium, or high energy using quantiles.
10. Saves one SWEE CSV and one SWEE plot per joint.

The main parameters are:

```text
WINDOW_SIZE = 20
STEP = 5
```

The energy calculation is:

```text
centered_effort = effort_window - mean(effort_window)
centered_effort_energy = sum(centered_effort ** 2)
```

The label logic uses the 33rd and 66th percentiles of the energy values for that
joint:

```text
energy < q33      -> low_energy
energy < q66      -> medium_energy
otherwise         -> high_energy
```

The phase for each SWEE window is selected using the most frequent phase label
inside that window.

### SWEE CSV Columns

Each `joint_N_SWEE.csv` contains:

```text
window_id
joint
start_time_sec
end_time_sec
center_time_sec
phase
mean_effort
range_effort
centered_effort_energy
energy_label
```

The most important columns for Popper-style logic facts are usually:

- `joint`
- `phase`
- `energy_label`
- `centered_effort_energy`
- `start_time_sec`
- `end_time_sec`

Example fact direction:

```prolog
effort_energy(run1, joint2, pick, high_energy).
effort_energy(run1, joint1, home, low_energy).
```

## Relationship to Popper

The output CSV files are not Popper input files yet. They are intermediate
analysis results that can be transformed into Popper facts.

The intended logic-learning path is:

```text
Processed data
  -> PLA velocity labels
  -> SWEE effort energy labels
  -> Prolog facts
  -> Popper background knowledge and examples
  -> learned rules
```

The value of PLA and SWEE is that they convert continuous robot signals into
discrete symbolic descriptions. Those symbolic descriptions are much easier for
an ILP system such as Popper to use than raw numeric time-series samples.
