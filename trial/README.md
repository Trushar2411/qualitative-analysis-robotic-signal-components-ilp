# Full-motion PLA trial

This folder retains `full_motion_joint_states.csv`, a standalone
`pla_full_motion.py`, and two historical output folders, `pla_output/` and
`pla_output_window5/`. The script analyzes a full multi-joint recording directly,
separately from the per-joint pipeline in `scripts/analysis/`.

From the repository root:

```bash
python trial/pla_full_motion.py trial/full_motion_joint_states.csv --output-dir /tmp/xarm_trial_PLA
python trial/pla_full_motion.py --help
```

Pass an explicit input/output path according to that help. The historical output
folder names record earlier parameter variants; they do not establish the
parameters of a new run. Preserve outputs before rerunning a comparison.
