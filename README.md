# xArm Branch - Qualitative Analysis of Robotic Signal Components using ILP

## Overview

This branch contains the **manipulator-specific implementation** of the project:

**"Qualitative Analysis of Robotic Signal Components using Inductive Logic Programming (ILP)"**

The focus of this branch is on analyzing **xArm robotic arm signals** during task execution and extracting **qualitative patterns** that can be represented symbolically and learned using ILP.

---

## Objective

The goal of this branch is to:

- Process raw actuator and joint signals from the xArm robot
- Segment robot actions (e.g., pick, place, lift)
- Extract qualitative signal characteristics
- Convert processed data into logical facts
- Learn interpretable symbolic rules using ILP

---

## Robot Platform

- **Robot:** UFactory xArm (e.g., xArm6 / xArm7)
- **Type:** Industrial manipulator
- **Use case:** Pick-and-place tasks

---

## Data Sources

The data used in this branch is typically obtained from:

- ROS 2 bag files
- Joint state topics (`/joint_states`)
- End-effector state
- Gripper state (if available)

### Signals analyzed:
- Joint positions
- Joint velocities
- Joint efforts (torques)
- End-effector trajectory
- Gripper open/close state

---

## Repository Layout

```text
.
|-- data/
|   |-- raw/rosbags/
|   `-- processed/csv/
|-- outputs/
|   `-- plots/
`-- scripts/
    |-- preprocessing/
    `-- analysis/
```

---

## Actions Considered

The manipulator actions are segmented into meaningful phases:

- `approach` - moving towards object
- `pick` - grasping object
- `lift` - lifting object
- `move` - transporting object
- `place` - releasing object
- `retract` - moving away
- `idle` - no motion

---

## Methodology

### 1. Data Preprocessing
- Extract signals from ROS 2 bag files
- Remove noise and idle regions
- Normalize and synchronize signals

### 2. Action Segmentation
- Divide continuous data into action windows
- Label each segment with corresponding action

### 3. Feature Extraction
Convert numeric signals into qualitative features:

- `increasing(signal)`
- `decreasing(signal)`
- `constant(signal)`
- `peak(signal)`
- `oscillating(signal)`

Current joint-2 analysis scripts focus on time-domain sliding windows:

```bash
python3 scripts/preprocessing/filter_joint_states_wide_csv.py
python3 scripts/analysis/plot_joint2_effort_energy.py
python3 scripts/analysis/qualitative_joint2_effort_analysis.py
```

Generated files:

- `data/processed/csv/joint2_position_energy.csv`
- `data/processed/csv/joint2_position_qualitative.csv`
- `outputs/plots/joint2_position_energy_sliding_window.png`
- `outputs/plots/joint2_position_qualitative_labels.png`

### 4. Logical Fact Generation
Example:

```prolog
increasing(joint2_velocity, t1).
constant(joint3_position, t1).
```

### 5. ILP Learning

Using:

- Background knowledge
- Positive examples (correct actions)
- Negative examples (incorrect or different actions)

Generate hypotheses such as:

```prolog
pick :-
    increasing(joint2_velocity),
    peak(joint3_effort),
    constant(gripper_position).
```

---

## Notes

- This branch is platform-specific and focuses only on the xArm robot.
- Shared concepts, theory, and general methodology are documented in the main branch.
- This implementation can later be extended to:
  - Fault detection
  - Action verification
  - Skill learning
