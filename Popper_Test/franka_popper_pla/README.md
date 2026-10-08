# Franka robot PLA → Popper (five motion phases)

Input: `all_signals_combined_PLA.csv`. The script uses existing **piecewise-linear-approximation labels** (`position_label`, `velocity_label`) for all seven joints and both fingers, without recomputing PLA or manufacturing additional demonstrations.

## Installation on Ubuntu

Requirements: `python3`, `pandas`, SWI-Prolog, and the [Popper repository](https://github.com/logic-and-learning-lab/Popper). In Popper's repository, follow its installation instructions (`uv sync` or dependency installation as applicable). The launcher below calls Popper using the Python environment currently activated. If your environment uses `uv`, run `uv run python ...` for an individual task.

```bash
sudo apt update && sudo apt install -y swi-prolog python3-venv
python3 -m venv .venv
source .venv/bin/activate
python -m pip install pandas
# Install Popper separately following its README, and make its dependencies available in this environment.
```

## Run

Copy `all_signals_combined_PLA.csv` into this folder (included in the zip), then:

```bash
python prepare_popper.py all_signals_combined_PLA.csv --out tasks
# Run one task from the Popper repository, e.g.:
cd /path/to/Popper
uv run popper.py /absolute/path/to/franka_popper_pla/tasks/pick --noisy --timeout 120
```

Or run all five tasks with the supplied wrapper from the project folder **after installing Popper's Python dependencies in the active environment**:

```bash
export POPPER_DIR="$HOME/Popper"  # change this path
bash run_all.sh all_signals_combined_PLA.csv
# optional: TIMEOUT=300 bash run_all.sh all_signals_combined_PLA.csv
```

Results: `results/<phase>.log` and `results/summary.tsv`. A zero exit code means the run completed, **not** that it found an accurate hypothesis. Examine each log.

## What Popper receives

Each time window is **one instance** (`w0000`, etc.) with 9 signals. Each signal has one position PLA label and one velocity PLA label. All of these become logical facts, e.g.:

```prolog
position_finger_1_ramp_down(w0037).
velocity_joint_2_constant(w0037).
```

`tasks/pick/exs.pl` contains positives for **pick** windows and negatives for windows in approach, transport, place, and retract. The other tasks follow the same one-vs-rest pattern. A bias file permits a maximum of 3 clauses and 3 literals per clause, using grounded, readable unary shape predicates. No target label, timestamp, or window identifier may appear in a clause body. All five phases get their own `bk.pl`, `exs.pl`, and `bias.pl`.

A possible rule **illustration, not a learned result**:

```prolog
pick(A) :- position_finger_1_ramp_down(A), position_joint_3_constant(A).
```

This means a pick window can be recognized if finger 1 is closing (if ramp-down represents closing for this dataset) while joint 3 stays approximately constant. Check actual motor sign conventions before applying semantic labels such as closing/opening.

## Critical dataset limits

This CSV contains **513 signal rows = 57 windows**, all from **one demonstration** (`demo_1_labeled`), with **37 approach**, **2 pick**, **15 transport**, **2 place**, and **1 retract** windows. These are not 513 independent training examples. Report training fits as exploratory; phase-level precision/recall on this same demonstration cannot support generalization claims.

`retract` has a single window, and that window has constant trends on all signals. Similar constant windows in other phases make retract hard to distinguish based on trend direction alone. Add more complete demonstrations before trusting any learned rules. Also, the PLA file includes **only trends** of joint/finger position and velocity; it does not establish object contact, whether a grasp succeeds, or whether the cube moves.

## Next steps for a valid experiment

Get PLA for many demonstrations (including different object start positions). Combine into a CSV while retaining `demonstration`. Hold out entire demonstrations before training. Tune signal/shape vocabulary and bias on training demonstrations; evaluate on held-out demonstrations. For each phase, report TP, FP, FN, TN, precision, recall, F1; inspect empty hypotheses and confusing constant windows. You may also compare position-only, velocity-only, and both feature groups.
