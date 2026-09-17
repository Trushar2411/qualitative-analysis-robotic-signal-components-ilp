# Six object placements: velocity and effort Popper comparison

`datasets/` contains 48 independent tasks: six recordings × eight phases.
The six datasets follow the order in `datasets/input_counts.csv`.

The transformation follows the earlier velocity-only package: for two adjacent
rows with the **same** phase, compare each joint's velocity and effort at row
N+1 with row N. For each signal, a difference greater than 0.01 is `increases`,
less than -0.01 is `decreases`, and the rest is `constant`. These fixed
deadbands are applied consistently to all six recordings; edit the two
constants near the top of `build_inputs.py` to change them. Transitions
crossing a phase boundary are dropped.
For each phase, positives are its transitions and negatives are transitions in
the other phases of **that same recording**. Position is excluded. The 36
velocity and effort predicates and the same bias are used for every recording.
Joints 4 and 6 have zero velocity throughout these CSVs, so their velocity
predicates are always `constant`.

Copy the package to your machine with Popper installed, then run:

```bash
RUNS=10 bash run_all.sh /absolute/path/to/your/Popper
```

The script writes `results/hypothesis_summary.txt` and retains each full output
in `results/logs/`. For a quick pipeline check, set `RUNS=1` first. Runs are
independent; no data from another placement appears in a task. A repeated rule
across placements is evidence of consistency, but the training precision and
recall printed by Popper are **not** held-out generalization scores. Some
phases have very few examples (dataset 5 has no `home` transitions), so their
rules should be interpreted cautiously. For unbiased transfer testing, learn
on five recordings and score on the sixth as a separate experiment.

To regenerate tasks if the CSVs change:

```bash
python3 build_inputs.py /absolute/path/to/csv_directory
```

The source directory must contain exactly the six `full_motion_joint_states*.csv`
files. Renaming or changing their sort order changes the `dataset_N` mapping.
