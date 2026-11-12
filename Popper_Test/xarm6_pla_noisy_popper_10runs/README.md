# xArm6 PLA Noisy Popper: 10-run experiment

Input: `pla_window20_reconstructed(1).csv` (4455 samples, one complete pick-and-place cycle).

**This package consumes the existing `*_trend` columns from the reconstructed PLA CSV.** It does not fit PLA again, and does not derive trends from reconstructed numeric `*_pla` columns. Each trend becomes exactly one `increases`, `decreases`, or `constant` predicate for its respective joint/finger position/velocity. Uses the 6 arm joints and left/right finger positions/velocities. The input has no joint-effort columns, so effort predicates are absent.

Phase windows: 20 consecutive samples (~0.2 seconds), non-overlapping and kept within one `phase_id`; a terminal window shorter than 80% of this length is discarded. A unique majority trend is selected for every signal in each window. Labels are used only to define the positive/negative examples and rank candidate predicates; phase labels are **not included in background knowledge**. Up to 12 predicates are selected per phase, negatives are limited to twice positives, and bias allows up to 2 clauses of 3 body literals.

There are eight binary classification tasks: `home`, `gripper_opening`, `pick`, `gripper_closing`, `lift`, `place`, `retract`, `return_home`. The retract task's Prolog head is `retract_phase/1` to avoid conflict with SWI-Prolog built-in `retract/1`. Folders remain named `retract` for consistency.

## Run on Ubuntu

Extract the ZIP, enter its `xarm6_pla_noisy_10runs` directory and execute:

```bash
python3 run_pla_noisy_10x.py generated_pla_3states \
  /home/tezz/Trushar/qualitative-analysis-robotic-signal-components-ilp/Popper \
  120 --runs 10
```

The second argument is the **Popper folder** containing `popper.py`, not the `popper.py` file. This requires your installed `uv` or appropriate Python/Popper dependencies. It executes Popper with `--noisy` for each task, 10 repeats. Individual outputs and merged summaries are written under `generated_pla_3states/repeated_runs/`:

- `run_01/logs/<phase>.log` … `run_10/logs/<phase>.log` and per-run `statuses.json`
- `merged_hypotheses.md`: final hypotheses and their frequencies
- `hypothesis_frequencies.csv`: frequencies and mean training precision/recall
- `all_results.csv`: one row per run/phase with TP, FP, FN, TN, precision, recall, F1, size, MDL

To regenerate the tasks with the original uploaded PLA CSV:

```bash
python3 prepare_pla_popper.py '/path/to/pla_window20_reconstructed(1).csv' \
  --out generated_pla_3states --window-size 20
```

To use a 50-sample window instead, pass `--window-size 50` and use a distinct output directory. **The earlier RAW experiment used 50-sample windows, not 20**, and included joint-effort signals, which the PLA CSV does not include. For an experimentally controlled RAW-vs-PLA comparison, regenerate both with identical windows, split, channels, and negative examples. The current PLA samples all come from **one cycle**; 10 repetitions are not an independent generalization test.
