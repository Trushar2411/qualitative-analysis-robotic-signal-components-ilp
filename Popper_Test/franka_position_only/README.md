# Franka position-only Popper tasks

This pipeline reads only `position_label` for 7 joints + 2 fingers. It excludes all velocity and effort predicates from both `bk.pl` and `bias.pl`. It creates one-vs-rest tasks for approach, pick, transport, place, retract and runs Popper with strict learning.

## Run on Ubuntu
```bash
chmod +x run_all_phases_position_only.sh
bash run_all_phases_position_only.sh
# optional: custom Popper location, timeout, and repeats
bash run_all_phases_position_only.sh /home/tezz/Trushar/qualitative-analysis-robotic-signal-components-ilp/Popper 120 1
```
Requirements: `python3` with pandas, `swipl`, and `uv`. Popper dependencies must be installed in Popper's uv environment.

The launcher regenerates `tasks/` automatically; logs are in a new `results_position_only_*` folder and combined hypotheses are in `hypothesis_summary.txt`. Multiple runs on the same windows are not independent validation. Only one demonstration is present; pick, place and retract have very few positive windows.
