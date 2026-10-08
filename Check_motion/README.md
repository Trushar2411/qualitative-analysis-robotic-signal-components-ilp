# Command-line motion checker

`check_pick_place.py` applies fixed qualitative phase rules to a supplied xArm
joint-state CSV. It compares adjacent samples, identifies phase matches, and
checks an ordered pick-and-place sequence. It does not load or train a new
Popper hypothesis.

From the repository root:

```bash
python Check_motion/check_pick_place.py Check_motion/full_motion_joint_states.csv
python Check_motion/check_pick_place.py --help
```

`--min-consecutive` controls the minimum matching block length; `--output-csv`
writes transition-level matches. The CSV must contain the joint signal columns
used by `RULES` in the script. A detected sequence describes agreement with
those rules; object pickup needs independent evidence.
