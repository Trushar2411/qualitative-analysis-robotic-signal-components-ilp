from pathlib import Path
import os
import warnings

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
warnings.filterwarnings("ignore", message="Unable to import Axes3D.*")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]

INPUT_CSV = REPO_ROOT / "data" / "processed" / "csv" / "joint_states_filtered_wide.csv"
OUT_CSV = REPO_ROOT / "data" / "processed" / "csv" / "joint2_position_pla_labels.csv"
OUT_PLOT = REPO_ROOT / "outputs" / "plots" / "joint2_position_pla_labels.png"

COL = "joint2_pos"

WINDOW_SIZE = 20
STEP = 20

DIRECTION_THRESHOLD = 0.02
PLA_SEGMENTS = 4


def load_signal(input_csv: Path = INPUT_CSV, col: str = COL) -> pd.DataFrame:
    df = pd.read_csv(input_csv)

    if "t_sec" not in df.columns:
        if "timestamp" not in df.columns:
            raise ValueError("CSV must contain either 't_sec' or 'timestamp'.")

        df = df.sort_values("timestamp").reset_index(drop=True)
        t0 = df["timestamp"].iloc[0]
        df["t_sec"] = (df["timestamp"] - t0) * 1e-9

    if col not in df.columns:
        available = ", ".join([c for c in df.columns if c.endswith("_pos")])
        raise ValueError(
            f"Column '{col}' not found. Available position columns: {available}"
        )

    signal = df[["t_sec", col]].dropna().sort_values("t_sec").reset_index(drop=True)
    signal = signal[np.isfinite(signal["t_sec"]) & np.isfinite(signal[col])]

    if len(signal) < WINDOW_SIZE:
        raise ValueError(f"Need at least {WINDOW_SIZE} valid samples.")

    return signal


def direction_label(slope: float) -> str:
    if slope > DIRECTION_THRESHOLD:
        return "ramp_up"
    if slope < -DIRECTION_THRESHOLD:
        return "ramp_down"
    return "constant"


def build_pla_segments(signal: pd.DataFrame, col: str = COL) -> pd.DataFrame:
    t = signal["t_sec"].to_numpy()
    x = signal[col].to_numpy()

    rows = []
    segment_id = 0

    for start in range(0, len(x) - WINDOW_SIZE + 1, STEP):
        end = start + WINDOW_SIZE

        t_win = t[start:end]
        x_win = x[start:end]

        segment_indices = np.array_split(np.arange(len(x_win)), PLA_SEGMENTS)

        for idx in segment_indices:
            if len(idx) < 2:
                continue

            t_seg = t_win[idx]
            x_seg = x_win[idx]

            slope, intercept = np.polyfit(t_seg, x_seg, 1)
            label = direction_label(float(slope))

            rows.append(
                {
                    "segment_id": segment_id,
                    "joint": "joint2",
                    "start_time_sec": float(t_seg[0]),
                    "end_time_sec": float(t_seg[-1]),
                    "duration_sec": float(t_seg[-1] - t_seg[0]),
                    "label": label,
                    "slope": float(slope),
                    "start_pos": float(x_seg[0]),
                    "end_pos": float(x_seg[-1]),
                }
            )

            segment_id += 1

    return pd.DataFrame(rows)


def merge_same_labels(pla_df: pd.DataFrame) -> pd.DataFrame:
    if pla_df.empty:
        return pla_df

    merged_rows = []
    current = pla_df.iloc[0].to_dict()

    for _, row in pla_df.iloc[1:].iterrows():
        row = row.to_dict()

        if row["label"] == current["label"]:
            current["end_time_sec"] = row["end_time_sec"]
            current["duration_sec"] = current["end_time_sec"] - current["start_time_sec"]
            current["end_pos"] = row["end_pos"]
            current["slope"] = (current["end_pos"] - current["start_pos"]) / max(
                current["duration_sec"], 1e-9
            )
        else:
            merged_rows.append(current)
            current = row

    merged_rows.append(current)

    merged_df = pd.DataFrame(merged_rows)
    merged_df["segment_id"] = range(len(merged_df))

    return merged_df


def save_plot(
    signal: pd.DataFrame,
    pla_df: pd.DataFrame,
    out_plot: Path = OUT_PLOT,
) -> None:
    out_plot.parent.mkdir(parents=True, exist_ok=True)

    t = signal["t_sec"].to_numpy()
    x = signal[COL].to_numpy()

    fig, ax = plt.subplots(figsize=(12, 6))

    ax.plot(
        t,
        x,
        color="lightgray",
        linewidth=1.5,
        label="Original Position",
    )

    added_labels = set()

    for _, row in pla_df.iterrows():
        mask = (t >= row["start_time_sec"]) & (t <= row["end_time_sec"])
        t_seg = t[mask]
        x_seg = x[mask]

        if len(t_seg) < 2:
            continue

        slope, intercept = np.polyfit(t_seg, x_seg, 1)
        y_seg = slope * t_seg + intercept

        if row["label"] == "ramp_up":
            color = "green"
            legend_label = "Ramp Up"
        elif row["label"] == "ramp_down":
            color = "red"
            legend_label = "Ramp Down"
        else:
            color = "blue"
            legend_label = "Constant"

        ax.plot(
            t_seg,
            y_seg,
            color=color,
            linewidth=2.5,
            label=legend_label if legend_label not in added_labels else None,
        )

        added_labels.add(legend_label)

    ax.set_title(f"P: {COL}")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Joint Position")
    ax.grid(True, alpha=0.3)
    ax.legend()

    fig.tight_layout()
    fig.savefig(out_plot, dpi=160)
    plt.close(fig)


def main() -> None:
    signal = load_signal()

    pla_df = build_pla_segments(signal)
    pla_df = merge_same_labels(pla_df)

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    pla_df.to_csv(OUT_CSV, index=False)

    save_plot(signal, pla_df)

    print(f"Valid samples: {len(signal)}")
    print(f"Saved PLA CSV: {OUT_CSV}")
    print(f"Saved PLA plot: {OUT_PLOT}")

    print("\nPLA label timing:")
    print(pla_df[["start_time_sec", "end_time_sec", "duration_sec", "label"]])


if __name__ == "__main__":
    main()