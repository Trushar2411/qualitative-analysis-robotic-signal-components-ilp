# Full-motion PLA trial

This folder retains three standalone PLA variants, two input CSVs, and the saved output directories `pla_output/`, `pla_output_window5/`, and `pla_fixed_output/`. The variants have distinct signal handling and settings. `pla_full_motion.py` analyzes a full multi-joint recording directly,
separately from the per-joint pipeline in `scripts/analysis/`.

From the repository root:

```bash
python archive/full_motion_pla_trials/pla_full_motion.py archive/full_motion_pla_trials/full_motion_joint_states.csv --output-dir /tmp/xarm_trial_PLA
python archive/full_motion_pla_trials/pla_full_motion.py --help
```

Pass an explicit input/output path according to that help. The historical output
folder names record earlier parameter variants; they do not establish the
parameters of a new run. Preserve outputs before rerunning a comparison.
