from pathlib import Path
import pandas as pd

CSV = Path("full_motion_joint_states_modified.csv")

thresholds = {
    "position": 0.002,
    "velocity": 0.01,
    "effort": 0.05,
}

# Representative Popper hypotheses learned from training data
RULES = {
    "pick": ["j3_pos_decreases", "j2_pos_increases"],
    "lift": ["j1_pos_decreases"],
    "place": ["j2_pos_increases", "j3_pos_increases"],
    "retract": ["j3_pos_constant", "j2_pos_decreases"],
    "return_home": ["j5_pos_increases", "j1_pos_increases"],
}

EXPECTED_ORDER = ["pick", "lift", "place", "retract", "return_home"]


def qualitative_facts(df):
    transitions = []

    for i in range(len(df) - 1):
        facts = set()

        for j in range(1, 7):
            for kind in ("position", "velocity", "effort"):
                col = f"joint{j}_{kind}"
                delta = float(df.loc[i + 1, col] - df.loc[i, col])
                eps = thresholds[kind]

                if delta > eps:
                    state = "increases"
                elif delta < -eps:
                    state = "decreases"
                else:
                    state = "constant"

                short = {
                    "position": "pos",
                    "velocity": "vel",
                    "effort": "eff",
                }[kind]

                facts.add(f"j{j}_{short}_{state}")

        transitions.append(facts)

    return transitions


def contiguous_ranges(indices):
    if not indices:
        return []

    ranges = []
    start = previous = indices[0]

    for value in indices[1:]:
        if value == previous + 1:
            previous = value
        else:
            ranges.append((start, previous))
            start = previous = value

    ranges.append((start, previous))
    return ranges


df = pd.read_csv(CSV)
facts = qualitative_facts(df)

detections = {}

for phase, rule in RULES.items():
    hits = [
        i for i, transition in enumerate(facts)
        if all(predicate in transition for predicate in rule)
    ]

    ranges = contiguous_ranges(hits)
    detections[phase] = ranges

    print(f"\n{phase.upper()}")
    print(f"Rule: {' AND '.join(rule)}")
    print(f"Matching transitions: {len(hits)}")
    print(f"Detected blocks: {ranges}")


# Pick the first detected block for each required phase and check ordering
first_blocks = {}

for phase in EXPECTED_ORDER:
    if detections[phase]:
        first_blocks[phase] = detections[phase][0]

all_present = len(first_blocks) == len(EXPECTED_ORDER)

correct_order = False
if all_present:
    starts = [first_blocks[p][0] for p in EXPECTED_ORDER]
    correct_order = starts == sorted(starts)

print("\n========================================")
print("PICK-AND-PLACE MOTION CHECK")
print("========================================")

if all_present and correct_order:
    print("RESULT: PICK-AND-PLACE MOTION DETECTED")
    print("All learned motion phases were found in the expected order.")
else:
    print("RESULT: PICK-AND-PLACE MOTION NOT CONFIRMED")

    missing = [p for p in EXPECTED_ORDER if p not in first_blocks]
    if missing:
        print("Missing phases:", ", ".join(missing))

    if all_present and not correct_order:
        print("All phases were detected, but not in the expected order.")
