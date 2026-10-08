# Six-placement independent velocity/effort tasks

The six recordings remain separate: `datasets/` contains 48 tasks,
one for each recording and each of eight phases.
Each adjacent-row transition is retained only when both rows have the same
phase. Velocity and effort differences use a 0.01 deadband; position is excluded.
Six joints and three labels per signal produce 36 candidate body predicates.

The recording order and phase counts are recorded in `datasets/input_counts.csv`.
Dataset 5 has no home transitions in the included source mapping. Joint 4 and
joint 6 velocity were constant in those source recordings. Regenerating with
other files requires checking these properties again.

From the repository root:

```bash
RUNS=10 bash Popper_Test/Six_Placement_Velocity_Effort_Popper/run_all.sh "$PWD/Popper"
python Popper_Test/Six_Placement_Velocity_Effort_Popper/build_inputs.py /absolute/path/to/six_csvs
```

Generation expects exactly six `full_motion_joint_states*.csv` files. File sort
order determines dataset numbering. The launcher writes
`results/hypothesis_summary.txt` and per-run `results/logs/`, replacing matching
outputs on another run. Use a copy or preserve results before repeating.

The learning scores use the generated training tasks. Repeated runs do not
supply independent recordings. Hold out a whole recording to assess transfer
across object placements.
