# Popper experiments

Each task uses `bk.pl` for signal facts, `exs.pl` for positive/negative examples,
and `bias.pl` for the target and search constraints. Experiment folders can
contain multiple tasks, source CSVs, and captured runs.

| Experiment | Features and scope |
|---|---|
| [Phase_pick](Phase_pick/README.md) | Adjacent-sample position, velocity, and effort; pick target |
| [Phase_pick_2](Phase_pick_2/README.md) | Separate saved pick task and captured output |
| [Phase_lift](Phase_lift/README.md) | Adjacent-sample signals; lift target |
| [All_Phases_Test](All_Phases_Test/README.md) | Shared xArm background knowledge; nine phase targets |
| [Full_18_signals](Full_18_signals/README.md) | Signal-change relation learning, without phase targets |
| [Popper_No_Position_All_Phases](Popper_No_Position_All_Phases/README.md) | Velocity and effort; nine phases |
| [Popper_Velocity_Only_All_Phases](Popper_Velocity_Only_All_Phases/README.md) | Velocity only; nine phases |
| [Six_Placement_Velocity_Effort_Popper](Six_Placement_Velocity_Effort_Popper/README.md) | Independent tasks for six recordings |
| [Six_Placements_Pooled_Velocity_Effort_Popper](Six_Placements_Pooled_Velocity_Effort_Popper/README.md) | Six recordings pooled into phase tasks |
| [popper_pla_position](popper_pla_position/README.md) | xArm position phase-summary labels |
| [popper_pla_effort](popper_pla_effort/README.md) | xArm effort phase-summary labels |
| [franka_popper_pla](franka_popper_pla/README.md) | Franka position and velocity window labels |
| [franka_position_only](franka_position_only/README.md) | Franka position window labels |

Install the repository's `Popper/` submodule, its Python dependencies, `uv`, and
SWI-Prolog. Commands in these guides assume the repository root unless stated
otherwise. For one task:

```bash
cd Popper
uv run popper.py ../Popper_Test/Phase_pick --noisy -v
```

Some experiments permit noisy learning; the PLA strict runners omit `--noisy`.
Do not compare their results without recording this setting. Captured results
are historical runs. Repeated runs reuse the same examples; training precision
and recall do not measure performance on an unseen demonstration.
