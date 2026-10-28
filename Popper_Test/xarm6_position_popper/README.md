# xArm6 position-only Popper project

This dataset records **xArm6** (six arm joints), with a gripper. It is not the earlier seven-joint Franka Panda dataset.

## Input and target actions

Input: `full_motion_joint_states(20261028-205807).csv` (4,457 time samples).

The eight **actual CSV phase labels** are: `home`, `gripper_opening`, `pick`, `gripper_closing`, `lift`, `place`, `retract`, `return_home`. There are nine consecutive `phase_id` steps because `gripper_opening` occurs twice.

The generator does not rename `lift` to `transport`, nor split the supplied `pick` phase into `approach` without evidence. Learning targets follow the CSV's real labels.

## Signals and qualitative encoding

Uses only six `joint*_position` fields plus `left_finger_joint_position`, `right_finger_joint_position`. Other gripper position columns are near-duplicates and excluded from the default bias. No velocities, efforts or timestamps are used as Popper body predicates (timestamps are used only to calculate the slope). For each *consecutive* phase segment, non-overlapping 20-sample windows are fitted with a straight line, using the fitted change to classify `increases`, `decreases`, or `constant`. Thresholds: arm 0.004 radians, fingers 0.001 radians. Thresholds are configurable; these are pragmatic defaults, not validated physical tolerances.

Each window becomes a unique Prolog constant (`w00000`, etc.) with position-trend facts. Every phase receives one-vs-rest positive and negative examples. The background knowledge is sorted by predicate to avoid SWI-Prolog discontiguous warnings.

## Ubuntu usage

```bash
cd xarm6_position_popper
python3 -m pip install pandas numpy   # only if missing
python3 prepare_popper.py 'full_motion_joint_states(20261028-205807).csv'
bash run_all_phases_strict.sh /home/tezz/Trushar/qualitative-analysis-robotic-signal-components-ilp/Popper 120 1
```

The runner automatically calls `prepare_popper.py`, then `uv run popper.py <task> --timeout <seconds>` **without** `--noisy`. It stores a new, timestamped `results_*/hypothesis_summary.txt` and individual logs. The runner must have a working `uv` installation in the Popper repository, plus SWI-Prolog.

To use another CSV with the **same columns**:

```bash
INPUT_CSV=/absolute/path/to/another.csv bash run_all_phases_strict.sh /absolute/path/to/Popper 120 1
```

To change window sizes or thresholds, invoke `prepare_popper.py --help`; note the runner regenerates tasks with default settings unless you edit its `python3 prepare_popper.py` call.

## Interpretation and limitations

The CSV has one `cycle` and is insufficient for independent evaluation or reliable cross-run generalization. The two gripper opening occurrences share a target label but are separate time segments. The exact shape trends may not distinguish all actions. Popper was **not run** when this project was generated, so no hypotheses or precision/recall scores are claimed. An exit code of zero does not guarantee a satisfactory hypothesis.
