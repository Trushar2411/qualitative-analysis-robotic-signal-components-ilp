from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DATA_DIR = REPO_ROOT / "Processed data"
OUTPUT_ROOT = REPO_ROOT / "outputs" / "SWEE"

WINDOW_SIZE = 20
STEP = 5


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
        "effort",
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
    signal["effort"] = pd.to_numeric(
        signal["effort"],
        errors="coerce",
    )

    signal = signal.dropna(
        subset=["bag_time_sec", "effort"]
    )

    signal = signal.rename(
        columns={"bag_time_sec": "time_sec"}
    )

    signal = signal[
        np.isfinite(signal["time_sec"])
        & np.isfinite(signal["effort"])
    ]

    signal = (
        signal.sort_values("time_sec")
        .reset_index(drop=True)
    )

    if len(signal) < WINDOW_SIZE:
        raise ValueError(
            f"{joint_csv} needs at least {WINDOW_SIZE} "
            "valid samples for SWEE."
        )

    # Make time start from zero for each joint.
    start_time = signal["time_sec"].iloc[0]
    signal["time_sec"] = (
        signal["time_sec"] - start_time
    )

    return signal


def dominant_phase(phases: pd.Series) -> str:
    valid_phases = phases.dropna()

    if valid_phases.empty:
        return "unknown"

    return str(valid_phases.value_counts().idxmax())


def compute_sliding_window_effort_energy(
    signal: pd.DataFrame,
) -> pd.DataFrame:
    time_values = signal["time_sec"].to_numpy(
        dtype=float
    )
    effort_values = signal["effort"].to_numpy(
        dtype=float
    )

    joint_name = str(signal["joint"].iloc[0])

    rows = []

    for start in range(
        0,
        len(effort_values) - WINDOW_SIZE + 1,
        STEP,
    ):
        end = start + WINDOW_SIZE

        effort_window = effort_values[start:end]
        time_window = time_values[start:end]
        phase_window = signal.iloc[start:end]["phase"]

        mean_effort = np.mean(effort_window)

        # Remove the average effort from the window.
        centered_effort = (
            effort_window - mean_effort
        )

        # Sliding-window centered effort energy.
        centered_effort_energy = np.sum(
            centered_effort**2
        )

        rows.append(
            {
                "window_id": len(rows),
                "joint": joint_name,
                "start_time_sec": float(
                    time_window[0]
                ),
                "end_time_sec": float(
                    time_window[-1]
                ),
                "center_time_sec": float(
                    np.mean(time_window)
                ),
                "phase": dominant_phase(
                    phase_window
                ),
                "mean_effort": float(
                    mean_effort
                ),
                "range_effort": float(
                    np.max(effort_window)
                    - np.min(effort_window)
                ),
                "centered_effort_energy": float(
                    centered_effort_energy
                ),
            }
        )

    energy_df = pd.DataFrame(rows)

    if energy_df.empty:
        raise ValueError(
            "No sliding windows could be generated."
        )

    # Divide energy values into low, medium and high
    # categories using the 33% and 66% quantiles.
    low_threshold = energy_df[
        "centered_effort_energy"
    ].quantile(0.33)

    high_threshold = energy_df[
        "centered_effort_energy"
    ].quantile(0.66)

    energy_df["energy_label"] = np.select(
        [
            energy_df["centered_effort_energy"]
            < low_threshold,
            energy_df["centered_effort_energy"]
            < high_threshold,
        ],
        [
            "low_energy",
            "medium_energy",
        ],
        default="high_energy",
    )

    return energy_df


def save_plot(
    signal: pd.DataFrame,
    energy_df: pd.DataFrame,
    out_plot: Path,
) -> None:
    out_plot.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    joint_name = str(signal["joint"].iloc[0])

    fig, axes = plt.subplots(
        nrows=2,
        ncols=1,
        figsize=(14, 8),
        sharex=True,
        constrained_layout=True,
    )

    # First subplot: original effort signal.
    axes[0].plot(
        signal["time_sec"],
        signal["effort"],
        color="tab:blue",
        linewidth=1.2,
        label="Effort",
    )

    axes[0].set_title(
        f"{joint_name} Effort"
    )
    axes[0].set_ylabel("Joint effort [N·m]")
    axes[0].grid(
        True,
        linestyle="--",
        alpha=0.4,
    )
    axes[0].legend()

    # Second subplot: sliding-window effort energy.
    axes[1].plot(
        energy_df["center_time_sec"],
        energy_df["centered_effort_energy"],
        color="tab:red",
        linewidth=1.5,
        label="Centered effort energy",
    )

    axes[1].set_title(
        "Sliding Window Centered Effort Energy "
        f"(window={WINDOW_SIZE}, step={STEP})"
    )
    axes[1].set_xlabel(
        "Time since run start [s]"
    )
    axes[1].set_ylabel(
        "Centered effort energy [N·m²]"
    )
    axes[1].grid(
        True,
        linestyle="--",
        alpha=0.4,
    )
    axes[1].legend()

    fig.suptitle(
        f"{joint_name} Sliding Window "
        "Effort Energy Analysis",
        fontsize=15,
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
        / f"{processed_run_dir.name}_SWEE_{timestamp}"
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

            energy_df = (
                compute_sliding_window_effort_energy(
                    signal
                )
            )

            stem = joint_csv.stem

            output_csv = (
                csv_dir
                / f"{stem}_SWEE.csv"
            )

            output_plot = (
                plots_dir
                / f"{stem}_SWEE.png"
            )

            energy_df.to_csv(
                output_csv,
                index=False,
            )

            save_plot(
                signal,
                energy_df,
                output_plot,
            )

            print(
                f"  CSV saved: {output_csv}"
            )
            print(
                f"  Plot saved: {output_plot}"
            )

        except (ValueError, pd.errors.EmptyDataError) as error:
            print(
                f"  Skipped {joint_csv.name}: {error}"
            )

    return output_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run sliding-window effort-energy "
            "analysis on processed joint effort data."
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
        f"SWEE outputs saved to: {output_dir}"
    )


if __name__ == "__main__":
    main()