# Earlier motion checker

`check_pick_and_place.py` reads the bundled
`full_motion_joint_states_modified.csv`, compares consecutive joint samples,
and checks fixed representative phase rules. The sample path is resolved
relative to the script.

From the repository root:

```bash
python Checking_motion/check_pick_and_place.py
```

The delta deadbands are 0.002 for position, 0.01 for velocity, and 0.05 for
reported effort. Matching transitions are grouped into blocks. The checker
compares the first detected block for each phase in this order:
`pick`, `lift`, `place`, `retract`, `return_home`.

| Phase | Required facts |
|---|---|
| pick | `j3_pos_decreases`, `j2_pos_increases` |
| lift | `j1_pos_decreases` |
| place | `j2_pos_increases`, `j3_pos_increases` |
| retract | `j3_pos_constant`, `j2_pos_decreases` |
| return_home | `j5_pos_increases`, `j1_pos_increases` |

These are fixed rules embedded in the script. Matching their sequence does not
verify a grasp. The separate checker in `../Check_motion/` accepts a CSV argument
and uses its own matching procedure.
