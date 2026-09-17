#!/usr/bin/env python3
"""Create independent velocity-and-effort Popper tasks for six xArm recordings."""
import argparse
import csv
import math
from pathlib import Path

VELOCITY_DEADBAND = 0.01
EFFORT_DEADBAND = 0.01
JOINTS = range(1, 7)
PHASES = ("home", "gripper_opening", "pick", "gripper_closing",
          "lift", "place", "retract", "return_home")


def bias(phase):
    head = f"phase_{phase}"
    predicates = [f"j{j}_{signal}_{direction}" for j in JOINTS
                  for signal in ("vel", "eff")
                  for direction in ("increases", "decreases", "constant")]
    lines = ["% Identical velocity-and-effort bias for every dataset and phase.",
             "max_vars(1).", "max_body(4).", "max_clauses(3).", "",
             f"head_pred({head},1)."]
    lines += [f"body_pred({p},1)." for p in predicates]
    lines += ["", f"type({head},(state,))."]
    lines += [f"type({p},(state,))." for p in predicates]
    lines += ["", f"direction({head},(in,))."]
    lines += [f"direction({p},(in,))." for p in predicates]
    return "\n".join(lines) + "\n"


def build(source, destination):
    with source.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    required = {"phase", *(f"joint{j}_{signal}" for j in JOINTS
                for signal in ("velocity", "effort"))}
    if not rows or not required.issubset(rows[0]):
        raise ValueError(f"Missing data or columns in {source}: {required - set(rows[0] if rows else [])}")
    unexpected = {r["phase"] for r in rows} - set(PHASES)
    if unexpected:
        raise ValueError(f"Unknown phase(s) in {source}: {sorted(unexpected)}")

    bk = ["% Compare consecutive velocity and effort samples within the same phase.",
          "% A state sN refers to CSV row N -> row N+1 (zero-based)."]
    bk += [f":- discontiguous j{j}_{signal}_{d}/1." for j in JOINTS
           for signal in ("vel", "eff")
           for d in ("increases", "decreases", "constant")]
    states = []
    for i, (first, second) in enumerate(zip(rows, rows[1:])):
        if first["phase"] != second["phase"]:
            continue
        facts = []
        for j in JOINTS:
            for signal, short, deadband in (("velocity", "vel", VELOCITY_DEADBAND),
                                            ("effort", "eff", EFFORT_DEADBAND)):
                key = f"joint{j}_{signal}"
                left, right = float(first[key]), float(second[key])
                if not (math.isfinite(left) and math.isfinite(right)):
                    raise ValueError(f"Nonfinite {key} in {source} at rows {i}, {i + 1}")
                delta = right - left
                direction = "increases" if delta > deadband else (
                    "decreases" if delta < -deadband else "constant")
                facts.append(f"j{j}_{short}_{direction}(s{i}).")
        bk.extend(facts)
        states.append((i, first["phase"]))
    if not states:
        raise ValueError(f"No within-phase transitions in {source}")
    destination.mkdir(parents=True, exist_ok=True)
    for phase in PHASES:
        folder = destination / phase
        folder.mkdir(exist_ok=True)
        (folder / "bias.pl").write_text(bias(phase))
        (folder / "bk.pl").write_text("\n".join(bk) + "\n")
        examples = [f"% Positive examples: {phase}; negative: other phases."]
        examples += [f"{'pos' if label == phase else 'neg'}(phase_{phase}(s{i}))."
                     for i, label in states]
        (folder / "exs.pl").write_text("\n".join(examples) + "\n")
    return len(rows), len(states), {p: sum(label == p for _, label in states) for p in PHASES}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_directory", type=Path)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent / "datasets")
    args = parser.parse_args()
    sources = sorted(args.csv_directory.glob("full_motion_joint_states*.csv"))
    if len(sources) != 6:
        parser.error(f"Expected exactly six CSVs; found {len(sources)} in {args.csv_directory}")
    report = ["dataset,source,rows,within_phase_transitions," + ",".join(PHASES)]
    for number, source in enumerate(sources, 1):
        name = f"dataset_{number}"
        rows, transitions, counts = build(source, args.output / name)
        report.append(f"{name},{source.name},{rows},{transitions}," +
                      ",".join(str(counts[p]) for p in PHASES))
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "input_counts.csv").write_text("\n".join(report) + "\n")
    print("\n".join(report))
