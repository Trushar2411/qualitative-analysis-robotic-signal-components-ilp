# RAW adjacent-step Noisy Popper: repeated-run merged results

Identical input examples and bias on each run. Repeats are **not** independent evaluations.

Hypothesis frequencies count equivalent exact rule sets, ignoring body-literal and clause ordering.

## home
Final solutions: 10/10. Unique hypotheses: 1.

### Rule set 1: 10/10 runs
Training precision: 0.980; training recall: 0.830
```prolog
home(V0):-joint1_position_constant(V0),joint1_velocity_constant(V0),joint5_position_increases(V0).
```

- Run 01: ok, return code 0, solution yes
- Run 02: ok, return code 0, solution yes
- Run 03: ok, return code 0, solution yes
- Run 04: ok, return code 0, solution yes
- Run 05: ok, return code 0, solution yes
- Run 06: ok, return code 0, solution yes
- Run 07: ok, return code 0, solution yes
- Run 08: ok, return code 0, solution yes
- Run 09: ok, return code 0, solution yes
- Run 10: ok, return code 0, solution yes

## gripper_opening
Final solutions: 10/10. Unique hypotheses: 2.

### Rule set 1: 5/10 runs
Training precision: 1.000; training recall: 0.640
```prolog
gripper_opening(V0):-left_finger_joint_position_decreases(V0).
```

### Rule set 2: 5/10 runs
Training precision: 1.000; training recall: 0.640
```prolog
gripper_opening(V0):-right_finger_joint_position_decreases(V0).
```

- Run 01: ok, return code 0, solution yes
- Run 02: ok, return code 0, solution yes
- Run 03: ok, return code 0, solution yes
- Run 04: ok, return code 0, solution yes
- Run 05: ok, return code 0, solution yes
- Run 06: ok, return code 0, solution yes
- Run 07: ok, return code 0, solution yes
- Run 08: ok, return code 0, solution yes
- Run 09: ok, return code 0, solution yes
- Run 10: ok, return code 0, solution yes

## pick
Final solutions: 10/10. Unique hypotheses: 1.

### Rule set 1: 10/10 runs
Training precision: 1.000; training recall: 0.660
```prolog
pick(V0):-joint1_position_constant(V0),joint1_velocity_constant(V0),joint2_position_increases(V0).
pick(V0):-joint1_position_constant(V0),joint1_velocity_constant(V0),joint5_position_decreases(V0).
```

- Run 01: ok, return code 0, solution yes
- Run 02: ok, return code 0, solution yes
- Run 03: ok, return code 0, solution yes
- Run 04: ok, return code 0, solution yes
- Run 05: ok, return code 0, solution yes
- Run 06: ok, return code 0, solution yes
- Run 07: ok, return code 0, solution yes
- Run 08: ok, return code 0, solution yes
- Run 09: ok, return code 0, solution yes
- Run 10: ok, return code 0, solution yes

## gripper_closing
Final solutions: 10/10. Unique hypotheses: 2.

### Rule set 1: 6/10 runs
Training precision: 1.000; training recall: 0.640
```prolog
gripper_closing(V0):-right_finger_joint_position_increases(V0).
```

### Rule set 2: 4/10 runs
Training precision: 1.000; training recall: 0.640
```prolog
gripper_closing(V0):-left_finger_joint_position_increases(V0).
```

- Run 01: ok, return code 0, solution yes
- Run 02: ok, return code 0, solution yes
- Run 03: ok, return code 0, solution yes
- Run 04: ok, return code 0, solution yes
- Run 05: ok, return code 0, solution yes
- Run 06: ok, return code 0, solution yes
- Run 07: ok, return code 0, solution yes
- Run 08: ok, return code 0, solution yes
- Run 09: ok, return code 0, solution yes
- Run 10: ok, return code 0, solution yes

## lift
Final solutions: 10/10. Unique hypotheses: 2.

### Rule set 1: 6/10 runs
Training precision: 0.960; training recall: 0.980
```prolog
lift(V0):-joint1_effort_decreases(V0),joint1_velocity_decreases(V0).
lift(V0):-joint1_effort_decreases(V0),joint5_effort_constant(V0).
lift(V0):-joint1_effort_increases(V0),joint1_position_decreases(V0).
lift(V0):-joint1_effort_increases(V0),joint5_effort_constant(V0).
lift(V0):-joint1_velocity_decreases(V0),joint2_effort_increases(V0),joint5_effort_constant(V0).
lift(V0):-joint2_position_decreases(V0),joint3_position_decreases(V0).
```

### Rule set 2: 4/10 runs
Training precision: 0.960; training recall: 0.980
```prolog
lift(V0):-joint1_effort_decreases(V0),joint1_velocity_decreases(V0).
lift(V0):-joint1_effort_decreases(V0),joint5_effort_constant(V0).
lift(V0):-joint1_effort_increases(V0),joint2_effort_increases(V0),joint5_position_increases(V0).
lift(V0):-joint1_effort_increases(V0),joint5_effort_constant(V0).
lift(V0):-joint1_velocity_decreases(V0),joint2_effort_increases(V0),joint5_effort_constant(V0).
lift(V0):-joint2_position_decreases(V0),joint3_position_decreases(V0).
```

- Run 01: ok, return code 0, solution yes
- Run 02: ok, return code 0, solution yes
- Run 03: ok, return code 0, solution yes
- Run 04: ok, return code 0, solution yes
- Run 05: ok, return code 0, solution yes
- Run 06: ok, return code 0, solution yes
- Run 07: ok, return code 0, solution yes
- Run 08: ok, return code 0, solution yes
- Run 09: ok, return code 0, solution yes
- Run 10: ok, return code 0, solution yes

## place
Final solutions: 10/10. Unique hypotheses: 1.

### Rule set 1: 10/10 runs
Training precision: 0.990; training recall: 0.870
```prolog
place(V0):-joint1_position_increases(V0),joint2_position_increases(V0).
place(V0):-joint1_velocity_decreases(V0),joint5_position_decreases(V0).
place(V0):-joint1_velocity_increases(V0),joint2_position_increases(V0).
place(V0):-joint2_velocity_increases(V0),joint5_velocity_increases(V0).
```

- Run 01: ok, return code 0, solution yes
- Run 02: ok, return code 0, solution yes
- Run 03: ok, return code 0, solution yes
- Run 04: ok, return code 0, solution yes
- Run 05: ok, return code 0, solution yes
- Run 06: ok, return code 0, solution yes
- Run 07: ok, return code 0, solution yes
- Run 08: ok, return code 0, solution yes
- Run 09: ok, return code 0, solution yes
- Run 10: ok, return code 0, solution yes

## retract
Final solutions: 10/10. Unique hypotheses: 1.

### Rule set 1: 10/10 runs
Training precision: 0.910; training recall: 0.890
```prolog
retract_phase(V0):-joint1_velocity_increases(V0),joint3_position_constant(V0),joint5_position_increases(V0).
retract_phase(V0):-joint2_effort_increases(V0),joint3_position_constant(V0),joint3_velocity_constant(V0).
retract_phase(V0):-joint2_position_decreases(V0),joint2_velocity_decreases(V0),joint3_position_constant(V0).
retract_phase(V0):-joint2_velocity_decreases(V0),joint5_velocity_decreases(V0).
retract_phase(V0):-joint3_position_constant(V0),joint3_velocity_constant(V0),joint5_position_increases(V0).
```

- Run 01: ok, return code 0, solution yes
- Run 02: ok, return code 0, solution yes
- Run 03: ok, return code 0, solution yes
- Run 04: ok, return code 0, solution yes
- Run 05: ok, return code 0, solution yes
- Run 06: ok, return code 0, solution yes
- Run 07: ok, return code 0, solution yes
- Run 08: ok, return code 0, solution yes
- Run 09: ok, return code 0, solution yes
- Run 10: ok, return code 0, solution yes

## return_home
Final solutions: 10/10. Unique hypotheses: 1.

### Rule set 1: 10/10 runs
Training precision: 0.980; training recall: 0.830
```prolog
return_home(V0):-joint1_position_increases(V0),joint2_position_decreases(V0).
return_home(V0):-joint1_velocity_increases(V0),joint2_position_decreases(V0),joint3_position_increases(V0).
return_home(V0):-joint3_effort_decreases(V0),joint3_position_increases(V0),joint3_velocity_decreases(V0).
return_home(V0):-joint3_effort_increases(V0),joint3_velocity_decreases(V0),joint5_position_increases(V0).
```

- Run 01: ok, return code 0, solution yes
- Run 02: ok, return code 0, solution yes
- Run 03: ok, return code 0, solution yes
- Run 04: ok, return code 0, solution yes
- Run 05: ok, return code 0, solution yes
- Run 06: ok, return code 0, solution yes
- Run 07: ok, return code 0, solution yes
- Run 08: ok, return code 0, solution yes
- Run 09: ok, return code 0, solution yes
- Run 10: ok, return code 0, solution yes

