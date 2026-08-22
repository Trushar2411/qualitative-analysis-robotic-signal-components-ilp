# Popper Velocity-Only All-Phases

This experiment removes both position and effort.

Signals available:
- joint1_velocity ... joint6_velocity

Relations:
- increases
- decreases
- constant

Velocity deadband: 0.01

Total candidate body predicates: 18.

All phases found in the CSV are included:
- home
- gripper_opening
- pick
- pick_delay
- gripper_closing
- lift
- place
- retract
- return_home

Run:
```bash
cd /path/to/Popper_Velocity_Only_All_Phases
chmod +x run_all_phases.sh
./run_all_phases.sh ~/qualitative-analysis-robotic-signal-components-ilp/Popper
```

The shell script runs every phase 10 times and creates one file only:
`hypothesis_summary.txt`.
