# Evaluate learned RAW and PLA Popper rules on an unlabeled xArm6 recording

This package **does not train Popper**. It reads the successful hypotheses learned in the supplied `all_results_raw.csv` and `all_results_pla.csv` and evaluates them on a new CSV. No SWI-Prolog installation is required.

## Install

```bash
python3 -m pip install numpy pandas matplotlib
```

## Run on an unlabeled pick-and-place recording

```bash
python3 compare_unlabelled.py '/path/to/unlabelled_pick_place.csv' --out results_new_motion
```

Your input needs `header_stamp_sec` (or `elapsed_sec` / `bag_time_sec`) and the relevant joint/finger `*_position`, `*_velocity`, and `*_effort` columns required by the learned RAW rules. The input **does not need** `phase`, `phase_id`, or `cycle`. All phase labels in a recording, if present, are *ignored* for prediction.

### Recommended if you have PLA-reconstructed telemetry for the new recording

```bash
python3 compare_unlabelled.py '/path/to/unlabelled_pick_place.csv' \
  --pla-csv '/path/to/pla_reconstructed_unlabelled.csv' \
  --out results_with_precomputed_pla
```

The PLA file must contain aligned timestamps/rows and `joint1_position_trend`, `joint1_velocity_trend`, etc. The evaluator takes the majority trend in **fixed, 20-sample, phase-blind windows**, similar to the PLA Popper training task but without phase labels. For better reproducibility, **generate this PLA file using the same PLA reconstruction settings as training**, but without ground-truth-based window boundaries.

If `--pla-csv` is omitted, the script **approximates** PLA by fitting a straight line to each nonoverlapping 20-sample interval and classifying its slope into increasing/decreasing/constant. This fallback is *not guaranteed* to match the earlier segmented PLA pipeline; a difference in predictions may reflect preprocessing differences rather than the rules alone.

### Optional: calculate true phase accuracy and boundary error

**An unlabeled CSV cannot establish the correct phases, true phase-boundary errors, F1, MCC, or which method is more accurate.** You need separate ground-truth annotations. You can supply either:

- A CSV with the same number of rows and a `phase` column, preferably with matching `header_stamp_sec`.
- An interval CSV with `phase,start_s,end_s` in seconds **relative to the start of the recording** (include all known phases, such as `home` and `gripper_opening`).

Example interval file:

```csv
phase,start_s,end_s
home,0.0,5.0
pick,5.0,10.0
gripper_closing,10.0,12.0
lift,12.0,17.0
place,17.0,22.0
gripper_opening,22.0,24.0
retract,24.0,29.0
return_home,29.0,34.0
```

These times are just illustrative; **do not use the example as ground truth for a real recording**.

```bash
python3 compare_unlabelled.py '/path/to/unlabelled_pick_place.csv' \
  --ground-truth '/path/to/actual_phase_intervals.csv' \
  --out scored_results
```

For a labeled CSV whose labels are in the telemetry itself (e.g., a validation recording), you can use `--ground-truth embedded`. Input label columns are never used for feature generation or prediction.

## Output

Always:

- `timestamped_predictions.csv`: per-time-step RAW and PLA rule activations and weighted rule scores.
- `all_detected_episodes.csv`: all detected phase intervals, including duplicates and false candidate episodes.
- `ordered_sequence_proposals.csv`: *heuristic* first chronological episode of each phase, requiring the expected task order. Missing phases are flagged. A complete proposal is NOT verified task success.
- `per_phase_summary.csv`: phase activation duration, fraction of recording detected, episode counts.
- `phase_timeline.png` and `.pdf`: visualization of detected intervals (includes ground-truth shading when supplied).
- `run_info.json`: configuration and caveats.

With ground truth:

- `ground_truth_accuracy.csv`: time-aligned per-phase TP/FP/FN/TN, precision, recall, F1, MCC, specificity, matched/missed/extra episodes, onset and offset errors, episode IoU.
- `matched_boundary_errors.csv`: true and predicted episode start/end times and absolute boundary errors.
- `accuracy_macro.csv`: macro precision, recall, F1, MCC and specificity. The script identifies the higher-F1/higher-MCC method on the given recording.

## Configuration

The RAW method computes `x[i+1] - x[i]` for every source row without windows, using the thresholds in `raw_thresholds.json` from the training task.

The PLA method uses 20-sample, **unlabeled** windows. If you provide a `--pla-csv`, the most frequent trend label is used when supported by at least 80% of that window. Otherwise the slope of each signal is computed using least squares. The slope is then assigned a sign using the same scale of threshold as the RAW method, adjustable via `--pla-slope-factor`.

```bash
python3 compare_unlabelled.py recording.csv --pla-window 20 \
  --smoothing-sec 0.20 --min-episode-sec 0.20 \
  --hypotheses majority --out comparison
```

`--hypotheses ensemble` averages the binary outputs of all distinct learned hypothesis variants weighted by their frequencies in the 10 runs (use `--ensemble-threshold` to change vote threshold). The default `majority` takes the most frequently learned canonical hypothesis per phase.

Smoothing is a **centered offline** majority vote, and therefore uses future observations. It is intended for post-run evaluation, **not online real-time recognition**.

## Interpretation safeguards

1. Complete chronological detection and long rule activation are **proxy measures**, not proof of correct Pick-and-Place recognition.
2. Boundary error, IoU and F1 require actual phase annotations; the script never manufactures them.
3. For a credible RAW-vs-PLA study, use unseen physical/simulated recordings, identical target time samples, and phase-blind signal preprocessing. The supplied learned rules were trained on a previously segmented recording; evaluating that original recording again is an in-sample diagnostic.
4. The training PLA representation was generated from phase-aligned windows. On unseen, unsegmented input, the phase-blind windows can behave differently near phase boundaries. Comparing pipelines under this deployment condition is scientifically useful but should be identified explicitly.
5. For new recordings, signal names and units must match training. The script reports missing feature channels rather than silently weakening rules.


## Applying to another robot (different CSV header)

For a CSV with `bag_time_ns,bag_time_sec,header_stamp_sec`, `joint1_position` through
`joint6_effort`, and `left_finger_position`, `right_finger_position`, etc.,
the evaluator automatically aliases `left_finger_position` to
`left_finger_joint_position` (and similarly for right finger, velocity, effort).
No `phase` or `phase_id` column is required.

```bash
python3 compare_unlabelled.py /path/to/new_robot.csv --out new_robot_results
```

Without `--pla-csv`, the script fits straight-line slopes to non-overlapping
20-sample intervals. **This approximation is not guaranteed equivalent to the
original phase-segmented PLA training pipeline.** Avoid treating the scores as
an apples-to-apples representation comparison unless the PLA procedure is matched.

**Transfer warning:** Joint numbers, axes, control modes, scale/units, finger
kinematics, sampling frequency and phase definitions may all differ across robots.
Same column names do not imply the same physical semantics. Rules were learned
on xArm6 and cannot be assumed valid for another robot. The outputs are candidate
activations rather than proof of pick/place performance. Unlabelled input cannot
produce ground-truth precision, F1, MCC, or phase-boundary error. For evaluation,
annotate true phase start/end times and provide `--ground-truth phases.csv`.
