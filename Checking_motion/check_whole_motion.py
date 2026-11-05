#!/usr/bin/env python3
"""Check the full arm/gripper motion without phase labels.

Put this script beside full_motion_joint_states(20261105-101612).csv and run:
    python3 check_whole_motion.py
Or provide another recording:
    python3 check_whole_motion.py other_recording.csv

Dependency: python3 -m pip install pandas

Uses ALL arm-rule alternatives from your ten-run table, combined with OR
within each action. Predicates inside each alternative are combined with AND
on the SAME sample transition. The gripper hypotheses stay unchanged
(right finger increases = closing, decreases = opening). It reports
all seven actions and checks their non-overlapping order. Initial home and
initial gripper preparation are optional; the gripper opening REQUIRED by the
sequence is the one AFTER place. It does not invent a new home rule.

Facts use consecutive sample differences, with arm threshold 0.002 and finger
threshold 0.001 in recorded position units. This is the simple encoding you
requested, not the PLA/window encoding used in your October 28 training run.
Arm rules also differ from that run. Do not interpret this as independent
validation of the October 28 model. Sampling rate and joint conventions matter.
Training frequencies are recorded as metadata; every alternative is accepted.
Frequencies are not confidence scores. Precision/recall of this OR combination
must be evaluated separately; they do not follow from individual-run scores.

Only positions and real timestamps are read; phase labels are ignored. The
right finger supplies the learned gripper rule. Left-finger trends are also
reported as an agreement diagnostic, not an additional learned condition.
If your gripper convention is reversed, use --closing-direction decreases.
Numerical position changes alone cannot determine which direction is closing.

Outputs a terminal summary, whole_motion_report.json and motion_matches.csv
inside <CSV-stem>_whole_motion_check. Reported data-row indices start at zero.
PATTERN_DETECTED refers to motion-pattern evidence, not verified object grasp
or placement success. NOT_CONFIRMED is not proof that the task did not occur.
"""

from pathlib import Path
import argparse
import json
import math

try:
    import pandas as pd
except ImportError:
    raise SystemExit("Install pandas: python3 -m pip install pandas")


CSV = Path(__file__).resolve().parent / "full_motion_joint_states(20261105-101612).csv"
ARM_THRESHOLD = 0.002
FINGER_THRESHOLD = 0.001

# Outer list = OR alternatives; each inner list = AND on one transition.
# All alternatives from the supplied ten-run table, including the 1/10 rule.
ARM_RULES = {
    "pick": [
        ["j3_pos_decreases", "j5_pos_decreases"],
        ["j2_pos_increases", "j3_pos_decreases"],
    ],
    "lift": [["j1_pos_decreases"]],
    "place": [
        ["j2_pos_increases", "j3_pos_increases"],
        ["j1_pos_increases", "j5_pos_decreases"],
        ["j3_pos_increases", "j5_pos_decreases"],
        ["j1_pos_increases", "j2_pos_increases"],
    ],
    "retract": [
        ["j3_pos_constant", "j5_pos_increases"],
        ["j2_pos_decreases", "j3_pos_constant"],
    ],
    "return_home": [
        ["j1_pos_increases", "j5_pos_increases"],
        ["j1_pos_increases", "j2_pos_decreases"],
        ["j3_pos_increases", "j5_pos_increases"],
        ["j3_pos_increases", "j2_pos_decreases"],
    ],
}
TRAINING_FREQUENCIES = {
    "lift": [10], "pick": [7, 3], "place": [3, 3, 3, 1],
    "retract": [5, 5], "return_home": [3, 3, 2, 2],
}
EXPECTED_ORDER = ["pick", "gripper_closing", "lift", "place",
                  "gripper_opening", "retract", "return_home"]


def make_rules(closing_direction):
    opening_direction = "decreases" if closing_direction == "increases" else "increases"
    rules = dict(ARM_RULES)
    rules["gripper_closing"] = [[f"right_finger_pos_{closing_direction}"]]
    rules["gripper_opening"] = [[f"right_finger_pos_{opening_direction}"]]
    return {action: rules[action] for action in EXPECTED_ORDER}


def load_positions(df):
    columns = {}
    for joint in (1, 2, 3, 5):
        canonical = f"joint{joint}_position"
        columns[f"j{joint}"] = next(
            (c for c in (canonical, f"joint_{joint}_position") if c in df), None)
    for side in ("left", "right"):
        columns[f"{side}_finger"] = next(
            (c for c in (f"{side}_finger_position", f"{side}_finger_joint_position")
             if c in df), None)
    missing = [name for name, col in columns.items() if col is None]
    if missing:
        raise ValueError("Missing required position signals: " + ", ".join(missing))
    values = {name: pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=float)
              for name, col in columns.items()}
    return columns, values


def get_times(df):
    # Never generate fictitious timestamps if none of these columns exists.
    col = next((c for c in ("header_stamp_sec", "bag_time_sec", "time_seconds", "time_sec")
                if c in df), None)
    if col is None:
        return None, None
    times = pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=float)
    if not all(math.isfinite(float(t)) for t in times):
        raise ValueError(f"Invalid timestamps in {col}.")
    if any(float(times[i + 1]) <= float(times[i]) for i in range(len(times) - 1)):
        raise ValueError(f"{col} must increase strictly. Split recordings at clock resets.")
    return col, times


def qualitative_facts(values, arm_threshold, finger_threshold):
    transitions = []
    size = len(next(iter(values.values())))
    for i in range(size - 1):
        facts = set()
        for name, signal in values.items():
            before, after = float(signal[i]), float(signal[i + 1])
            if not (math.isfinite(before) and math.isfinite(after)):
                continue
            change = after - before
            if not math.isfinite(change):
                continue
            eps = finger_threshold if "finger" in name else arm_threshold
            state = "increases" if change > eps else "decreases" if change < -eps else "constant"
            facts.add(f"{name}_pos_{state}")
        transitions.append(facts)
    return transitions


def contiguous_ranges(indices):
    if not indices:
        return []
    blocks = []
    start = previous = indices[0]
    for index in indices[1:]:
        if index != previous + 1:
            blocks.append((start, previous))
            start = index
        previous = index
    blocks.append((start, previous))
    return blocks


def ordered_prefix(detections, first_transition=0):
    selected = {}
    end = first_transition - 1
    for action in EXPECTED_ORDER:
        eligible = [b for b in detections[action] if b[0] > end]
        if not eligible:
            break
        block = min(eligible, key=lambda b: b[1])
        selected[action] = block
        end = block[1]
    return selected


def ordered_sequence(detections, first_transition=0):
    selected = ordered_prefix(detections, first_transition)
    return selected if len(selected) == len(EXPECTED_ORDER) else None


def block_details(action, block, times):
    start, end = block
    return {
        "action": action, "start_transition": start, "end_transition": end,
        "start_row": start, "end_row": end + 1, "matching_transitions": end - start + 1,
        "start_elapsed_sec": float(times[start] - times[0]) if times is not None else None,
        "end_elapsed_sec": float(times[end + 1] - times[0]) if times is not None else None,
    }


def annotated_block(action, block, times, rule_hits):
    details = block_details(action, block, times)
    start, end = block
    # A rule contributes if it fires anywhere inside this OR-combined block.
    details["contributing_rule_ids"] = ";".join(
        f"{action}_r{i + 1}" for i, hits in enumerate(rule_hits[action])
        if any(start <= hit <= end for hit in hits))
    return details


def match_rules(facts, rules, minimum, times):
    """Evaluate AND clauses separately, then form each phase's unique OR union."""
    detections, counts, matches, rule_hits, per_rule = {}, {}, [], {}, {}
    for action, alternatives in rules.items():
        clause_hits = [{i for i, fact in enumerate(facts) if all(p in fact for p in clause)}
                       for clause in alternatives]
        rule_hits[action] = clause_hits
        hits = sorted(set().union(*clause_hits))
        blocks = [b for b in contiguous_ranges(hits) if b[1] - b[0] + 1 >= minimum]
        detections[action], counts[action] = blocks, len(hits)
        matches.extend(annotated_block(action, b, times, rule_hits) for b in blocks)
        per_rule[action] = []
        for i, (clause, fired) in enumerate(zip(alternatives, clause_hits)):
            freq = TRAINING_FREQUENCIES.get(action)
            clause_blocks = [b for b in contiguous_ranges(sorted(fired))
                             if b[1] - b[0] + 1 >= minimum]
            per_rule[action].append({
                "rule_id": f"{action}_r{i + 1}", "predicates": clause,
                "training_frequency": f"{freq[i]}/10" if freq else None,
                "matching_transitions": len(fired),
                "blocks": [block_details(action, b, times) for b in clause_blocks],
            })
    return detections, counts, matches, rule_hits, per_rule


def check_motion(args):
    source = args.csv.expanduser().resolve()
    df = pd.read_csv(source)
    df.columns = [str(c).strip().lstrip("\ufeff") for c in df.columns]
    if len(set(df.columns)) != len(df.columns):
        raise ValueError("Duplicate CSV columns after whitespace removal.")
    if len(df) < 2:
        raise ValueError("At least two data rows are required.")
    columns, values = load_positions(df)
    time_column, times = get_times(df)
    facts = qualitative_facts(values, args.threshold, args.finger_threshold)
    rules = make_rules(args.closing_direction)
    detections, counts, matches, rule_hits, per_rule = match_rules(
        facts, rules, args.min_consecutive, times)
    print(f"CSV: {source}\nRows: {len(df)} | transitions: {len(facts)}")
    print(f"Thresholds: arm={args.threshold:g}, finger={args.finger_threshold:g}")
    print(f"Gripper convention: closing={args.closing_direction}; opening=opposite")
    print("Logic: OR between alternatives; AND within each alternative.")
    for action, alternatives in rules.items():
        blocks = detections[action]
        print(f"\n{action.upper()}")
        for entry in per_rule[action]:
            frequency = f" [{entry['training_frequency']} training runs]" if entry['training_frequency'] else ""
            print(f"  {entry['rule_id']}: {' AND '.join(entry['predicates'])}{frequency}")
            print(f"    Matching transitions: {entry['matching_transitions']}")
        print(f"OR-combined unique transitions: {counts[action]} | qualifying blocks: {len(blocks)}")
        print(f"Blocks: {blocks[:8]}" + (" ... (all blocks in report)" if len(blocks) > 8 else ""))

    sequences = []
    next_transition = 0
    while True:
        chosen = ordered_sequence(detections, next_transition)
        if chosen is None:
            break
        sequences.append([annotated_block(action, chosen[action], times, rule_hits)
                          for action in EXPECTED_ORDER])
        next_transition = chosen[EXPECTED_ORDER[-1]][1] + 1
    notes = [
        "All arm alternatives are from the supplied ten-run table; finger rules are unchanged.",
        "Consecutive-sample encoding differs from the October 28 PLA/window training setup.",
        "No phase labels, velocity or effort are used.",
        "Initial home/gripper preparation are optional; opening after place is required.",
        "Matches are motion evidence; successful object handling cannot be verified from positions alone.",
        "Strict rule misses can reflect a different trajectory or sampling rate, not task failure.",
        "Ordering alone sets no maximum gap between actions; inspect the reported row/time ranges.",
    ]
    diagnostics = {}
    for name, signal in values.items():
        finite = [float(v) for v in signal if math.isfinite(float(v))]
        span = max(finite) - min(finite) if finite else None
        diagnostics[name] = {"column": columns[name], "range": span,
                             "invalid_samples": len(signal) - len(finite)}
        if len(finite) != len(signal):
            notes.append(f"{name}: invalid values skip affected facts; they are not treated as constant.")
        if name.startswith("j") and span is not None and span <= args.threshold:
            notes.append(f"{name} spans only {span:.6g}, below the arm threshold; "
                         "increase/decrease rules for this joint cannot match.")
    finger_moving = sum(any(f"right_finger_pos_{s}" in f for s in ("increases", "decreases"))
                        for f in facts)
    agreement = sum(any(f"right_finger_pos_{s}" in f and f"left_finger_pos_{s}" in f
                        for s in ("increases", "decreases")) for f in facts)
    missing = [action for action in EXPECTED_ORDER if not detections[action]]
    prefix = ordered_prefix(detections)
    next_required = EXPECTED_ORDER[len(prefix)] if len(prefix) < len(EXPECTED_ORDER) else None
    report = {
        "source": str(source), "status": "PATTERN_DETECTED" if sequences else "NOT_CONFIRMED",
        "required_order": EXPECTED_ORDER, "rules": rules, "matches": counts,
        "rule_logic": "OR between alternatives; AND on the same transition within each alternative",
        "rule_matches": per_rule,
        "frequency_note": "Training frequencies are metadata, not weights or confidence scores.",
        "validation_note": "The combined rule set needs its own evaluation; single-run recall/precision are not inherited.",
        "missing_actions": missing, "complete_sequences": sequences,
        "ordered_prefix": [annotated_block(action, block, times, rule_hits)
                           for action, block in prefix.items()],
        "next_unmatched_stage_in_order": next_required,
        "detected_blocks": matches, "time_column": time_column,
        "threshold": args.threshold, "finger_threshold": args.finger_threshold,
        "min_consecutive": args.min_consecutive, "closing_direction": args.closing_direction,
        "signal_diagnostics": diagnostics,
        "right_finger_moving_transitions": finger_moving,
        "both_fingers_same_direction_transitions": agreement,
        "notes": notes,
    }
    out = (args.output_dir or source.parent / (source.stem + "_whole_motion_check")).resolve()
    if source in [out / "motion_matches.csv", out / "whole_motion_report.json"]:
        raise ValueError("Output directory would overwrite the input.")
    out.mkdir(parents=True, exist_ok=True)
    (out / "whole_motion_report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n",
                                                 encoding="utf-8")
    pd.DataFrame(matches, columns=list(block_details("", (0, 0), None)) + ["contributing_rule_ids"]).to_csv(
        out / "motion_matches.csv", index=False)
    print(f"\nWHOLE MOTION: {report['status']}")
    print("Required: " + " -> ".join(EXPECTED_ORDER))
    if missing:
        print("Actions without qualifying rule matches: " + ", ".join(missing))
    elif not sequences:
        print("All actions match somewhere, but not in the required non-overlapping order.")
    if not sequences and next_required:
        print("Matched in order: " + (" -> ".join(prefix) if prefix else "none"))
        print("Next required stage without an eligible block: " + next_required)
    for i, sequence in enumerate(sequences, 1):
        print(f"Complete sequence {i}:")
        for event in sequence:
            span = f"rows {event['start_row']}–{event['end_row']}"
            if times is not None:
                span += f"; elapsed {event['start_elapsed_sec']:.3f}–{event['end_elapsed_sec']:.3f} s"
            print(f"  {event['action']}: {span}")
    print(f"Finger direction agreement: {agreement}/{finger_moving} moving right-finger transitions")
    for note in notes[7:]:
        print("Note: " + note)
    print("Motion evidence only; object grasp/placement are unverified.")
    print(f"Results saved in: {out}")
    return report


def main():
    parser = argparse.ArgumentParser(description="Check all arm and gripper stages from positions")
    parser.add_argument("csv", nargs="?", type=Path, default=CSV)
    parser.add_argument("--threshold", type=float, default=ARM_THRESHOLD)
    parser.add_argument("--finger-threshold", type=float, default=FINGER_THRESHOLD)
    parser.add_argument("--min-consecutive", type=int, default=1)
    parser.add_argument("--closing-direction", choices=("increases", "decreases"), default="increases")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if any(not math.isfinite(v) or v < 0 for v in (args.threshold, args.finger_threshold)):
        parser.error("Thresholds must be finite and non-negative.")
    if args.min_consecutive < 1:
        parser.error("--min-consecutive must be at least 1.")
    try:
        check_motion(args)
    except (ValueError, OSError, pd.errors.ParserError) as exc:
        parser.exit(2, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
