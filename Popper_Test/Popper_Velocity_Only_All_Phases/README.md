# xArm velocity only phase tasks

Each phase directory contains its own `bk.pl`, `bias.pl`, and `exs.pl`.
The features are adjacent-sample changes in velocity only, labeled `increases`,
`decreases`, or `constant`. There are 18 candidate body predicates.
Position is excluded. The fixed delta deadband is 0.01 for the included signals.

The tasks cover home, gripper_opening, pick, pick_delay, gripper_closing,
lift, place, retract, and return_home. Background predicate declarations
prevent discontiguous-clause warnings without changing the facts.

From the repository root:

```bash
RUNS=10 bash Popper_Test/Popper_Velocity_Only_All_Phases/run_all_phases.sh "$PWD/Popper"
```

The default is ten repeats. The launcher replaces `hypothesis_summary.txt`
in this experiment folder and collects final clauses and score lines.
It does not retain separate per-run logs. Repeats use the same task examples;
report their scores as training fits.
