# Single Popper Project: 18 Signals x 3 Relations

This project uses all six joints and all three signal classes:

- position
- velocity
- effort

There are 18 signals total and three relations:

- `increases`
- `decreases`
- `unchanged`

The target is:

```prolog
signal_change(Signal, Time, Relation).
```

Examples are generated automatically from adjacent raw CSV rows. No action,
phase, fault, pick, or place labels are used.

## Expected Learned Program

```prolog
signal_change(S,T,R):-
    signal_increases(S,T),
    relation_increases(R).

signal_change(S,T,R):-
    signal_decreases(S,T),
    relation_decreases(R).

signal_change(S,T,R):-
    signal_unchanged(S,T),
    relation_unchanged(R).
```

## Data Counts

- Rows: 157
- Adjacent pairs per signal: 156
- Signals: 18
- Positive examples: 2808
- Negative examples: 5616
- Increases: 453
- Decreases: 392
- Unchanged: 1963

## Run

```bash
cd ~/Popper
uv run popper.py ../Popper_Test/Full_18_signals --noisy -v
```

This is a self-supervised relation-learning test. The raw values determine the
examples, and Popper learns the three general clauses connecting each comparison
predicate to its relation symbol.
