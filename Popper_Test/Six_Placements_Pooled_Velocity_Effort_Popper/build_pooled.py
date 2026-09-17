#!/usr/bin/env python3
"""Combine six recordings into one velocity-and-effort task per phase."""
import argparse
import csv
import math
from collections import Counter
from pathlib import Path

PHASES = ("home", "gripper_opening", "pick", "gripper_closing",
          "lift", "place", "retract", "return_home")
SIGNALS = (("velocity", "vel", 0.01), ("effort", "eff", 0.01))
PREDICATES = tuple(f"j{joint}_{short}_{direction}"
                   for joint in range(1, 7)
                   for _, short, _ in SIGNALS
                   for direction in ("increases", "decreases", "constant"))


def make_bias(phase):
    head = f"phase_{phase}"
    lines = ["% Same bias for every phase; no position predicates.",
             "max_vars(1).", "max_body(4).", "max_clauses(3).", "",
             f"head_pred({head},1)."]
    lines.extend(f"body_pred({p},1)." for p in PREDICATES)
    lines.extend(("", f"type({head},(state,))."))
    lines.extend(f"type({p},(state,))." for p in PREDICATES)
    lines.extend(("", f"direction({head},(in,))."))
    lines.extend(f"direction({p},(in,))." for p in PREDICATES)
    return "\n".join(lines) + "\n"


def read_recording(source, dataset_number):
    with source.open(newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"phase", *(f"joint{j}_{signal}" for j in range(1, 7)
                               for signal, _, _ in SIGNALS)}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{source}: missing columns {sorted(missing)}")
        rows = list(reader)
    if len(rows) < 2:
        raise ValueError(f"{source}: need at least two rows")
    unexpected = {r["phase"] for r in rows} - set(PHASES)
    if unexpected:
        raise ValueError(f"{source}: unexpected phases {sorted(unexpected)}")
    states = []
    for row_number, (before, after) in enumerate(zip(rows, rows[1:])):
        if before["phase"] != after["phase"]:
            continue
        state = f"d{dataset_number}_s{row_number}"
        facts = []
        for joint in range(1, 7):
            for signal, short, deadband in SIGNALS:
                column = f"joint{joint}_{signal}"
                first, second = float(before[column]), float(after[column])
                if not math.isfinite(first) or not math.isfinite(second):
                    raise ValueError(f"{source}: nonfinite {column} at row {row_number}")
                delta = second - first
                relation = ("increases" if delta > deadband else
                            "decreases" if delta < -deadband else "constant")
                facts.append(f"j{joint}_{short}_{relation}({state}).")
        states.append((state, before["phase"], facts))
    return len(rows), states


def build(directory, output):
    sources = sorted(directory.glob("full_motion_joint_states*.csv"))
    if len(sources) != 6:
        raise ValueError(f"Expected exactly six CSVs; found {len(sources)} in {directory}")
    output.mkdir(parents=True, exist_ok=True)
    states = []
    report = ["dataset,source,rows,within_phase_transitions," + ",".join(PHASES)]
    for dataset_number, source in enumerate(sources, 1):
        row_count, recording = read_recording(source, dataset_number)
        states.extend(recording)
        counts = Counter(phase for _, phase, _ in recording)
        report.append(f"dataset_{dataset_number},{source.name},{row_count},{len(recording)}," +
                      ",".join(str(counts[p]) for p in PHASES))
    (output / "input_counts.csv").write_text("\n".join(report) + "\n")
    facts = ["% All six recordings pooled; dN_sM means dataset N, CSV row M -> M+1.",
             "% Only within-phase transitions are included."]
    facts.extend(f":- discontiguous {p}/1." for p in PREDICATES)
    for _, _, lines in states:
        facts.extend(lines)
    background = "\n".join(facts) + "\n"
    for phase in PHASES:
        task = output / phase
        task.mkdir(exist_ok=True)
        (task / "bias.pl").write_text(make_bias(phase))
        (task / "bk.pl").write_text(background)
        examples = [f"% All six datasets: positive={phase}, negative=other phases."]
        examples.extend(f"{'pos' if label == phase else 'neg'}(phase_{phase}({state}))."
                        for state, label, _ in states)
        (task / "exs.pl").write_text("\n".join(examples) + "\n")
    print(f"Created {len(PHASES)} pooled tasks using {len(states)} transitions")
    print("\n".join(report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_directory", type=Path)
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).resolve().parent / "tasks")
    args = parser.parse_args()
    build(args.csv_directory, args.output)
