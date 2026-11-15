# RAW adjacent-sample Noisy Popper (10 repetitions)

This package uses the provided xArm6 CSV to build eight one-versus-rest Popper tasks. No windows and no PLA are used. Every example is one pair of adjacent samples from the *same phase_id / phase / cycle*.

`delta = signal[t+1] - signal[t]`

- `delta > threshold`: `signal_increases(t_id)`
- `delta < -threshold`: `signal_decreases(t_id)`
- otherwise: `signal_constant(t_id)`

Applies to joint1-6 position, velocity and effort, plus left/right finger position and velocity (22 signals; finger effort columns are all NaN and are omitted). The names for velocity/effort mean *their changes*, not positive/negative velocity or torque values.

The output includes `generated_raw_nextstep/transitions.csv` with sample indices and timestamps, eight phase directories with `bk.pl`, `exs.pl`, `bias.pl`, and a `manifest.json` documenting settings.

## Run existing prepared tasks (on Ubuntu)

From this experiment directory, allocate a fresh run directory:

```bash
run_dir="$(mktemp -d)"
python3 run_raw_nextstep_10x.py \
  generated_raw_nextstep \
  "$PWD/../../Popper" \
  120 --runs 10 --output "$run_dir/repeated_runs"
```

The saved historical outputs remain in `generated_raw_nextstep/repeated_runs/`: `all_results.csv`, `hypothesis_frequencies.csv`, `merged_hypotheses.md` and individual logs.

## Regenerate from raw CSV

```bash
python3 prepare_raw_nextstep_popper.py \
  '/absolute/path/to/full_motion_joint_states(20261111-191003)(4).csv' \
  --out "$run_dir/tasks" \
  --position-threshold 0.0001 \
  --velocity-threshold 0.0001 \
  --effort-threshold 0.001 \
  --max-predicates 12 --seed 42
```

Default thresholds are **per sample difference**; they are illustrative, tunable hyperparameters, not sensor-certified noise floors. You can also set all thresholds to zero to enforce literal mathematical sign at the cost of sensitivity to floating-point noise. Popper tasks are generated with a deterministic subset of negatives at a 2:1 negative-to-positive ratio; change `--max-neg-ratio` to 0 to include every other-phase transition as a negative example. By default, 12 discriminative features are screened independently for each phase; increase `--max-predicates` for broader hypothesis search (potentially much slower).

`retract_phase/1` is used to avoid conflict with SWI-Prolog's built-in `retract/1`. `bk.pl` facts are written grouped by predicate to avoid discontiguous warnings.

## Experimental cautions

This recording contains only one complete cycle. Ten runs on unchanged data do not constitute ten independent tests. Accuracy from Popper's final solution is on its selected training examples; it is NOT accuracy on the entire motion or on a held-out recording. Also, because RAW now uses 1-step transitions and PLA used 20-sample windows, the examples and denominators differ: do not claim that a raw-vs-PLA accuracy difference isolates the effect of PLA alone unless the evaluation is performed on the same held-out time intervals.

See the [reproduction guide](../../docs/reproduction.md#generate-raw-and-pla-tasks) for checked-in input paths and the paired workflow.
