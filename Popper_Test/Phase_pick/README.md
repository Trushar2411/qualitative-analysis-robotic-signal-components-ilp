# xArm pick-phase task

This task learns `phase_pick/1` from adjacent samples within the same phase.
Six joints contribute position, velocity, and effort changes. Delta deadbands
are 0.002 for position, 0.01 for velocity, and 0.05 for reported effort.
Phase labels create examples and are excluded from background facts.

From the repository root:

```bash
cd Popper
uv run popper.py ../Popper_Test/Phase_pick --noisy -v
```

The folder retains the source CSV, task files, and a saved `hypothesis.pl`.
Regenerate into a separate folder from the repository root:

```bash
python Popper_Test/Phase_pick/generate_run2.py Popper_Test/Phase_pick/full_motion_joint_states.csv /tmp/xarm_pick_task
```

The generator defaults to its bundled CSV and a local `Run2_phase_pick/` output
folder. A saved hypothesis describes the training examples used for that run;
use a separate recording to assess transfer.
