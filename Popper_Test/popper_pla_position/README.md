# xArm position phase-summary tasks

The input is `pla_position_phase_summary.csv`. Nine phase summaries supply
one positive and eight negative examples per target. Features are overall
`ramp_up`, `ramp_down`, or `constant` labels for joints 1, 2, 3, and 5. Counts are
retained for inspection and are excluded from the learning predicates.

Each `tasks/PHASE/` folder contains `bk.pl`, `bias.pl`, and `exs.pl`. The bias
permits at most 4 body literals and three clauses. The runner uses strict
learning and omits `--noisy`.

From the repository root:

```bash
bash Popper_Test/popper_pla_position/run_all_phases_strict.sh "$PWD/Popper" 120 1
python Popper_Test/popper_pla_position/verify_results.py Popper_Test/popper_pla_position/RESULTS_DIRECTORY
```

Replace `RESULTS_DIRECTORY` with the folder printed by the launcher. Each run
creates a fresh `results_<timestamp>_<suffix>/` with logs,
`hypothesis_summary.txt`, and `run_status.tsv`. Verification writes
`verified_scores.csv` and rejects unsupported rule syntax. These are training
scores on the same phase summaries.

Home, gripper_opening, pick_delay, and gripper_closing have identical retained
label signatures. Strict learning cannot separate those positives from identical
negatives using these features. A missing hypothesis for those tasks is a data
limitation. Summary trends may also hide mixed window behavior. Effort trend
describes effort change and does not itself establish physical movement.
