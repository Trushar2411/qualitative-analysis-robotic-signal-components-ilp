# Strict Popper for updated effort data

Uses the supplied nine-row effort phase summary. Joints 1–5 are retained, including joint 4; joint 6 is excluded. Only the summary labels ramp_up, ramp_down and constant become background facts. Counts are not used as predictors. Targets are phases, with one positive and eight negative examples per task. Facts do not contain phase names.

## Run

Requires uv, SWI-Prolog and your Popper checkout with its dependencies configured.
Extract this folder under Popper_Test and run from inside it:

```bash
bash run_all_phases_strict.sh ../../Popper 120 1
```

Or pass the absolute path to your Popper checkout. The script runs `uv run popper.py TASK --timeout 120` from that checkout. It never passes --noisy. The final argument controls repeated runs; these reuse the same data and are not cross-validation.

Each phase has tasks/PHASE/bias.pl, exs.pl and bk.pl. The bias permits up to five body literals and three clauses, with no minimum body length. Popper may choose a shorter rule and does not enumerate every equivalent rule.

A fresh results directory contains individual logs, hypothesis_summary.txt and run_status.tsv. Exit code 0 alone does not mean a hypothesis was found.

## Independently check results

Replace RESULTS_DIRECTORY with the directory printed by the runner:

```bash
uv run python verify_results.py RESULTS_DIRECTORY
```

This writes verified_scores.csv by evaluating final supported rules directly against the input summary. These are training scores, not evidence of generalization.

## Identical examples

home, gripper_opening, pick_delay and gripper_closing all have the same constant joint 1–5 signature. Each such task has identical positive and negative feature vectors, so strict learning cannot separate them using this background knowledge. NO SOLUTION is expected for these tasks. To distinguish them, supply additional real information such as gripper state or temporal context. The package does not change labels or add features that encode the answer.

Effort trends describe changes in effort, not necessarily physical joint movement. A summary label may hide mixed window trends; the original counts remain in the included CSV for inspection.
