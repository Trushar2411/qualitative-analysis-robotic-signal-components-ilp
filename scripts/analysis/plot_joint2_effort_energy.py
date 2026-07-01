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
OUT_CSV = REPO_ROOT / "data" / "processed" / "csv" / "joint3_efforts_energy.csv"
OUT_PLOT = REPO_ROOT / "outputs" / "plots" / "joint3_efforts_energy_sliding_window.png"
COL = "joint3_eff"
WINDOW_SIZE = 20
STEP = 5


def load_signal(input_csv: Path = INPUT_CSV, col: str = COL) -> pd.DataFrame:
    df = pd.read_csv(input_csv)

    if "t_sec" not in df.columns:
        if "timestamp" not in df.columns:
            raise ValueError("CSV must contain either 't_sec' or 'timestamp'.")
        df = df.sort_values("timestamp").reset_index(drop=True)
        t0 = df["timestamp"].iloc[0]
        df["t_sec"] = (df["timestamp"] - t0) * 1e-9

    if col not in df.columns:
        available = ", ".join([c for c in df.columns if "joint3" in c][:20])
        raise ValueError(f"Column '{col}' not found. Available joint3 columns: {available}")

    signal = df[["t_sec", col]].dropna().sort_values("t_sec").reset_index(drop=True)
    signal = signal[np.isfinite(signal["t_sec"]) & np.isfinite(signal[col])]
    if len(signal) < WINDOW_SIZE:
        raise ValueError(f"Need at least {WINDOW_SIZE} valid samples for sliding energy.")
    return signal


def compute_sliding_energy(signal: pd.DataFrame, col: str = COL) -> pd.DataFrame:
    t = signal["t_sec"].to_numpy()
    x = signal[col].to_numpy()
    rows = []

    for start in range(0, len(x) - WINDOW_SIZE + 1, STEP):
        end = start + WINDOW_SIZE
        x_win = x[start:end]
        t_win = t[start:end]
        centered = x_win - np.mean(x_win)

        rows.append(
            {
                "window_id": len(rows),
                "start_time_sec": float(t_win[0]),
                "end_time_sec": float(t_win[-1]),
                "center_time_sec": float(np.mean(t_win)),
                "mean_efforts": float(np.mean(x_win)),
                "range_efforts": float(np.max(x_win) - np.min(x_win)),
                "energy": float(np.sum(centered**2)),
            }
        )

    energy_df = pd.DataFrame(rows)
    q1 = energy_df["energy"].quantile(0.33)
    q2 = energy_df["energy"].quantile(0.66)
    energy_df["energy_label"] = np.select(
        [energy_df["energy"] < q1, energy_df["energy"] < q2],
        ["low_energy", "medium_energy"],
        default="high_energy",
    )
    return energy_df


def save_plot(signal: pd.DataFrame, energy_df: pd.DataFrame, out_plot: Path = OUT_PLOT) -> None:
    out_plot.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 1, figsize=(12, 6), sharex=False)

    axes[0].plot(signal["t_sec"], signal[COL], label=COL)
    axes[0].set_xlabel("Time [s]")
    axes[0].set_ylabel("efforts [rad]")
    axes[0].set_title("Joint 3 efforts")
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()

    axes[1].plot(
        energy_df["center_time_sec"],
        energy_df["energy"],
        marker="o",
        linewidth=1.5,
        label="Sliding energy",
    )
    axes[1].set_xlabel("Time [s]")
    axes[1].set_ylabel("Centered energy")
    axes[1].set_title("Sliding Window Energy")
    axes[1].grid(True, alpha=0.3)
    axes[1].legend()

    fig.tight_layout()
    fig.savefig(out_plot, dpi=160)
    plt.close(fig)


def main() -> None:
    signal = load_signal()
    energy_df = compute_sliding_energy(signal)

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    energy_df.to_csv(OUT_CSV, index=False)
    save_plot(signal, energy_df)

    print(f"Valid samples: {len(signal)}")
    print(f"Saved sliding energy CSV: {OUT_CSV}")
    print(f"Saved sliding energy plot: {OUT_PLOT}")


if __name__ == "__main__":
    main()
