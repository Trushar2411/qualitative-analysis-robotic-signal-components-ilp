#!/usr/bin/env python3
"""Check the full arm/gripper motion without phase labels.

Put this script beside full_motion_joint_states(20261105-101612).csv and run:
    python3 check_whole_motion.py
Or provide another recording:
    python3 check_whole_motion.py other_recording.csv

Dependencies: python3 -m pip install numpy pandas

Uses ALL arm-rule alternatives from your ten-run table, combined with OR
within each action. Predicates inside each alternative are combined with AND
on the SAME window. The gripper hypotheses stay unchanged
(right finger increases = closing, decreases = opening). It reports
all seven actions and checks their non-overlapping order. Initial home and
initial gripper preparation are optional; the gripper opening REQUIRED by the
sequence is the one AFTER place. It does not invent a new home rule.

Facts use the fitted end-to-end change of a least-squares line through each
20-sample window: slope * (last_time - first_time). Training defaults are
step=20, arm threshold=0.004, finger threshold=0.001, min-samples=8. Thresholds
are in recorded position units per window, not per-sample differences.
The abstraction matches prepare_popper.py; this OR rule set is the ten-run
table you supplied, not the separate single-run hypotheses of October 28.
Sampling rate, window alignment and joint conventions still matter.
Training frequencies are recorded as metadata; every alternative is accepted.
Frequencies are not confidence scores. Precision/recall of this OR combination
must be evaluated separately; they do not follow from individual-run scores.

By default only positions and real timestamps are read; labels are ignored. The
right finger supplies the learned gripper rule. Left-finger trends are also
reported as an agreement diagnostic, not an additional learned condition.
If your gripper convention is reversed, use --closing-direction decreases.
Numerical position changes alone cannot determine which direction is closing.

Optional reference evaluation with exact supplied training window boundaries:
    python3 check_whole_motion.py simulation.csv --window-index window_index.csv
The index must belong to that CSV (rows and timestamps are validated). Its
phase labels are used only AFTER rule matching to calculate reference metrics.
Those metrics use annotated boundaries and are not label-free validation.

Outputs windows.csv, whole_motion_report.json and motion_matches.csv
inside <CSV-stem>_whole_motion_check. Reported data-row indices start at zero.
PATTERN_DETECTED refers to motion-pattern evidence, not verified object grasp
or placement success. NOT_CONFIRMED is not proof that the task did not occur.
"""

from pathlib import Path
import argparse
import json
import math

try:
    import numpy as np
    import pandas as pd
except ImportError:
    raise SystemExit("Install dependencies: python3 -m pip install numpy pandas")


CSV = Path(__file__).resolve().parent / "full_motion_joint_states(20261105-101612).csv"
ARM_THRESHOLD = 0.004
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
    col = next((c for c in ("header_stamp_sec", "bag_time_sec", "time_seconds", "time_sec")
                if c in df), None)
    if col is None:
        return None, np.arange(len(df), dtype=float)
    times = pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(times).all():
        raise ValueError(f"Invalid timestamps in {col}.")
    if np.any(np.diff(times) <= 0):
        raise ValueError(f"{col} must increase strictly. Split recordings at clock resets.")
    return col, times


def window_definitions(size, times, time_column, args):
    if args.window_index is None:
        return [{"window_id": f"w{i:05d}", "start_row": start,
                 "end_row": min(start + args.window, size) - 1}
                for i, start in enumerate(range(0, size, args.step))
                if min(start + args.window, size) - start >= args.min_samples]
    index = pd.read_csv(args.window_index.expanduser())
    required = {"start_row", "end_row"}
    if not required.issubset(index.columns) or index.empty:
        raise ValueError("Window index must contain nonempty start_row and end_row columns.")
    definitions = []
    previous_end = -1
    for i, row in index.iterrows():
        bounds = pd.to_numeric(row[["start_row", "end_row"]], errors="coerce").to_numpy(float)
        if not np.isfinite(bounds).all() or not np.equal(bounds, np.floor(bounds)).all():
            raise ValueError(f"Window index row {i}: row bounds must be finite integers.")
        start, end = map(int, bounds)
        if not (0 <= start <= end < size):
            raise ValueError(f"Window index row {i}: bounds outside this recording.")
        if start <= previous_end:
            raise ValueError("Reference windows must be ordered and non-overlapping.")
        if end - start + 1 < args.min_samples:
            raise ValueError(f"Window {i} has fewer than {args.min_samples} samples.")
        if "samples" in row.index:
            recorded_samples = pd.to_numeric(pd.Series([row["samples"]]), errors="coerce").iloc[0]
            if not np.isfinite(recorded_samples) or recorded_samples != end - start + 1:
                raise ValueError(f"Window {i}: samples does not agree with row bounds.")
        if time_column:
            for field, pos in (("start_time_sec", start), ("end_time_sec", end)):
                if field in row.index:
                    try:
                        recorded = float(row[field])
                    except (ValueError, TypeError):
                        raise ValueError(f"Window {i}: invalid reference timestamp.")
                    if not math.isfinite(recorded) or abs(recorded - float(times[pos])) > 1e-5:
                        raise ValueError(f"Window {i}: {field} does not match this CSV. "
                                         "Use the index only with its original recording.")
        item = {"window_id": str(row.get("window_id", f"w{i:05d}")),
                "start_row": start, "end_row": end}
        if "phase" in row.index and pd.notna(row["phase"]):
            item["reference_phase"] = str(row["phase"])
        definitions.append(item)
        previous_end = end
    if len({d["window_id"] for d in definitions}) != len(definitions):
        raise ValueError("Reference window_id values must be unique.")
    return definitions


def qualitative_windows(values, times, definitions, args, has_time):
    facts, windows = [], []
    for wi, definition in enumerate(definitions):
        start, end = definition["start_row"], definition["end_row"]
        row = dict(definition, window_number=wi, samples=end - start + 1,
                   start_time_sec=float(times[start]) if has_time else None,
                   end_time_sec=float(times[end]) if has_time else None,
                   start_elapsed_sec=float(times[start] - times[0]) if has_time else None,
                   end_elapsed_sec=float(times[end] - times[0]) if has_time else None)
        window_facts = set()
        for name, signal in values.items():
            t, y = times[start:end + 1], signal[start:end + 1]
            good = np.isfinite(t) & np.isfinite(y)
            label, change = "unknown", None
            if int(good.sum()) >= args.min_samples:
                tg, yg = t[good], y[good]
                duration = tg[-1] - tg[0]
                if duration > 0:
                    slope = np.polyfit(tg - tg[0], yg, 1)[0]
                    fitted_change = float(slope * duration)
                    if math.isfinite(fitted_change):
                        change = fitted_change
                        eps = args.finger_threshold if "finger" in name else args.threshold
                        label = ("increases" if change > eps else
                                 "decreases" if change < -eps else "constant")
                        window_facts.add(f"{name}_pos_{label}")
            row[f"{name}_fitted_change"] = change
            row[f"{name}_trend"] = label
            row[f"{name}_valid_samples"] = int(good.sum())
        windows.append(row)
        facts.append(window_facts)
    return facts, windows


def contiguous_ranges(indices, windows):
    if not indices:
        return []
    blocks = []
    start = previous = indices[0]
    for index in indices[1:]:
        if (index != previous + 1 or
                windows[index]["start_row"] > windows[previous]["end_row"] + 1):
            blocks.append((start, previous))
            start = index
        previous = index
    blocks.append((start, previous))
    return blocks


def block_details(action, block, windows, rule_hits=None):
    start, end = block
    first, last = windows[start], windows[end]
    item = {
        "action": action, "start_window": start, "end_window": end,
        "start_window_id": first["window_id"], "end_window_id": last["window_id"],
        "matching_windows": end - start + 1,
        "start_row": first["start_row"], "end_row": last["end_row"],
        "start_time_sec": first["start_time_sec"], "end_time_sec": last["end_time_sec"],
        "start_elapsed_sec": first["start_elapsed_sec"], "end_elapsed_sec": last["end_elapsed_sec"],
    }
    if rule_hits is not None:
        item["contributing_rule_ids"] = ";".join(
            f"{action}_r{i + 1}" for i, hits in enumerate(rule_hits[action])
            if any(start <= hit <= end for hit in hits))
    return item


def match_rules(facts, rules, minimum, windows):
    detections, counts, blocks_output, rule_hits, per_rule = {}, {}, [], {}, {}
    for action, alternatives in rules.items():
        clause_hits = [{i for i, fact in enumerate(facts) if all(p in fact for p in clause)}
                       for clause in alternatives]
        rule_hits[action] = clause_hits
        union = set().union(*clause_hits)
        blocks = [b for b in contiguous_ranges(sorted(union), windows)
                  if b[1] - b[0] + 1 >= minimum]
        detections[action], counts[action] = blocks, len(union)
        blocks_output.extend(block_details(action, b, windows, rule_hits) for b in blocks)
        per_rule[action] = []
        for i, (clause, fired) in enumerate(zip(alternatives, clause_hits)):
            freq = TRAINING_FREQUENCIES.get(action)
            clause_blocks = [b for b in contiguous_ranges(sorted(fired), windows)
                             if b[1] - b[0] + 1 >= minimum]
            per_rule[action].append({
                "rule_id": f"{action}_r{i + 1}", "predicates": clause,
                "training_frequency": f"{freq[i]}/10" if freq else None,
                "matching_windows": len(fired),
                "blocks": [block_details(action, b, windows) for b in clause_blocks],
            })
        for wi, row in enumerate(windows):
            row[f"match_{action}"] = wi in union
            row[f"rules_{action}"] = ";".join(
                f"{action}_r{i + 1}" for i, fired in enumerate(clause_hits) if wi in fired)
    for row in windows:
        row["matching_actions"] = ";".join(a for a in rules if row[f"match_{a}"])
    return detections, counts, blocks_output, rule_hits, per_rule


def ordered_prefix(detections, windows, first_window=0):
    selected = {}
    end_window = first_window - 1
    end_row = windows[end_window]["end_row"] if end_window >= 0 else -1
    for action in EXPECTED_ORDER:
        eligible = [b for b in detections[action]
                    if b[0] > end_window and windows[b[0]]["start_row"] > end_row]
        if not eligible:
            break
        block = min(eligible, key=lambda b: b[1])
        selected[action] = block
        end_window, end_row = block[1], windows[block[1]]["end_row"]
    return selected


def reference_metrics(windows, rules):
    # Reference labels never affect matching or sequence selection.
    labelled = [w for w in windows if "reference_phase" in w]
    if not labelled:
        return None
    metrics = {}
    for action in rules:
        tp = sum(w["reference_phase"] == action and w[f"match_{action}"] for w in labelled)
        fn = sum(w["reference_phase"] == action and not w[f"match_{action}"] for w in labelled)
        fp = sum(w["reference_phase"] != action and w[f"match_{action}"] for w in labelled)
        tn = len(labelled) - tp - fn - fp
        metrics[action] = {"tp": tp, "fn": fn, "fp": fp, "tn": tn,
                           "precision": tp / (tp + fp) if tp + fp else None,
                           "recall": tp / (tp + fn) if tp + fn else None}
    return {"labelled_windows": len(labelled), "actions": metrics,
            "scope": "Annotated-boundary window evaluation; not independent label-free validation.",
            "prediction_unit": "OR rule match before the min-consecutive event filter"}


def check_motion(args):
    source = args.csv.expanduser().resolve()
    df = pd.read_csv(source)
    df.columns = [str(c).strip().lstrip("\ufeff") for c in df.columns]
    if len(set(df.columns)) != len(df.columns):
        raise ValueError("Duplicate CSV columns after whitespace removal.")
    if len(df) < args.min_samples:
        raise ValueError(f"At least {args.min_samples} rows are required.")
    columns, values = load_positions(df)
    time_column, times = get_times(df)
    definitions = window_definitions(len(df), times, time_column, args)
    if not definitions:
        raise ValueError("No usable windows.")
    facts, windows = qualitative_windows(values, times, definitions, args, bool(time_column))
    rules = make_rules(args.closing_direction)
    detections, counts, matches, rule_hits, per_rule = match_rules(
        facts, rules, args.min_consecutive, windows)
    print(f"CSV: {source}\nRows: {len(df)} | windows: {len(windows)}")
    mode = "supplied reference index" if args.window_index else "unlabelled fixed windows"
    print(f"Abstraction: fitted change | {mode} | window={args.window}, step={args.step}")
    print(f"Fitted-change thresholds: arm={args.threshold:g}, finger={args.finger_threshold:g}")
    print(f"Gripper convention: closing={args.closing_direction}; opening=opposite")
    print("Logic: OR between alternatives; AND within the same window.")
    for action in rules:
        print(f"\n{action.upper()}")
        for entry in per_rule[action]:
            freq = f" [{entry['training_frequency']} training runs]" if entry["training_frequency"] else ""
            print(f"  {entry['rule_id']}: {' AND '.join(entry['predicates'])}{freq}")
            print(f"    Matching windows: {entry['matching_windows']}")
        print(f"OR-combined unique windows: {counts[action]} | blocks: {len(detections[action])}")

    sequences, next_window = [], 0
    while next_window < len(windows):
        chosen = ordered_prefix(detections, windows, next_window)
        if len(chosen) != len(EXPECTED_ORDER):
            break
        sequences.append([block_details(a, chosen[a], windows, rule_hits) for a in EXPECTED_ORDER])
        next_window = chosen[EXPECTED_ORDER[-1]][1] + 1
    prefix = ordered_prefix(detections, windows)
    next_required = EXPECTED_ORDER[len(prefix)] if len(prefix) < len(EXPECTED_ORDER) else None
    notes = [
        "13 arm alternatives from the ten-run table; gripper direction predicates are unchanged.",
        "Fitted-change abstraction and default thresholds match the supplied prepare_popper.py.",
        "The combined OR rule set needs its own evaluation; training frequencies are not confidence scores.",
        "Global window boundaries can cross actions; they are not the original phase-bounded training windows.",
        "Initial home/preparation are optional; opening after place is required.",
        "Ordered motion evidence cannot verify successful object grasp or placement.",
        "There is no maximum allowed gap between stages; inspect the reported time/row ranges.",
    ]
    if args.window_index:
        notes.append("Reference window boundaries are supplied. Labels only evaluate completed predictions; "
                     "annotated boundaries make this different from unlabelled deployment.")
    if time_column is None:
        notes.append("No known time column: fitting against sample index; no timestamps are invented. "
                     "Supply real times for irregular sampling.")
    diagnostics = {}
    for name, signal in values.items():
        finite = signal[np.isfinite(signal)]
        span = float(finite.max() - finite.min()) if len(finite) else None
        diagnostics[name] = {"column": columns[name], "range": span,
                             "invalid_samples": len(signal) - len(finite)}
        if len(finite) != len(signal):
            notes.append(f"{name}: invalid samples require at least {args.min_samples} finite values "
                         "per fit; insufficient fits are unknown, never constant.")
    finger_moving = sum(any(f"right_finger_pos_{s}" in f for s in ("increases", "decreases")) for f in facts)
    agreement = sum(any(f"right_finger_pos_{s}" in f and f"left_finger_pos_{s}" in f
                        for s in ("increases", "decreases")) for f in facts)
    missing = [a for a in EXPECTED_ORDER if not detections[a]]
    report = {
        "source": str(source), "status": "PATTERN_DETECTED" if sequences else "NOT_CONFIRMED",
        "abstraction": "least_squares_fitted_change", "match_unit": "windows",
        "source_rows": len(df), "window_count": len(windows),
        "window_mode": "reference_index" if args.window_index else "unlabelled_fixed",
        "window_index_source": str(args.window_index.resolve()) if args.window_index else None,
        "settings": {k: getattr(args, k) for k in ("window", "step", "min_samples", "threshold",
                     "finger_threshold", "min_consecutive", "closing_direction")},
        "required_order": EXPECTED_ORDER, "rules": rules, "matches": counts,
        "rule_logic": "OR between alternatives; AND on the same window within each alternative",
        "rule_matches": per_rule, "missing_actions": missing, "complete_sequences": sequences,
        "ordered_prefix": [block_details(a, b, windows, rule_hits) for a, b in prefix.items()],
        "next_unmatched_stage_in_order": next_required,
        "detected_blocks": matches, "time_column": time_column,
        "signal_diagnostics": diagnostics,
        "right_finger_moving_windows": finger_moving,
        "both_fingers_same_direction_windows": agreement,
        "reference_evaluation": reference_metrics(windows, rules), "notes": notes,
    }
    out = (args.output_dir or source.parent / (source.stem + "_whole_motion_check")).expanduser().resolve()
    output_paths = [out / n for n in ("windows.csv", "motion_matches.csv", "whole_motion_report.json")]
    inputs = {source}
    if args.window_index:
        inputs.add(args.window_index.expanduser().resolve())
    if any(p in inputs for p in output_paths):
        raise ValueError("Output directory would overwrite an input file.")
    out.mkdir(parents=True, exist_ok=True)
    (out / "whole_motion_report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n",
                                                 encoding="utf-8")
    pd.DataFrame(windows).to_csv(out / "windows.csv", index=False)
    empty_schema = list(block_details("", (0, 0), windows)) + ["contributing_rule_ids"]
    pd.DataFrame(matches, columns=empty_schema).to_csv(out / "motion_matches.csv", index=False)
    print(f"\nWHOLE MOTION: {report['status']}")
    print("Required: " + " -> ".join(EXPECTED_ORDER))
    if missing:
        print("Actions without qualifying rule matches: " + ", ".join(missing))
    if not sequences:
        print("Matched in order: " + (" -> ".join(prefix) if prefix else "none"))
        print("Next required stage without an eligible block: " + str(next_required))
    for i, sequence in enumerate(sequences, 1):
        print(f"Complete sequence {i}:")
        for event in sequence:
            span = f"rows {event['start_row']}–{event['end_row']}"
            if time_column:
                span += f"; elapsed {event['start_elapsed_sec']:.3f}–{event['end_elapsed_sec']:.3f} s"
            print(f"  {event['action']}: {span} | {event['contributing_rule_ids']}")
    print(f"Finger direction agreement: {agreement}/{finger_moving} moving right-finger windows")
    for note in notes[7:]:
        print("Note: " + note)
    print("Motion evidence only; object handling is unverified.")
    print(f"Results saved in: {out}")
    return report


def make_parser():
    parser = argparse.ArgumentParser(description="Check the full motion using 20-sample fitted trends")
    parser.add_argument("csv", nargs="?", type=Path, default=CSV)
    parser.add_argument("--window", type=int, default=20)
    parser.add_argument("--step", type=int, default=20)
    parser.add_argument("--min-samples", type=int, default=8)
    parser.add_argument("--threshold", type=float, default=ARM_THRESHOLD,
                        help="Arm fitted-change threshold per window (default: 0.004)")
    parser.add_argument("--finger-threshold", type=float, default=FINGER_THRESHOLD)
    parser.add_argument("--min-consecutive", type=int, default=1,
                        help="Minimum consecutive matching windows per event (default: 1)")
    parser.add_argument("--closing-direction", choices=("increases", "decreases"), default="increases")
    parser.add_argument("--window-index", type=Path,
                        help="Optional reference windows from THIS CSV; omit for unlabelled checking")
    parser.add_argument("--output-dir", type=Path)
    return parser


def main():
    parser = make_parser()
    args = parser.parse_args()
    if any(not math.isfinite(v) or v < 0 for v in (args.threshold, args.finger_threshold)):
        parser.error("Thresholds must be finite and non-negative.")
    if args.min_consecutive < 1:
        parser.error("--min-consecutive must be at least 1.")
    if not (2 <= args.min_samples <= args.window and 1 <= args.step <= args.window):
        parser.error("Require 2 <= min-samples <= window and 1 <= step <= window.")
    try:
        check_motion(args)
    except (ValueError, OSError, pd.errors.ParserError) as exc:
        parser.exit(2, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
