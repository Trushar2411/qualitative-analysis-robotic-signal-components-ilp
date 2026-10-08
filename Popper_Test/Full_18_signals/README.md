# Signal-change relation task

The target is `signal_change(Signal, Time, Relation)`. It maps qualitative
comparison facts to `increases`, `decreases`, or `unchanged` for six joints,
each with position, velocity, and effort signals.

The folder contains `bk.pl`, `bias.pl`, `exs.pl`, and a saved `hypothesis.pl`.
No source CSV or regeneration script is included here. Inspect the task files
for the exact facts and examples.

From the repository root:

```bash
cd Popper
uv run popper.py ../Popper_Test/Full_18_signals --noisy -v
```

Examples and comparison predicates encode the same signal-change relation.
This is a check of relation learning; it does not classify action phases or faults.
