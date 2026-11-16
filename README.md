# Kelo Robile Wall-Following: Interpretable Phase Rules with ILP

**Author:** Alisha Syed Karimulla
**Joint project:** Qualitative Analysis of Robotic Signal Components using Inductive Logic Programming (with Trushar Ghanekar, xArm6 part on branch `xarm`)
**Supervisors:** Prof. Dr. Javad Ghofrani, Youssef Mahmoud Youssef
**University:** Hochschule Bonn-Rhein-Sieg (H-BRS)

This branch contains the **Kelo Robile** part of the project. A rule-based wall-following controller drives the robot along a wall and around a pillar. The recorded signals are turned into qualitative words, and **Popper** (ILP) learns one short, interpretable rule per controller phase.

## Robot and task

- **Robot:** Kelo Robile (holonomic: drives forward and sideways), ROS 2 Humble
- **Controller:** rule-based wall-following controller (`wall_follower_node.py`, `pillar_follower_node.py`) keeping about 0.5 m to the wall on the left
- **Logger:** `data_logger_node.py` writes one CSV row every 0.1 s (10 Hz) with sensor values and the controller's phase label

| Phase | What the robot does |
|---|---|
| `approaching_wall` | moves toward the wall |
| `wall_following` | drives along the wall at ~0.5 m |
| `obstacle_detected` | pillar appears, robot brakes (0.5 s) |
| `obstacle_avoidance` | slides away from the wall around the pillar (2.5 s) |
| `wall_reacquired` | pillar passed, returns to the wall (1.5 s) |

Not used for rules: `idle`, `searching_wall`, `wall_following_fail`.

## Data

| Scenario | Raw CSV | Good runs | Bad runs (joystick) |
|---|---|---|---|
| Plain wall | `data/` | 10 | 5 |
| Wall with pillar | `data_pillar/` | 7 | 3 |

- `data_cleaned/`: labelled runs, invalid lidar readings capped at 10 m
- `data_cleaned_odom/`: cleaned runs plus odometry-derived signals (`side_speed`, `total_speed`); input of the final experiments
- `dataset_labels.json`: good/bad classification of every run

## Method

1. **Sensor selection:** all recorded signals were screened. Used: the 4 lidar beams (left, right, front, front-right) and **total speed** from the odometry position. Excluded: wheel speeds (always 0), IMU acceleration (vibration noise), commands `cmd_*` (issued by the controller that also assigns the labels), turning rate (rules did not transfer to a second environment), forward speed (no variation between phases).
2. **Total speed:** `v = sqrt(dx^2 + dy^2) / 0.1 s` from consecutive odometry positions; values above 1 m/s removed. Matches the commanded speeds (0.100 vs 0.1 m/s in wall following).
3. **Qualitative words per phase segment:**
   - *Trend* (inside the segment): increasing, decreasing, constant, oscillating, computed with **RAW** (step-wise ups and downs) and **QTA** (slope and spread)
   - *Jump* (at the start of the segment): first 0.5 s minus last 0.5 s of the previous segment; ±10 cm for lidar, ±10 % of the signal range for speed
4. **Popper:** for each phase, the shortest rule that covers all its segments and no others (max 3 clauses, max 4 conditions per clause, 1 variable).
5. **Evaluation:** leave-one-run-out on the 7 pillar runs, transfer to the 10 plain-wall runs, comparison of Popper settings.

## Results (final: lidar + total speed, noisy Popper)

Recall and precision on the hidden run (leave-one-run-out):

| Phase | QTA rule | Recall | Precision | RAW rule | Recall | Precision |
|---|---|---|---|---|---|---|
| approaching_wall | L dec | 0.93 | 1.00 | L dec | 1.00 | 1.00 |
| wall_following | speed const | 1.00 | 1.00 | L no jump + R const | 0.80 | 1.00 |
| obstacle_detected | L jump↓ + speed jump↓ + speed dec | 0.86 | 1.00 | L const + L jump↓ | 0.86 | 0.75 |
| obstacle_avoidance | L inc + FR no jump | 1.00 | 1.00 | L inc | 1.00 | 1.00 |
| wall_reacquired | L jump↑ | 1.00 | 1.00 | L jump↑ | 1.00 | 0.88 |
| **Average** | | **0.96** | **1.00** | | **0.93** | **0.93** |

L = left lidar, R = right lidar, FR = front-right lidar, speed = total speed.

- **Second environment:** rules learned on the pillar runs, applied unchanged to the plain-wall runs: 10/10 recognised, 0 false positives. Rules using the turning rate failed (wall following 0/10) and were rejected.
- **Popper settings:** training recall is 1.00 only in strict mode (guaranteed by construction). On hidden runs, results are stable from 2 conditions per clause upward, and the core conditions appear in every setting.

## Repository structure

| Path | Content |
|---|---|
| `src/robile_wall_follower/` | ROS 2 package: plain-wall controller and data logger |
| `src/robile_wall_follower/signal_processing/pipeline/` | all analysis scripts and final results (`README.txt` = run order) |
| `.../pipeline/multisensor_results/` | final rules, leave-one-run-out, transfer and settings results |
| `src/robile_pillar_follower/` | ROS 2 package: pillar controller and data logger |
| `data/`, `data_pillar/` | raw CSV recordings |
| `data_cleaned/`, `data_cleaned_odom/` | cleaned and odometry-enriched runs |
| `phase_plots/` | figures (signals per phase, rule validation) |

## Reproduction (main steps)

Requires Python 3 (pandas, numpy, matplotlib) and Popper 4.x with SWI-Prolog (here in `~/popper_env`). Run inside `src/robile_wall_follower/signal_processing/pipeline`:

| Step | Command |
|---|---|
| odometry signals | `python3 add_odometry.py` |
| total speed | `python3 add_total_speed.py` |
| learn + evaluate | `SETS="lidar+speed" POPPER_ARGS="--noisy" ~/popper_env/bin/python -u ilp_multisensor.py` |
| recall/precision per rule | `python3 recall_precision.py` |
| Popper settings table | `python3 settings_table.py` |
| one run end to end | `python3 check_one_run.py pill_good_02` |

`ilp_multisensor.py` options (environment variables): `SETS`, `POPPER_ARGS`, `MAX_BODY`, `MAX_CLAUSES`. Earlier lidar-only steps are listed in `pipeline/README.txt`.

## Limitations and future work

- Labels come from the controller; three phases end on timers.
- 7 pillar runs, one room, one pillar; several obstacles not yet tested.
- The CSV logger stored only selected signals (no rosbag): no sideways velocity, no wheel speeds, 4 lidar beams. Speed was reconstructed from odometry.
- Next: label permutation test, runs with several pillars (recorded or simulated), rosbag recording, rules over phase sequences for faulty runs.
