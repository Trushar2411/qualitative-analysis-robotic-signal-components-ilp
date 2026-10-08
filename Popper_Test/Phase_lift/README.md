# xArm lift-phase task

This folder retains a full-motion CSV, Popper task files, a generator, and a
captured hypothesis summary. Position, velocity, and effort deltas use
thresholds 0.002, 0.01, and 0.05 respectively.

From the repository root:

```bash
cd Popper
uv run popper.py ../Popper_Test/Phase_lift --noisy -v
```

Regenerate into a separate folder from the repository root:

```bash
python Popper_Test/Phase_lift/generate_run3_lift.py Popper_Test/Phase_lift/full_motion_joint_states.csv /tmp/xarm_lift_task
```

With no arguments, the generator reads its bundled CSV and creates local
`Run3_phase_lift/`. The saved summary reflects a training run on the task files.
