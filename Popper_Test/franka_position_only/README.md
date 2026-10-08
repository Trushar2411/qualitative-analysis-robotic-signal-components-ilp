# Franka position-only PLA phase tasks

The preparation script reads existing PLA labels for seven arm joints and two
fingers. Only `position_label` becomes a feature.
Targets are approach, pick, transport, place, and retract, with one-vs-rest
examples. Phase labels, timestamps, and demonstration IDs are excluded from
candidate rule bodies.

One window is one example; nine signal rows describe that same example.
`tasks/window_index.csv` maps window IDs to demonstrations and sample intervals.
Each phase has its own background, examples, and bias, allowing at most three
body literals and three clauses.

From the repository root:

```bash
python Popper_Test/franka_position_only/prepare_popper_position_only.py Popper_Test/franka_position_only/all_signals_combined_PLA_2.csv --out Popper_Test/franka_position_only/tasks
bash Popper_Test/franka_position_only/run_all_phases_position_only.sh "$PWD/Popper" 120 1
```

The runner uses `uv run popper.py` with strict learning and no `--noisy`.
It regenerates tasks from `all_signals_combined_PLA_2.csv` by default. Set `INPUT_CSV` to an absolute path to use another PLA CSV.
It creates a fresh `results_position_only_*` directory containing logs,
`hypothesis_summary.txt`, and `run_status.tsv`. Exit code zero means the command
completed; inspect the log to see whether a hypothesis was found.

For another demonstration, pass its combined PLA CSV from
`FrankaReplay/outputs/PLA/` or a fresh pipeline run. Multiple demonstrations can
be concatenated while retaining `demonstration` identifiers. Preparation rejects
unknown labels, conflicting phases, and duplicate signals within a window.

The included inputs are exploratory single-demonstration examples with few
positive windows for some phases. Repeated runs reuse those windows. Constant
signatures can be shared across phases, so strict learning may find no separating
rule. Joint/finger trends and inferred phases do not verify a successful grasp.
Hold out entire demonstrations before training to evaluate generalization.
