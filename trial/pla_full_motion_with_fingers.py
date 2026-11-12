#!/usr/bin/env python3
"""Phase-wise PLA for xArm6 and gripper data. Excludes idle."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

WINDOW = 10
STEP = 5
THRESHOLDS = {"position": 0.005, "velocity": 0.010, "effort": 0.050}
ARM = [f"joint{i}" for i in range(1, 7)]
FINGERS = [
    "drive_joint", "left_finger_joint", "left_inner_knuckle_joint",
    "right_outer_knuckle_joint", "right_finger_joint",
    "right_inner_knuckle_joint",
]

def windows_for_group(df, columns, threshold, window, step):
    """Fit small windows independently within each contiguous phase segment."""
    records = []
    phase_values = df["phase"].astype(str)
    # Segment at phase changes, even if a phase name occurs again later.
    segments = phase_values.ne(phase_values.shift()).cumsum()
    for segment_id, part in df.groupby(segments, sort=False):
        phase = str(part["phase"].iloc[0])
        t = pd.to_numeric(part["bag_time_sec"], errors="coerce").to_numpy(float)
        t = t - t[0]
        starts = list(range(0, len(part) - window + 1, step))
        if len(part) >= window and starts[-1] != len(part) - window:
            starts.append(len(part) - window)  # include final samples
        for start in starts:
            end = start + window
            record = {"phase": phase, "segment": int(segment_id),
                      "cycle": part["cycle"].iloc[0],
                      "start_index": int(part.index[start]),
                      "end_index": int(part.index[end-1]),
                      "start_time_sec": float(t[start]),
                      "end_time_sec": float(t[end-1])}
            for col in columns:
                y = pd.to_numeric(part[col].iloc[start:end], errors="coerce").to_numpy(float)
                tx = t[start:end]
                valid = np.isfinite(tx) & np.isfinite(y)
                if valid.sum() < 2 or np.ptp(tx[valid]) <= 0:
                    label, slope, change, rmse = "unavailable", np.nan, np.nan, np.nan
                else:
                    slope, intercept = np.polyfit(tx[valid] - tx[valid][0], y[valid], 1)
                    predicted = slope * (tx[valid] - tx[valid][0]) + intercept
                    change = float(slope * np.ptp(tx[valid]))
                    rmse = float(np.sqrt(np.mean((y[valid] - predicted)**2)))
                    label = ("ramp_up" if change > threshold else
                             "ramp_down" if change < -threshold else "constant")
                record[col + "_label"] = label
                record[col + "_slope"] = slope
                record[col + "_change"] = change
                record[col + "_rmse"] = rmse
            records.append(record)
    return pd.DataFrame(records)

def summarize(windows, columns, phases):
    rows = []
    for phase in phases:
        part = windows.loc[windows["phase"] == phase] if not windows.empty else pd.DataFrame()
        row = {"phase": phase}
        for col in columns:
            counts = (part[col + "_label"].value_counts()
                      if not part.empty else pd.Series(dtype=int))
            valid_count = sum(int(counts.get(k, 0)) for k in
                              ("ramp_up", "ramp_down", "constant"))
            if valid_count:
                # Ties: prefer constant, then ramp_up, then ramp_down.
                priority = ["constant", "ramp_up", "ramp_down"]
                label = max(priority, key=lambda x: (int(counts.get(x, 0)), -priority.index(x)))
                fraction = int(counts.get(label, 0)) / valid_count
            else:
                label, fraction = "unavailable", np.nan
            row[col] = label
            row[col + "_dominant_fraction"] = fraction
            for k in ("ramp_up", "ramp_down", "constant"):
                row[col + "_" + k + "_count"] = int(counts.get(k, 0))
        rows.append(row)
    return pd.DataFrame(rows)

def make_plot(df, cols, group, out, window, step):
    fig, ax = plt.subplots(figsize=(16, 7))
    t = df["bag_time_sec"].to_numpy(float)
    for col in cols:
        y = pd.to_numeric(df[col], errors="coerce")
        if y.notna().any():
            ax.plot(t, y, linewidth=1.0, label=col)
    phases = df["phase"].astype(str)
    changes = np.flatnonzero(phases.ne(phases.shift()).to_numpy())
    for i in changes:
        ax.axvline(t[i], linestyle="--", linewidth=0.8, alpha=0.5)
    if len(t):
        ytop = ax.get_ylim()[1]
        for i in changes:
            ax.annotate(phases.iloc[i], (t[i], ytop), xytext=(2, -4),
                        textcoords="offset points", rotation=90, va="top", fontsize=8)
    ax.set(title=f"{group} — phase-wise PLA input (window={window}, step={step})",
           xlabel="bag_time_sec [s]", ylabel="Recorded signal value")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8, ncol=2, loc="best")
    fig.tight_layout()
    fig.savefig(out, dpi=180)
    plt.close(fig)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_file")
    ap.add_argument("--output-dir", default="pla_output")
    ap.add_argument("--window", type=int, default=WINDOW)
    ap.add_argument("--step", type=int, default=STEP)
    for kind, value in THRESHOLDS.items():
        ap.add_argument("--" + kind + "-threshold", type=float, default=value)
    args = ap.parse_args()
    if args.window < 2 or args.step < 1:
        ap.error("window must be >=2 and step must be >=1")
    df = pd.read_csv(args.csv_file)
    if "phase" not in df or "bag_time_sec" not in df:
        ap.error("CSV must contain phase and bag_time_sec")
    df = df.loc[df["phase"].notna() & df["phase"].astype(str).str.strip().str.lower().ne("idle")].copy()
    if df.empty:
        ap.error("No non-idle data found")
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    phases = list(dict.fromkeys(df["phase"].astype(str)))
    groups = {
        "position": [f"{j}_position" for j in ARM],
        "velocity": [f"{j}_velocity" for j in ARM],
        "effort": [f"{j}_effort" for j in ARM],
        "finger_position": [f"{j}_position" for j in FINGERS],
    }
    for group, cols in groups.items():
        missing = [c for c in cols if c not in df]
        if missing:
            print(f"Skipping {group}: missing columns {missing}")
            continue
        threshold_type = "position" if group == "finger_position" else group
        threshold = getattr(args, threshold_type + "_threshold")
        detailed = windows_for_group(df, cols, threshold, args.window, args.step)
        summary = summarize(detailed, cols, phases)
        summary.to_csv(out / f"pla_{group}_phase_summary.csv", index=False)
        detailed.to_csv(out / f"pla_{group}_windows.csv", index=False)
        make_plot(df, cols, group, out / f"pla_{group}.png", args.window, args.step)
        print(f"\n{group.upper()} (threshold={threshold})")
        print(summary[["phase"] + cols].to_string(index=False))
        if all(df[c].isna().all() for c in cols):
            print("WARNING: all values missing; classifications are 'unavailable'.")
    print(f"\nFinished. Results in: {out.resolve()}")

if __name__ == "__main__":
    main()
