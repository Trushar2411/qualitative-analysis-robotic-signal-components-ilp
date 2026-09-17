#!/usr/bin/env python3
"""Check a joint-state CSV against rules learned from six pooled xArm recordings.

Predictions use velocity and effort only. An existing 'phase' column is ignored.
"""

import argparse
import csv
import math
from collections import Counter
from pathlib import Path

DEADBAND = {"vel": 0.01, "eff": 0.01}
# Each inner tuple is an AND clause. Clauses for a phase are joined by OR.
# Lift/pick/retract/return_home: run 1 of pooled hypothesis summary;
# place: run 3 (the most frequent first clause and the shared core clause).
RULES = {
    "pick": (
        ("j1_eff_constant", "j2_eff_decreases"),
        ("j1_vel_constant", "j3_vel_increases"),
    ),
    "lift": (
        ("j1_vel_constant", "j4_eff_decreases"),
        ("j2_vel_increases", "j3_vel_increases"),
    ),
    "place": (
        ("j3_vel_constant", "j4_eff_increases"),
        ("j1_eff_decreases", "j2_eff_decreases", "j3_vel_constant", "j4_eff_constant"),
        ("j1_eff_increases", "j2_eff_decreases", "j4_eff_constant", "j5_vel_constant"),
    ),
    "retract": (
        ("j1_vel_increases", "j3_vel_decreases"),
        ("j1_eff_constant", "j2_eff_increases", "j3_eff_decreases", "j5_vel_constant"),
    ),
    "return_home": (
        ("j1_vel_decreases", "j2_vel_increases"),
        ("j1_eff_decreases", "j2_vel_constant", "j2_eff_increases", "j4_eff_constant"),
        ("j1_eff_increases", "j2_vel_constant", "j2_eff_increases", "j4_eff_constant"),
    ),
}


def read_rows(path):
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream)
        required = {f"joint{joint}_{signal}" for joint in range(1, 7)
                    for signal in ("velocity", "effort")}
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise ValueError("Missing columns: " + ", ".join(sorted(missing)))
        rows = list(reader)
    if len(rows) < 2:
        raise ValueError("The CSV needs at least two rows")
    return rows


def transitions(rows):
    for index, (first, second) in enumerate(zip(rows, rows[1:])):
        facts = set()
        for joint in range(1, 7):
            for signal, abbreviation in (("velocity", "vel"), ("effort", "eff")):
                column = f"joint{joint}_{signal}"
                try:
                    a, b = float(first[column]), float(second[column])
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"Bad value in {column}, CSV rows {index + 2}–{index + 3}") from exc
                if not (math.isfinite(a) and math.isfinite(b)):
                    raise ValueError(f"Nonfinite {column}, CSV rows {index + 2}–{index + 3}")
                delta = b - a
                relation = ("increases" if delta > DEADBAND[abbreviation] else
                            "decreases" if delta < -DEADBAND[abbreviation] else "constant")
                facts.add(f"j{joint}_{abbreviation}_{relation}")
        hits = {phase for phase, clauses in RULES.items()
                if any(set(clause) <= facts for clause in clauses)}
        yield index, hits


def matching_stretches(events, phase, minimum=3):
    """Find stretches of consecutive transitions satisfying a phase rule."""
    stretches = []
    start = None
    last = None
    for index, hits in events:
        if phase in hits:
            if start is None:
                start = index
            last = index
        elif start is not None:
            if last - start + 1 >= minimum:
                stretches.append((start, last))
            start = last = None
    if start is not None and last - start + 1 >= minimum:
        stretches.append((start, last))
    return stretches


def ordered_witness(events, phases=("pick", "lift", "place"), minimum=3):
    """Find distinct phase stretches ordered in time; allow gaps between them."""
    evidence = []
    previous_end = -1
    for phase in phases:
        options = matching_stretches(events, phase, minimum)
        selected = next((span for span in options if span[0] > previous_end), None)
        if selected is None:
            return None
        evidence.append(selected)
        previous_end = selected[1]
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_file", type=Path, help="New full_motion_joint_states.csv")
    parser.add_argument("--output-csv", type=Path,
                        help="Optional per-transition rule matches for inspection")
    parser.add_argument("--min-consecutive", type=int, default=3,
                        help="Consecutive rule matches required for each phase (default: 3)")
    args = parser.parse_args()
    if args.min_consecutive < 1:
        parser.error("--min-consecutive must be positive")
    rows = read_rows(args.csv_file)
    events = list(transitions(rows))
    counts = Counter(phase for _, hits in events for phase in hits)
    witness = ordered_witness(events, minimum=args.min_consecutive)
    print(f"CSV: {args.csv_file} ({len(rows)} rows, {len(events)} transitions)")
    print("Rule matches (a transition may match multiple phases):")
    for phase in RULES:
        print(f"  {phase:12} {counts[phase]:4d}")
    if witness:
        print("RESULT: YES — pick → lift → place motion pattern detected")
        print("Matching CSV row ranges: " + ", ".join(
            f"{phase} {first + 2}–{last + 3}"
            for phase, (first, last) in zip(("pick", "lift", "place"), witness)))
    else:
        print("RESULT: NO — these rules did not confirm pick → lift → place")
    print(f"A phase needs at least {args.min_consecutive} consecutive matching transitions.")
    print("Rule matches are evidence of motion patterns, not proof that an object was grasped or placed.")
    if args.output_csv:
        with args.output_csv.open("w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(("transition_index", "csv_row_from", "csv_row_to", *RULES))
            for index, hits in events:
                writer.writerow((index, index + 2, index + 3,
                                 *(int(phase in hits) for phase in RULES)))
        print(f"Transition results: {args.output_csv}")


if __name__ == "__main__":
    main()
