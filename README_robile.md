# Robile Wall Following — Qualitative Signal Analysis using ILP

**Author:** Alisha Syed Karimulla  
**Project:** Qualitative Analysis of Robotic Signal Components using Inductive Logic Programming  
**Supervisor:** Prof. Dr. Javad Ghofrani | Youssef Mahmoud Youssef  
**University:** Hochschule Bonn-Rhein-Sieg (H-BRS)  

---

## Overview

This branch contains the implementation for the **Kelo Robile mobile robot** component of the joint R&D project. The goal is to collect real-world sensor telemetry from the Robile during wall-following tasks, apply qualitative signal abstraction (QTA), and use Inductive Logic Programming (ILP) to learn interpretable rules describing robot behavior.

---

## Robot Platform

**Robot:** Kelo Robile 04  
**Environment:** Real university corridor (H-BRS)  
**Controller:** Holonomic P-controller (sideways motion, no rotation)  
**Framework:** ROS 2 Humble  

---

## Experimental Scenarios

### Scenario 1 — Plain Wall Following
**Action Labels:**
| Label | Description |
|-------|-------------|
| `idle` | Robot stationary |
| `searching_wall` | Sliding left to find wall |
| `approaching_wall` | Moving toward wall |
| `wall_following` | Stable at 0.5m ✅ |
| `wall_following_fail` | Too close or unstable ❌ |

---

### Scenario 2 — Pillar Wall Following
**Action Labels:**
| Label | Description |
|-------|-------------|
| `idle` | Robot stationary |
| `searching_wall` | Sliding left to find wall |
| `approaching_wall` | Moving toward wall |
| `wall_following` | Stable at 0.5m ✅ |
| `obstacle_detected` | Pillar detected ⚠️ |
| `obstacle_avoidance` | Moving around pillar 🔄 |
| `wall_reacquired` | Finding wall after pillar 🔄 |
| `wall_following_fail` | Failed behavior ❌ |

---

## Repository Structure
robile branch/
├── src/
│ ├── robile_wall_follower/ ← Plain wall package
│ │ ├── wall_follower_node.py ← P-controller
│ │ ├── data_logger_node.py ← CSV recorder
│ │ ├── launch/
│ │ │ └── wall_follower.launch.py
│ │ └── signal_processing/
│ │ ├── visualizer.py ← Raw signal plots
│ │ ├── signal_processor.py ← Event detection
│ │ ├── qta_visualizer.py ← QTA visualization
│ │ └── prolog_generator.py ← ILP facts (WIP)
│ │
│ └── robile_pillar_follower/ ← Pillar wall package
│ ├── pillar_follower_node.py ← State machine controller
│ ├── data_logger_node.py ← CSV recorder
│ └── launch/
│ └── pillar_follower.launch.py
│
├── data/ ← Plain wall CSV files
├── data_pillar/ ← Pillar wall CSV files
├── data_cleaned/ ← Event-detected CSV files
├── plots/ ← Raw signal visualizations
├── plots_qta/ ← QTA visualizations
├── qta_results/ ← QTA JSON outputs
└── dataset_labels.json ← Good/bad classification
---

## Dataset

| Scenario | Good Runs | Bad Runs | Total |
|----------|-----------|----------|-------|
| Plain wall | 11 | 4 | 15 |
| Pillar wall | 7 | 3 | 10 |
| **Total** | **18** | **7** | **25** |

**Sampling rate:** 10 Hz (every 0.1 seconds)  
**Sensors recorded:** LIDAR, Odometry, IMU, Wheel speeds, Commands

---

## Pipeline
Step 1: Data Collection
Raw sensor data → CSV files with action labels

Step 2: Event Detection
CSV files → Identify useful sensors at event boundaries
→ Remove useless sensors (wheel speeds = 0, cmd_angular_z = 0)

Step 3: QTA Visualization
Cleaned CSV → Apply QTA per action window
→ is_constant / is_decreasing / is_increasing / is_oscillating / is_zero
→ Colored graphs (like PLA visualization)

Step 4: Prolog Generation (In Progress)
QTA results → Prolog facts
→ signal_shape(run_id, action_window, sensor, shape).

Step 5: Popper ILP (Coming Soon)
Prolog facts → Learn interpretable rules
→ wall_following(Run) :- signal_shape(Run, wall_following, lidar_left, is_constant).

Step 6: Evaluation (Coming Soon)
→ Precision and Recall measurement
---

## Key Technical Findings

### Event Detection Results
Sensors ranked by usefulness across all 25 runs:

| Sensor | Kept in | Frequency |
|--------|---------|-----------|
| `imu_accel_x` | 25/25 | 100% |
| `imu_accel_y` | 25/25 | 100% |
| `imu_angular_z` | 25/25 | 100% |
| `lidar_left` | 24/25 | 96% |
| `lidar_right` | 24/25 | 96% |
| `lidar_front_right` | 24/25 | 96% |
| `wheel_speed_0-3` | 0/25 | 0% ❌ |
| `cmd_angular_z` | 1/25 | 4% ❌ |

### QTA Results — Plain Wall Good Runs
| Action Window | lidar_left QTA shape |
|--------------|---------------------|
| approaching_wall | is_decreasing |
| wall_following | **is_constant** ✅ |
| idle | is_constant |

### QTA Results — Pillar Wall Good Runs
| Action Window | lidar_left QTA shape |
|--------------|---------------------|
| approaching_wall | is_decreasing |
| wall_following | **is_constant** ✅ |
| obstacle_detected | is_constant |
| obstacle_avoidance | **is_increasing** ✅ |
| wall_reacquired | is_decreasing |
| wall_following | **is_constant** ✅ |

---

## Visualization Examples

### Plain Wall — QTA Analysis (lidar_left)
- **RED line** = `is_decreasing` (approaching wall)
- **BLUE line** = `is_constant` (wall following at 0.5m)

### Pillar Wall — QTA Analysis (lidar_left)
- **RED line** = `is_decreasing` (approaching)
- **BLUE line** = `is_constant` (stable following)
- **GREEN line** = `is_increasing` (avoiding pillar!)
- **RED line** = `is_decreasing` (returning to wall)
- **BLUE line** = `is_constant` (resumed following)

---

## How To Run

### Prerequisites
```bash
# ROS 2 Humble
source /opt/ros/humble/setup.bash
source ~/rnd_ws/install/setup.bash
export ROS_DOMAIN_ID=3
```

### Connect To Robot
```bash
ssh -x studentkelo@192.168.0.104
tmux new -s drivers
source ~/ros2ws/install/setup.bash
ros2 launch robile_bringup robot.launch.py
# Ctrl+B then D to detach
```

### Run Plain Wall Follower
```bash
ros2 launch robile_wall_follower wall_follower.launch.py
```

### Run Pillar Wall Follower
```bash
ros2 launch robile_pillar_follower pillar_follower.launch.py
```

### Run Signal Processing Pipeline
```bash
cd ~/rnd_ws/src/robile_wall_follower/signal_processing

# Step 1: Event Detection
python3 signal_processor.py

# Step 2: QTA Visualization
python3 qta_visualizer.py

# Step 3: Prolog Generation (coming soon)
python3 prolog_generator.py
```

---

## Technical Notes

**Why holonomic control?**  
The Robile uses omnidirectional wheels. Using sideways motion (`cmd.linear.y`) instead of rotation produces smoother signal patterns — cleaner data for ILP learning.

**Why timer-based stop for pillar wall?**  
Odometry underestimates distance when using holonomic sideways movement. A 75-second timer provides more reliable stopping.

**Why lidar_left for pillar detection?**  
The front-left LIDAR beam missed the 17cm pillar. The left beam reliably detects the pillar as a sudden drop from 0.5m to 0.33m.

**Why IMU sensors ranked highest?**  
IMU acceleration sensors capture ALL movement including sideways holonomic motion, making them more informative than odometry at event boundaries.

---

## Status

| Work Package | Status |
|-------------|--------|
| WP2: Data Collection | ✅ Complete |
| WP3: Signal Processing (Event Detection) | ✅ Complete |
| WP3: QTA Visualization | ✅ Complete |
| WP4: Prolog Generation | 🔄 In Progress |
| WP4: Popper ILP | ❌ Not Started |
| WP5: Evaluation | ❌ Not Started |
| WP6: Documentation | 🔄 In Progress |