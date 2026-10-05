# Updated position PLA Popper

Built from the supplied pla_position_phase_summary(1).csv, retained here as
pla_position_phase_summary.csv. All nine phases are included: home,
gripper_opening, pick, pick_delay, gripper_closing, lift, place, retract,
return_home. Each task has bias.pl, exs.pl and bk.pl, one positive and eight
negative examples. Static facts/examples are grouped to avoid warnings.

Features are the overall position labels for joints 1,2,3,5. Joints 4 and 6,
which have constant summary labels throughout, are excluded. No seen
predicates, count features or minimum-body constraints. max_body(4) and
max_clauses(3) are upper bounds. Phase names appear only in examples, not BK.

Extract under Popper_Test, enter popper_pla_position_updated, then run:

```bash
bash run_all_phases_uv.sh ../../Popper 120 1
```

The runner always uses uv run popper.py with --noisy and creates a fresh
results folder with individual logs, hypothesis_summary.txt and run_status.tsv.
The last two arguments are timeout seconds and number of runs per phase.

Check final unary joint-trend rules directly against this CSV with:

```bash
python3 verify_results.py results_YOUR_FOLDER_NAME
```

Use the actual results folder printed by the runner. This creates
verified_scores.csv with training scores. Unsupported rule syntax is rejected.

home, gripper_opening, pick_delay and gripper_closing have identical overall
labels. They cannot be perfectly distinguished with these features. Noisy
learning may yield approximate rules or no hypothesis. There is only one
positive example per phase, regardless of the number of windows summarized.
Repeated runs are not new data or independent validation.

The gripper_opening counts still contain one moving window for joints
1,2,3,5. These count columns are not learning features here, but this CSV
does not establish that all opening windows are stationary. The phase summary
also does not show whether the original windows overlap.

Input label/count consistency, example counts, allowed predicates and
Python/Bash syntax were checked. Popper was not run during preparation.
