# Popper No-Position Experiment — Clean Version

This experiment completely removes all joint-position information.

## Signals available to Popper

- 6 joint velocity signals
- 6 joint effort signals
- 3 qualitative relations per signal: `increases`, `decreases`, `constant`

Total candidate body predicates: 36.

## SWI-Prolog warning suppression

Every phase `bk.pl` now starts with declarations such as:

```prolog
:- discontiguous j1_vel_increases/1.
:- discontiguous j1_vel_decreases/1.
:- discontiguous j1_vel_constant/1.

:- discontiguous j1_eff_increases/1.
:- discontiguous j1_eff_decreases/1.
:- discontiguous j1_eff_constant/1.
```

The same declarations are included for joints 2–6. They suppress the
`Clauses ... are not together in the source-file` warnings and do not change
the learned logic.

## Run all phases 10 times

```bash
cd /path/to/Popper_No_Position_All_Phases_Clean
chmod +x run_all_phases.sh
./run_all_phases.sh ~/qualitative-analysis-robotic-signal-components-ilp/Popper
```

The script creates only:

```text
hypothesis_summary.txt
```

It does not create separate logs or hypothesis files.

The summary contains, for each phase and each of 10 runs:

- final Precision / Recall / TP / FN / TN / FP / Size / MDL line
- final learned hypothesis rule(s)

To change the number of repetitions temporarily:

```bash
RUNS=3 ./run_all_phases.sh ~/qualitative-analysis-robotic-signal-components-ilp/Popper
```
