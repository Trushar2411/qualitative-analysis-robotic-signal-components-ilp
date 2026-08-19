# Popper Tests

This folder contains Popper ILP experiments built from the robot signal data.
Each test folder is a self-contained Popper task with examples, background
knowledge, and bias files.

## Test Folders

- `Phase_pick/`: learns `phase_pick/1` from 18 qualitative joint-state signals.
- `Phase_pick_2/`: second pick-phase experiment with generated summaries.
- `Phase_lift/`: lift-phase experiment.
- `All_Phases_Test/`: phase-classification experiments for all detected phases.
- `Full_18_signals/`: self-supervised relation-learning test across all 18
  joint-state signals.

## Common Popper Files

- `bk.pl`: background knowledge and generated qualitative facts.
- `bias.pl`: Popper search constraints and target declaration.
- `exs.pl`: positive and negative examples.
- `hypothesis.pl`: learned hypothesis when present.
- `*_summary.txt`: captured run summaries and learned clauses.

Run commands are documented inside each experiment folder.
