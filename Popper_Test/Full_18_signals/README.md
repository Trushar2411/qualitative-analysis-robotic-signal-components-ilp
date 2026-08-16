# Single Popper project: 18 signals × 3 relations

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

## Expected learned program

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

## Data counts

- rows: 157
- adjacent pairs per signal: 156
- signals: 18
- positive examples: 2808
- negative examples: 5616
- increases: 453
- decreases: 392
- unchanged: 1963

## Run

```bash
cd ~/Popper
uv run popper.py ../Popper_Test/Full_18_signals --noisy -v
```

This is a self-supervised relation-learning test. The raw values determine the
examples, and Popper learns the three general clauses connecting each comparison
predicate to its relation symbol.
