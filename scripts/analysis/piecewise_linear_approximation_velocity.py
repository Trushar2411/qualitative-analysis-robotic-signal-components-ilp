from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DATA_DIR = REPO_ROOT / "Processed data"
OUTPUT_ROOT = REPO_ROOT / "outputs" / "PLA"

WINDOW_SIZE = 20
STEP = 20
PLA_SEGMENTS = 4
DIRECTION_THRESHOLD = 0.02


def find_latest_processed_run(
    processed_data_dir: Path = PROCESSED_DATA_DIR,
) -> Path:
    if not processed_data_dir.exists():
        raise FileNotFoundError(
            f"Processed data folder not found: {processed_data_dir}"
        )

    runs = [
        path
        for path in processed_data_dir.iterdir()
        if path.is_dir() and any(path.glob("joint_*.csv"))
    ]

    if not runs:
        raise FileNotFoundError(
            f"No processed runs found in {processed_data_dir} "
            "containing joint_*.csv"
        )

    return max(runs, key=lambda path: path.stat().st_mtime)


def load_joint_signal(joint_csv: Path) -> pd.DataFrame:
    df = pd.read_csv(joint_csv)

    required_columns = [
        "joint",
        "bag_time_sec",
        "velocity",
        "phase",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"{joint_csv} is missing: {', '.join(missing_columns)}"
        )

    signal = df[required_columns].copy()

    signal["bag_time_sec"] = pd.to_numeric(
        signal["bag_time_sec"],
        errors="coerce",
    )
    signal["velocity"] = pd.to_numeric(
        signal["velocity"],
        errors="coerce",
    )

    signal = signal.dropna(
        subset=["bag_time_sec", "velocity"]
    )

    signal = signal.rename(
        columns={"bag_time_sec": "time_sec"}
    )

    signal = signal[
        np.isfinite(signal["time_sec"])
        & np.isfinite(signal["velocity"])
    ]

    signal = (
        signal.sort_values("time_sec")
        .reset_index(drop=True)
    )

    if len(signal) < WINDOW_SIZE:
        raise ValueError(
            f"{joint_csv} needs at least {WINDOW_SIZE} "
            "valid samples."
        )

    # Start time at zero for each joint signal.
    start_time = signal["time_sec"].iloc[0]
    signal["time_sec"] = (
        signal["time_sec"] - start_time
    )

    return signal


def direction_label(slope: float) -> str:
    if slope > DIRECTION_THRESHOLD:
        return "ramp_up"

    if slope < -DIRECTION_THRESHOLD:
        return "ramp_down"

    return "constant"


def dominant_phase(phases: pd.Series) -> str:
    valid_phases = phases.dropna()

    if valid_phases.empty:
        return "unknown"

    return str(
        valid_phases.value_counts().idxmax()
    )


def build_pla_segments(
    signal: pd.DataFrame,
) -> pd.DataFrame:
    time_values = signal["time_sec"].to_numpy(
        dtype=float
    )
    velocity_values = signal["velocity"].to_numpy(
        dtype=float
    )

    joint_name = str(signal["joint"].iloc[0])

    rows = []
    segment_id = 0

    for start in range(
        0,
        len(velocity_values) - WINDOW_SIZE + 1,
        STEP,
    ):
        end = start + WINDOW_SIZE

        window_indices = np.arange(start, end)

        segment_indices = np.array_split(
            window_indices,
            PLA_SEGMENTS,
        )

        for indices in segment_indices:
            if len(indices) < 2:
                continue

            time_segment = time_values[indices]
            velocity_segment = velocity_values[indices]

            slope, intercept = np.polyfit(
                time_segment,
                velocity_segment,
                1,
            )

            rows.append(
                {
                    "segment_id": segment_id,
                    "joint": joint_name,
                    "start_time_sec": float(
                        time_segment[0]
                    ),
                    "end_time_sec": float(
                        time_segment[-1]
                    ),
                    "duration_sec": float(
                        time_segment[-1]
                        - time_segment[0]
                    ),
                    "phase": dominant_phase(
                        signal.iloc[indices]["phase"]
                    ),
                    "label": direction_label(
                        float(slope)
                    ),
                    "slope": float(slope),
                    "intercept": float(intercept),
                    "start_velocity": float(
                        velocity_segment[0]
                    ),
                    "end_velocity": float(
                        velocity_segment[-1]
                    ),
                    "mean_velocity": float(
                        np.mean(velocity_segment)
                    ),
                }
            )

            segment_id += 1

    return pd.DataFrame(rows)


def merge_same_labels(
    pla_df: pd.DataFrame,
) -> pd.DataFrame:
    if pla_df.empty:
        return pla_df

    merged_rows = []
    current = pla_df.iloc[0].to_dict()

    for _, next_row in pla_df.iloc[1:].iterrows():
        row = next_row.to_dict()

        same_label = (
            row["label"] == current["label"]
        )
        same_phase = (
            row["phase"] == current["phase"]
        )

        if same_label and same_phase:
            current["end_time_sec"] = (
                row["end_time_sec"]
            )

            current["duration_sec"] = (
                current["end_time_sec"]
                - current["start_time_sec"]
            )

            current["end_velocity"] = (
                row["end_velocity"]
            )

            current["mean_velocity"] = (
                current["start_velocity"]
                + current["end_velocity"]
            ) / 2.0

            current["slope"] = (
                current["end_velocity"]
                - current["start_velocity"]
            ) / max(
                current["duration_sec"],
                1e-9,
            )

            current["intercept"] = (
                current["start_velocity"]
                - current["slope"]
                * current["start_time_sec"]
            )

        else:
            merged_rows.append(current)
            current = row

    merged_rows.append(current)

    merged_df = pd.DataFrame(merged_rows)
    merged_df["segment_id"] = range(
        len(merged_df)
    )

    return merged_df


def save_plot(
    signal: pd.DataFrame,
    pla_df: pd.DataFrame,
    out_plot: Path,
) -> None:
    out_plot.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    time_values = signal["time_sec"].to_numpy(
        dtype=float
    )
    velocity_values = signal["velocity"].to_numpy(
        dtype=float
    )

    joint_name = str(signal["joint"].iloc[0])

    colors = {
        "ramp_up": "tab:green",
        "ramp_down": "tab:red",
        "constant": "tab:blue",
    }

    fig, axis = plt.subplots(
        figsize=(14, 7),
        constrained_layout=True,
    )

    # Plot the original velocity signal.
    axis.plot(
        time_values,
        velocity_values,
        color="0.75",
        linewidth=1.2,
        label="Raw velocity",
        zorder=1,
    )

    labels_added = set()

    # Plot each PLA segment.
    for _, row in pla_df.iterrows():
        start_time = float(
            row["start_time_sec"]
        )
        end_time = float(
            row["end_time_sec"]
        )

        mask = (
            (time_values >= start_time)
            & (time_values <= end_time)
        )

        segment_time = time_values[mask]
        segment_velocity = velocity_values[mask]

        if len(segment_time) < 2:
            continue

        # Recalculate the best-fit line over the complete
        # merged segment.
        slope, intercept = np.polyfit(
            segment_time,
            segment_velocity,
            1,
        )

        fitted_velocity = (
            slope * segment_time + intercept
        )

        label = str(row["label"])
        color = colors.get(label, "black")

        legend_label = (
            label.replace("_", " ").title()
            if label not in labels_added
            else None
        )

        axis.plot(
            segment_time,
            fitted_velocity,
            color=color,
            linewidth=2.5,
            label=legend_label,
            zorder=2,
        )

        labels_added.add(label)

    axis.set_title(
        f"{joint_name} Velocity Piecewise Linear Approximation",
        fontsize=15,
    )

    axis.set_xlabel(
        "Time since run start [s]"
    )
    axis.set_ylabel(
        "Velocity"
    )

    axis.grid(
        True,
        linestyle="--",
        alpha=0.4,
    )

    axis.axhline(
        y=0,
        color="black",
        linewidth=0.8,
        alpha=0.6,
    )

    axis.legend(
        loc="best"
    )

    fig.savefig(
        out_plot,
        dpi=300,
        bbox_inches="tight",
    )

    plt.close(fig)


def analyze_run(
    processed_run_dir: Path,
) -> Path:
    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    output_dir = (
        OUTPUT_ROOT
        / f"{processed_run_dir.name}_PLA_{timestamp}"
    )

    csv_dir = output_dir / "csv"
    plots_dir = output_dir / "plots"

    csv_dir.mkdir(
        parents=True,
        exist_ok=False,
    )
    plots_dir.mkdir(
        parents=True,
        exist_ok=False,
    )

    joint_csv_files = sorted(
        processed_run_dir.glob("joint_*.csv")
    )

    if not joint_csv_files:
        raise FileNotFoundError(
            f"No joint_*.csv files found in "
            f"{processed_run_dir}"
        )

    for joint_csv in joint_csv_files:
        print(f"Processing: {joint_csv.name}")

        try:
            signal = load_joint_signal(
                joint_csv
            )

            initial_pla_df = build_pla_segments(
                signal
            )

            pla_df = merge_same_labels(
                initial_pla_df
            )

            if pla_df.empty:
                print(
                    f"  Skipped {joint_csv.name}: "
                    "no PLA segments were generated."
                )
                continue

            stem = joint_csv.stem

            output_csv = (
                csv_dir
                / f"{stem}_PLA.csv"
            )

            output_plot = (
                plots_dir
                / f"{stem}_PLA.png"
            )

            pla_df.to_csv(
                output_csv,
                index=False,
            )

            save_plot(
                signal,
                pla_df,
                output_plot,
            )

            print(
                f"  CSV saved: {output_csv}"
            )
            print(
                f"  Plot saved: {output_plot}"
            )

        except (
            ValueError,
            pd.errors.EmptyDataError,
        ) as error:
            print(
                f"  Skipped {joint_csv.name}: {error}"
            )

    return output_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run piecewise linear approximation "
            "on processed joint velocity data."
        )
    )

    parser.add_argument(
        "--processed-run",
        type=Path,
        default=None,
        help=(
            "Path to a Processed data run folder. "
            "Defaults to the latest processed run."
        ),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.processed_run is not None:
        processed_run_dir = (
            args.processed_run.expanduser().resolve()
        )
    else:
        processed_run_dir = (
            find_latest_processed_run()
        )

    if not processed_run_dir.exists():
        raise FileNotFoundError(
            f"Processed run folder not found: "
            f"{processed_run_dir}"
        )

    output_dir = analyze_run(
        processed_run_dir
    )

    print()
    print(
        f"Processed run used: {processed_run_dir}"
    )
    print(
        f"PLA outputs saved to: {output_dir}"
    )


if __name__ == "__main__":
    main()