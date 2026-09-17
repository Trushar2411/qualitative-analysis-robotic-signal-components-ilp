# Pooled Popper models for all six placements

The six CSVs are **pooled before learning**. There are eight Popper tasks, one
for each phase. Each task has positive transitions for its phase from all six
recordings and negative transitions for the other phases from all six
recordings. Dataset 5 contributes no `home` positives, but the other five do.

Each state has a unique name: `d3_s42` means dataset 3, CSV row 42 to 43.
The mapping between dataset numbers and filenames, together with phase
counts, is in `tasks/input_counts.csv`. Transitions across phase boundaries
are excluded. No facts mix adjacent rows from different recordings.

Each joint contributes six candidate predicates: velocity and effort, each
classified as `increases`, `decreases`, or `constant` by comparing consecutive
values with a fixed 0.01 deadband. Position is excluded. The bias has 36 body
predicates, `max_vars(1)`, `max_body(4)`, and `max_clauses(3)`.
Joint 4 and joint 6 velocity stay zero in all six source CSVs.

From the unpacked directory, with Popper, uv, and swipl installed:

```bash
RUNS=1 bash run_pooled.sh /absolute/path/to/Popper
RUNS=10 bash run_pooled.sh /absolute/path/to/Popper
```

The second command replaces the first summary. It writes
`results/hypothesis_summary.txt` and full per-run output in `results/logs/`.
The file `tasks/place/exs.pl` now contains examples from all placements;
the same is true for each other phase. Training precision and recall on the
pooled data do not measure performance on a previously unseen placement.

To regenerate from the six CSVs:

```bash
python3 build_pooled.py /absolute/path/to/csv_directory
```
