# Pick-and-place: joint and finger position Popper inputs

Independent tasks matching the structure of `Six_Placement_Velocity_Effort_Popper`,
using all 258 recordings (`demo_0` through `demo_257`). The last run ID is 257;
there are 258 files because numbering starts at zero. No Popper execution is performed.

Each `datasets/demo_N/<phase>/` contains `bias.pl`, `bk.pl`, and `exs.pl`.
The five targets are `phase_approach`, `phase_pick`, `phase_transport`,
`phase_place`, and `phase_retract`. `datasets/input_counts.csv` lists positive
and negative counts and flags tasks with no positive examples. Keep these
empty-phase tasks for structural consistency; skip them when learning rules.

## Position trend encoding

Only `joint1_position` through `joint7_position` and `finger1_position`,
`finger2_position` are used as features. Velocity, effort, gripper width,
phase labels and run IDs are not body predicates.

For consecutive data rows N and N+1 in the same phase, state `sN` has exactly
nine facts: one per position signal. Pairs crossing a phase boundary are omitted,
as in the reference package. Row numbers are zero-based, excluding the CSV header.

For delta = position[N+1] - position[N]:

- delta > tolerance: `increases`
- delta < -tolerance: `decreases`
- otherwise: `constant` (approximately constant within the tolerance)

Default tolerance is 0.000001 for joints and 0.000001 for fingers, in the
respective source position units (expected radians for joints, metres for fingers).
This is an explicit numerical-noise tolerance, not a calibrated physical threshold.
Set both deadbands to zero for exact comparisons. The velocity/effort reference's
0.01 threshold is not reused for these position signals.

Example facts: `j1_pos_increases(s10).`, `j7_pos_constant(s10).`,
`finger1_pos_decreases(s10).`, `finger2_pos_decreases(s10).`
There are 27 allowed body predicates (9 signals times 3 trends).
Bias retains `max_vars(1)`, `max_body(4)`, `max_clauses(3)` and the reference's
unary state types and input directions. Empty predicates are declared dynamic
so they fail safely instead of being undefined.

For each phase, positive examples are its states and negative examples are all
other states from that same run. There is no mixing between runs and no held-out
test split. Position signs alone can produce identical feature patterns with
different phase labels; generating valid inputs does not guarantee a perfect rule.

## Labels and limitations

The targets use the existing CSV phase labels without modifying them. Those labels
were inferred from gripper-width threshold crossings (close below 0.05, open above
0.06), with 10-sample pick/place windows. They are not independently annotated
ground truth. Finger positions contribute to the gripper width used to generate
the labels, so learning these targets is not independent validation of task phases.
Most recordings end during place and have no retract examples; no retract data
is invented. A phase with one sample would also have no within-phase transition.

Regenerate from the repository root (Python standard library only):

```bash
python Popper_Test/Pick_Place_Joint_Finger_Position_Popper/build_inputs.py
```

Optional arguments: a source CSV directory, `--output`, `--joint-deadband`,
and `--finger-deadband`. The builder only writes input files and a count report.
