# Saved second pick-phase task

This folder contains `bk.pl`, `bias.pl`, `exs.pl`, and a captured
`hypothesis_summary.txt`. The task files define the experiment; there is no
source CSV or generator in this folder.

From the repository root:

```bash
cd Popper
uv run popper.py ../Popper_Test/Phase_pick_2 --noisy -v
```

Inspect the bias and examples when comparing this task with `../Phase_pick/`.
The captured output is a historical training run, not an independent test.
