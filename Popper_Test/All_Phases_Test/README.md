# All xArm phase targets

`set_target.py` rewrites the shared `bias.pl` and `exs.pl` for a selected phase.
`bk.pl` contains qualitative position, velocity, and effort facts. Deadbands are
0.002, 0.01, and 0.05 respectively. The nine targets are home, gripper_opening,
pick, pick_delay, gripper_closing, lift, place, retract, and return_home.

From the repository root:

```bash
bash Popper_Test/All_Phases_Test/run_all_phases_10_times.sh "$PWD/Popper"
```

This runs each target ten times, replaces `all_phases_hypothesis_summary.txt`,
and leaves `bias.pl` and `exs.pl` configured for the last target. It is a serial
runner; do not run concurrent targets against those shared files.

To select one target and run it:

```bash
python Popper_Test/All_Phases_Test/set_target.py lift
cd Popper
uv run popper.py ../Popper_Test/All_Phases_Test --noisy -v
```

`generate_all_phases.py` separately creates per-phase tasks in the nested
`All_Phases_Test/` folder. It accepts optional source CSV and output directory
positional arguments. Its default input is the bundled full-motion CSV. These
nested tasks are separate from the shared task used by the ten-run launcher.
