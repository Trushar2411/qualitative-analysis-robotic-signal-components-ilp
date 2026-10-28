# Update an existing installation

Version 0.1.4 raises the fixed base to 1.0 metre above the floor to clear the gripper in the folded starting pose. The height is part of `world_joint` in the robot description, so ROS TF and Gazebo agree. Start with `base_height:=1.0`; the launch prints the configured mount height.

This revision initializes the gripper to 0.33 rad and waits for stable actual finger readings before opening the rosbag. Both recorded opening steps should now decrease from 0.33 to 0.15 rad. Repeated cycles include a labelled `gripper_reset` between cycles.

CSV exports now exclude the `idle` phase. Holds during task phases remain included, and timestamps keep their original values. The rosbag retains the complete recording. The standalone `scripts/remove_idle_rows.py` can remove idle rows from an existing CSV without ROS; see README.md.

Version 0.1.3 also defaults the passive finger plugins to kinematic position following, avoiding PID follower offsets blocking the 0.33-rad initialization in this position-only scene. The initialization tolerances and settling gate remain active. This mode represents ideal coupling rather than independent finger dynamics. To opt into the vendor PID mode, use `gripper_mimic_mode:=pid`.

1. Stop the previous simulation with Ctrl+C.
2. Replace the contents of your previous extracted `xarm6_simulation` folder with this updated folder. Keep its location the same so your workspace's package link continues to work.
3. In a fresh Ubuntu terminal, rebuild the custom package:

```bash
source /opt/ros/humble/setup.bash
cd ~/jessie_sim_ws
colcon build --symlink-install --packages-select xarm6_pick_place_sim
source install/setup.bash
ros2 launch xarm6_pick_place_sim simulation.launch.py record:=true
```

If your workspace has another location, use that location in the `cd` command. There is no need to clone the vendor repository again.

If you followed the later `install_updated` workflow, use these build and source paths instead, after extracting the updated ZIP into the repository:

```bash
source /opt/ros/humble/setup.bash
source ~/jessie_sim_ws/install/setup.bash
cd ~/jessie_sim_ws
colcon build \
  --base-paths ~/qualitative-analysis-robotic-signal-components-ilp/xarm6_simulation/src/xarm6_pick_place_sim \
  --packages-select xarm6_pick_place_sim \
  --build-base build_updated \
  --install-base install_updated \
  --symlink-install
source ~/jessie_sim_ws/install_updated/setup.bash
ros2 launch xarm6_pick_place_sim simulation.launch.py record:=true
```

Stop the old Gazebo process before launching again; the new mimic mode is part of the spawned model.

The console will print `Initializing gripper at 0.330 rad...`, followed by `Gripper settled at 0.330 rad.` before `Recording to ...`. If initialization fails, the runner exits without beginning a recording.

The generated CSV should show approximately 0.33 rad for `drive_joint_position` during the initial home phase, then 0.33 -> 0.15 during the first opening, 0.15 -> 0.33 during closing, and 0.33 -> 0.15 during the second opening. The five mimic joints may have small simulation offsets.

This revision changes initialization. It does not repair zero-reported velocity fields in the earlier recording; position-only analysis remains the intended workflow here. New simulation runs are needed to obtain the corrected first opening. The previously saved CSV is unchanged.
