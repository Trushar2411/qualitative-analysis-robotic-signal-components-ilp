All Phases Popper Test

Detected phases in the uploaded CSV:
- home
- gripper_opening
- pick
- pick_delay
- gripper_closing
- lift
- place
- retract
- return_home

Files:
- full_motion_joint_states.csv: source data
- bk.pl: one shared qualitative BK for all targets
- set_target.py: rewrites bias.pl and exs.pl for one selected phase
- bias.pl / exs.pl: initialized below for 'home'
- run_all_phases_10_times.sh: runs all 9 targets 10 times each
- all_phases_hypothesis_summary.txt: created only when the run script executes

Deadbands:
- position: 0.002 rad
- velocity: 0.01 rad/s
- effort: 0.05 in /joint_states effort units

Run all:
cd ~/qualitative-analysis-robotic-signal-components-ilp/Popper
../Popper_Test/All_Phases_Test/run_all_phases_10_times.sh "$PWD"

Or set one target:
python3 ../Popper_Test/All_Phases_Test/set_target.py lift
uv run popper.py ../Popper_Test/All_Phases_Test --noisy -v
