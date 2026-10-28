# Jessie xArm6: simulation and gripper recording

This package replays the nine steps in your supplied real-robot script in Gazebo and records the arm and gripper together. It targets **Ubuntu 22.04, ROS 2 Humble and Gazebo Classic 11**. The robot meshes, gripper mechanism and controllers come from UFACTORY's `xarm_ros2` repository.

The supplied motion is reproduced as joint targets. Movement durations are configurable because the real script did not specify a speed or acceleration. This is a zero-gravity motion-test scene, following the vendor's simulation convention. It has no object, table or grasp/contact model. It does not establish that a cube would be picked up successfully. Gazebo Classic is an older simulator; this package is specifically for the existing Humble stack, not Gazebo Harmonic or Jazzy.

Version 0.1.3 uses **kinematic mimic following** by default for the five passive gripper joints. The vendor plugin directly sets their simulated joint positions from the drive joint instead of using its force/PID path. This is intended for the position-only experiments here: it avoids follower tracking error blocking initialization while retaining actual Gazebo joint-state recording and the settling check. It imposes ideal mechanical coupling and does not model independent finger dynamics, compliance or grasp forces. The expanded URDF stored in the bag records this configuration.

Version 0.1.4 mounts the fixed robot base **1.0 metre above the floor**. The default folded pose can put the gripper below the base, so mounting at floor level can create ground penetration and large simulated joint errors even when a controller reports success. The offset is applied to the URDF's fixed `world_joint`, so Gazebo and ROS TF agree. It does not change the arm's joint targets or gripper angles. This is an elevated fixed mount, without a physical table or pedestal model.

## 1. Install prerequisites

Use a normal Ubuntu terminal outside conda, uv and Python virtual environments. ROS 2 Humble must already be installed and `/opt/ros/humble/setup.bash` must exist. If needed, follow the [official Humble Ubuntu installation guide](https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html).

```bash
sudo apt update
sudo apt install -y git unzip python3-colcon-common-extensions python3-rosdep python3-yaml \
  ros-humble-gazebo-ros-pkgs ros-humble-gazebo-ros2-control \
  ros-humble-ros2-controllers ros-humble-rosbag2-py \
  ros-humble-rosbag2-storage-default-plugins ros-humble-xacro
```

Initialize rosdep once if you have not already done so. Skip `sudo rosdep init` when it is already initialized.

```bash
sudo rosdep init
rosdep update
```

## 2. Extract and build

Assuming the ZIP is in `~/Downloads`:

```bash
mkdir -p ~/Trushar
unzip ~/Downloads/XArm6_Simulation_With_Gripper.zip -d ~/Trushar
cd ~/Trushar/xarm6_simulation
bash scripts/build_workspace.sh
```

The build script creates `~/jessie_sim_ws`, downloads UFACTORY's Humble source with its submodules, installs missing dependencies with rosdep (which may request your sudo password), and builds the required packages. It pins a newly cloned vendor checkout to the source revision checked while preparing this package:

```text
ac736c92b02de7ca7e0be6f737d77d46707464d8
```

An existing vendor checkout is reused without resetting it. Keep the extracted `xarm6_simulation` folder because the workspace links to it. To use another workspace:

```bash
bash scripts/build_workspace.sh ~/another_jessie_sim_ws
```

## 3. Start the simulation and record one sequence

In a fresh terminal:

```bash
source /opt/ros/humble/setup.bash
source ~/jessie_sim_ws/install/setup.bash
ros2 launch xarm6_pick_place_sim simulation.launch.py record:=true
```

Gazebo opens and the runner waits for the simulation clock, both controllers, the robot description, and all 12 joints. Before opening the bag, it commands the gripper to **0.33 rad** and checks a full second of simulator readings: all six gripper joints must be within 0.02 rad of the target, with no more than 0.002 rad position range per joint in that second. If initialization fails, recording does not begin.

The arm then performs the recorded sequence:

1. Home
2. Open gripper
3. Move to pick
4. Close gripper
5. Lift
6. Move to place
7. Open gripper
8. Retract
9. Return home

Keep Gazebo unpaused. Allow around a minute of simulation time; a slower computer may take longer. The console prints the output directory when recording and CSV export finish. Gazebo stays open afterward; press Ctrl+C to close it.

For a headless run:

```bash
ros2 launch xarm6_pick_place_sim simulation.launch.py record:=true gui:=false
```

To select another output directory:

```bash
ros2 launch xarm6_pick_place_sim simulation.launch.py record:=true output_dir:=$HOME/Trushar/simulation_data
```

The mount height is configurable in metres. For example:

```bash
ros2 launch xarm6_pick_place_sim simulation.launch.py record:=true base_height:=1.0
```

Use `record:=false` to inspect the raised starting pose before running. Restart Gazebo after changing the height. The launch prints `Fixed robot base mounted 1.000 m above the floor.` Do not additionally shift the model through Gazebo's pose editor or add a second spawn z offset; the mount transform already contains the height.

## 4. Inspect first, then record repeated runs

Launch without automatically moving:

```bash
ros2 launch xarm6_pick_place_sim simulation.launch.py
```

In a second terminal, source the same ROS and workspace setup files and run:

```bash
ros2 run xarm6_pick_place_sim run_sequence --ros-args \
  -p use_sim_time:=true -p cycles:=3
```

All cycles are saved in one bag. Each phase has a unique `phase_id` and a cycle number. The two `gripper_opening` occurrences get separate CSV files. The first cycle initializes before recording. Between subsequent cycles, a separate `gripper_reset` phase returns the gripper to 0.33 rad and waits for it to settle. This ensures the first opening in every cycle starts closed, rather than becoming a no-op after the previous cycle ended open.

## 5. Recorded data

The default destination is `~/xarm_sim_data/pick_place_sim_<date_and_time>/`.

| Output | Contents |
|---|---|
| `rosbag/` | SQLite ROS 2 bag and `metadata.yaml` |
| `csv/full_motion_joint_states.csv` | All arm and gripper samples with phase labels |
| `csv/gripper_joint_states.csv` | Gripper-only columns with the same phase labels |
| `csv/phase_timestamps.csv` | Start/end times, occurrence IDs, cycle numbers and status |
| `csv/cycle_001_step_02_gripper_opening_joint_states.csv` | First opening occurrence |
| `csv/cycle_001_step_07_gripper_opening_joint_states.csv` | Second opening occurrence |
| Other `csv/cycle_..._joint_states.csv` files | Remaining individual phase occurrences |
| `phase_log.json` | Phase intervals, including an aborted step when possible |
| `motion_used.yaml` | Exact configuration used for the run |
| `run_info.json` | Completion status, sample count and data limitations |

Bag topics:

| Topic | Type and contents |
|---|---|
| `/xarm/joint_states` | `sensor_msgs/msg/JointState`: six arm joints plus six gripper joints |
| `/xarm/gripper_joint_states` | `sensor_msgs/msg/JointState`: six gripper joints only |
| `/xarm_sim/phase_events` | `std_msgs/msg/String`: JSON start/end events |
| `/clock` | ROS simulation clock |
| `/robot_description` | Expanded URDF, including the telemetry plugin |
| `/tf`, `/tf_static` | Robot transforms |

The gripper joints are `drive_joint`, `left_finger_joint`, `left_inner_knuckle_joint`, `right_outer_knuckle_joint`, `right_finger_joint` and `right_inner_knuckle_joint`.

The normal ros2_control state broadcaster only exposes the gripper drive joint. This launch adds Gazebo's joint-state plugin at a requested 100 Hz and explicitly reads all 12 simulated joints. Finger values come from Gazebo, including the vendor's mimic-joint mechanism. The recorder does not manufacture finger values by copying the drive joint or command target. The original controller topic `/joint_states` remains available; the full raw Gazebo telemetry is `/xarm_sim/joint_states`.

With the default kinematic follower mode the passive joint positions are constrained to follow the drive joint, so they are redundant position signals by design. To explicitly compare with the original vendor force/PID mode:

```bash
ros2 launch xarm6_pick_place_sim simulation.launch.py record:=true gripper_mimic_mode:=pid
```

PID mode may retain offsets or oscillation and fail the same strict initialization gate. Changing the follower mode requires restarting Gazebo to load the new robot description.

Positions are **radians** and velocities are **radians/second**. The standard Gazebo joint-state plugin does not publish effort; those CSV cells are empty. Do not use these data as measured torque, grip force or evidence of a successful grasp. Blank effort fields should remain missing values when preparing ILP predicates.

## 6. Joint targets and gripper conversion

The current arm targets are copied from the script in this request:

| Pose | Joint angles in degrees |
|---|---|
| Home | `[0, -53.6, 4.3, 0, 49.4, 0]` |
| Pick | `[0, 39, -60, 0, -67, 0]` |
| Lift | `[-22, 25, -72, 0, -45, 0]` |
| Place | `[-15, 46, -68, 0, -69, 0]` |
| Retract | `[-21, 16, -67, 0, -42, 0]` |

UFACTORY's driver conversion with `max_pos=850` gives:

```text
drive_joint angle [rad] = (850 - SDK position) / 1000
700 (open target)  -> 0.15 rad
520 (close target) -> 0.33 rad
```

These SDK positions are not a direct finger-gap measurement in millimetres. Your close target is preserved; it is not replaced with the fully closed limit.

`initial_gripper_rad: 0.33` is set in `motion.yaml`. Both opening steps now command **0.33 -> 0.15 rad**, so both have a decreasing position trend. The closing step commands **0.15 -> 0.33 rad**. The initial movement from the model's spawn configuration to 0.33 rad happens before recording; it is preparation, not a labelled opening step. Older custom YAML configurations without this key default to their configured SDK close target.

Edit `src/xarm6_pick_place_sim/config/motion.yaml` to change targets, movement durations or dwell times. To keep a separate experiment configuration, copy it and pass the absolute path:

```bash
ros2 run xarm6_pick_place_sim run_sequence --ros-args \
  -p use_sim_time:=true -p config_file:=$HOME/Trushar/my_motion.yaml
```

Arm commands use joint-trajectory controllers directly. They do not add collision-aware MoveIt planning. The arm begins at the model's default configuration, so the first home step includes movement from that configuration. The gripper is commanded closed and verified stable before recording starts.

## 7. Time and phase labels

Folder names use the computer's date and time. All bag timestamps and phase intervals use **ROS simulation time**. `header_stamp_ns` preserves each simulator message's stamp; `bag_time_ns` is the runner's simulation-clock receipt time. The nanosecond columns are authoritative.

The phase starts before the command and ends after its configured dwell, matching your script's phase definition. CSV labels use half-open intervals `[start, end)`. Samples before the first phase, after the last phase, or in gaps are excluded from the CSV exports. **The exported CSV files contain no `idle` phase.** The rosbag retains the full recording. Timestamps are preserved rather than compressed across removed gaps, and holds inside a labelled phase remain part of that phase. There is no backward/forward fill. An aborted phase is marked `aborted`. An unfinished interval with no end is not silently extended over later samples.

The bag writer is in-process, so there is no recorder startup sleep or unconsumed subprocess pipe. On a normal finish it closes the bag before exporting. Ctrl+C attempts to preserve partial logs and recording, but a forced process kill or power loss can still leave an unfinalized bag.

## 8. Inspect or re-export a bag

Replace `/path/to/run/rosbag` with the directory printed by the recorder:

```bash
ros2 bag info /path/to/run/rosbag
ros2 run xarm6_pick_place_sim export_bag /path/to/run/rosbag
```

The exporter supports split bags through rosbag2's reader. Phase intervals are loaded from `phase_log.json`, or recovered from bagged phase events when that file is absent.

The same command re-exports older bags with idle rows removed. To remove idle rows from an existing CSV without ROS or changing its other values, use the standalone script from this extracted folder:

```bash
python3 scripts/remove_idle_rows.py /path/to/full_motion_joint_states.csv /path/to/full_motion_no_idle.csv
```

The output path must be a new file. This removes only rows whose phase is blank or `idle`; it does not fix initialization in a previously recorded sequence.

To play the recorded joint and phase messages, first stop the live simulation and recorder:

```bash
ros2 bag play /path/to/run/rosbag --clock \
  --topics /xarm/joint_states /xarm/gripper_joint_states /xarm_sim/phase_events
```

This generates one playback clock and excludes the already recorded `/clock` stream. Playback publishes recorded state; it does not command Gazebo to repeat the motion.

## 9. Troubleshooting

**Waiting for simulation readiness:** unpause Gazebo and inspect:

```bash
ros2 control list_controllers
ros2 topic echo /xarm_sim/joint_states --once
ros2 topic echo /clock --once
ros2 action list -t
```

Expected active controllers: `joint_state_broadcaster`, `xarm6_traj_controller` and `xarm_gripper_traj_controller`. The telemetry message must contain all 12 joint names.

**Missing gripper motion:** look for `libgazebo_mimic_joint_plugin.so` loading errors. The launch adds the installed `xarm_gazebo/lib` directory to Gazebo's plugin path. Ensure the vendor package built and that the workspace is sourced. The extra telemetry plugin requires `ros-humble-gazebo-plugins`, included in the prerequisite packages.

**Controller succeeds but initialization fails:** the gripper controller commands `drive_joint`; success alone does not verify all five followers. This version uses the vendor plugin's direct-position path for the follower joints by removing the `hasPID` elements from the generated robot description. Setting their text to `false` would not work: the plugin tests for element presence. The runner still checks the actual positions and now prints each failing joint's position, target and error on timeout. If the problem persists, keep Gazebo running with `record:=false` and inspect `ros2 topic echo /xarm_sim/joint_states --once`; do not widen the tolerances without looking at those values.

**Gripper intersects the floor:** stop the old simulation and restart with version 0.1.4 and `base_height:=1.0` (or a higher mount for a changed trajectory). Confirm the new mount-height log message and inspect the model with `record:=false`. A position-controller success message does not establish collision-free execution.

**Wrong Python or imports fail:** deactivate your virtual environment, open a fresh terminal and source `/opt/ros/humble/setup.bash` before the workspace. Use Ubuntu's ROS-compatible Python, not a pip replacement for rclpy.

**Trajectory timeout:** unpause Gazebo. For a very slow computer, increase the per-action wall-clock timeout in the manual runner command:

```bash
ros2 run xarm6_pick_place_sim run_sequence --ros-args \
  -p use_sim_time:=true -p action_wall_timeout:=360.0
```

**Gazebo cannot load or build:** check that this is Ubuntu 22.04/Humble with Gazebo Classic 11. This launch uses `gazebo_ros2_control`, not the `gz_ros2_control` interface used by newer Gazebo releases.

## Validation performed

Offline unit tests cover SDK conversion, phase boundaries/gaps, repeated phase occurrences, configuration targets, joint-name mapping, the telemetry plugin joint list, missing effort values, closed-start defaults, and the one-second settling gate. The settling tests reject oscillation, an open starting position, missing fingers, insufficient history and telemetry gaps. Python syntax and shell syntax were also checked. ROS 2 and Gazebo are not installed in the creation environment, so compilation with colcon and a live Gazebo/rosbag round trip have **not** been run here. Run the readiness checks and inspect the first bag locally before adding it to your research dataset.

Additional offline checks verify that only the five gripper follower plugins switch to direct-position mode, the PID mode can be restored, incomplete plugin lists fail before simulation starts, and target-timeout diagnostics expose individual joint errors. These checks validate configuration and code paths; the follower-mode change still requires a live run on the target Humble/Gazebo installation.

## Primary source references

- [UFACTORY xarm_ros2](https://github.com/xArm-Developer/xarm_ros2/tree/humble)
- [Arm controller configuration](https://github.com/xArm-Developer/xarm_ros2/blob/ac736c92b02de7ca7e0be6f737d77d46707464d8/xarm_controller/config/xarm6_controllers.yaml)
- [Gripper controller configuration](https://github.com/xArm-Developer/xarm_ros2/blob/ac736c92b02de7ca7e0be6f737d77d46707464d8/xarm_controller/config/xarm_gripper_controllers.yaml)
- [Gripper joints and mimic relationships](https://github.com/xArm-Developer/xarm_ros2/blob/ac736c92b02de7ca7e0be6f737d77d46707464d8/xarm_description/urdf/gripper/xarm_gripper.urdf.xacro)
- [Driver SDK-to-joint conversion](https://github.com/xArm-Developer/xarm_ros2/blob/ac736c92b02de7ca7e0be6f737d77d46707464d8/xarm_api/src/xarm_driver.cpp)
- [Gazebo ROS joint-state publisher](https://github.com/ros-simulation/gazebo_ros_pkgs/blob/ros2/gazebo_plugins/src/gazebo_ros_joint_state_publisher.cpp)
- [Vendor mimic plugin: hasPID detection and direct SetPosition path](https://github.com/xArm-Developer/xarm_ros2/blob/ac736c92b02de7ca7e0be6f737d77d46707464d8/xarm_gazebo/src/mimic_joint_plugin.cpp)

The custom package is MIT licensed; vendor dependencies retain their own licenses.
