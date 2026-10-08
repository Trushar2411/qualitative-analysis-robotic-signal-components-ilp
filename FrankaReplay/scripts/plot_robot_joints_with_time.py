#!/usr/bin/env python3
"""Plot Franka arm and finger position/velocity against time in seconds."""

import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def plot(csv_path: Path, output_dir: Path, time_col: str = "time_seconds"):
    df = pd.read_csv(csv_path)
    if time_col not in df.columns:
        raise ValueError(
            f"'{time_col}' not found in {csv_path}. Available columns: {list(df.columns)}"
        )
    time = pd.to_numeric(df[time_col], errors="raise").to_numpy(dtype=float)
    if not np.isfinite(time).all() or np.any(np.diff(time) < 0):
        raise ValueError("Time must contain finite, nondecreasing values.")
    time = time - time[0]  # elapsed seconds since first observation
    output_dir.mkdir(parents=True, exist_ok=True)

    for kind in ("position", "velocity"):
        fig, axes = plt.subplots(
            9, 1, figsize=(13, 18), sharex=True, constrained_layout=True
        )
        for i, ax in enumerate(axes):
            label = f"Joint {i+1}" if i < 7 else f"Finger {i-6}"
            col = f"joint_{i+1}_{kind}" if i < 7 else f"finger_{i-6}_{kind}"
            if col not in df.columns:
                raise ValueError(f"Missing column: {col}")
            values = pd.to_numeric(df[col], errors="raise").to_numpy(dtype=float)
            ax.plot(time, values, linewidth=1.15)
            ax.set_ylabel(label, rotation=0, labelpad=40)
            ax.grid(alpha=0.3)
        axes[-1].set_xlabel("Elapsed time (seconds)")
        fig.suptitle(
            f"{csv_path.stem}: {kind.capitalize()} vs time (7 arm joints + 2 fingers)",
            fontsize=15,
        )
        out = output_dir / f"{csv_path.stem}_{kind}_vs_time.png"
        fig.savefig(out, dpi=180, bbox_inches="tight")
        plt.close(fig)
        print(f"Saved: {out}")
    print(f"Duration (first to last recorded sample): {time[-1]:.3f} seconds")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "csv", type=Path, help="CSV containing time_seconds and filtered joint columns"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "outputs" / "joint_plots",
    )
    parser.add_argument(
        "--time-col",
        default="time_seconds",
        help="Time column name (default: time_seconds)",
    )
    args = parser.parse_args()
    plot(args.csv, args.output, args.time_col)
