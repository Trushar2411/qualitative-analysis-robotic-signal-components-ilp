# Run 2: Learn `phase_pick/1` From 18 Qualitative Joint-State Signals

## Dataset

- Rows: 157
- Columns: 22
- Signals used: 18 = 6 joints x position, velocity, effort

## Qualitative Encoding

For every consecutive pair of rows that remains inside the same phase:

```text
delta = value[row+1] - value[row]
```

Position:

- `increases` if `delta > 0.002`
- `decreases` if `delta < -0.002`
- `constant` otherwise

Velocity:

- `increases` if `delta > 0.01`
- `decreases` if `delta < -0.01`
- `constant` otherwise

Effort:

- `increases` if `delta > 0.05`
- `decreases` if `delta < -0.05`
- `constant` otherwise

## Training Examples

- Positive examples: 47 transitions inside `pick`
- Negative examples: 101 transitions inside all non-pick phases

## Important

The phase column is used only for creating positive and negative labels.
There is deliberately no `phase(sN,pick)` fact in `bk.pl`. Otherwise Popper
could learn the trivial leakage rule:

```prolog
phase_pick(A) :- phase(A,pick).
```

## Run

From the Popper repository root, if this folder is copied there:

```bash
uv run popper.py ../Popper_Test/Phase_pick --noisy -v
```

## Regenerate

```bash
python generate_run2.py /path/to/full_motion_joint_states.csv Run2_phase_pick
```
