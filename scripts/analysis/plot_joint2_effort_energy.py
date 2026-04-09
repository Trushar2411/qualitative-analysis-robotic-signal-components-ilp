from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
INPUT_CSV = REPO_ROOT / "data" / "processed" / "csv" / "joint_states_filtered_wide.csv"
COL = "left_arm_joint2_eff"

# --- Load ---
df = pd.read_csv(INPUT_CSV)

if "t_sec" not in df.columns:
    if "timestamp" not in df.columns:
        raise ValueError("CSV must contain either 't_sec' or 'timestamp'.")
    t0 = df["timestamp"].iloc[0]
    df["t_sec"] = (df["timestamp"] - t0) * 1e-9

if COL not in df.columns:
    raise ValueError(
        f"Column '{COL}' not found. Available columns include: "
        f"{', '.join([c for c in df.columns if 'left_arm_joint2' in c][:20])} ..."
    )

df = df.dropna(subset=["t_sec", COL]).sort_values("t_sec").reset_index(drop=True)

t = df["t_sec"].to_numpy()
x = df[COL].to_numpy()

# --- Sliding window energy ---
window_size = 20   # number of samples
step = 5           # shift between windows

energy_times = []
energy_vals = []

for start in range(0, len(x) - window_size + 1, step):
    end = start + window_size
    x_win = x[start:end]
    t_win = t[start:end]

    energy = np.sum(x_win ** 2)
    energy_vals.append(energy)
    energy_times.append(np.mean(t_win))

energy_times = np.array(energy_times)
energy_vals = np.array(energy_vals)

# --- Plot ---
plt.figure(figsize=(12, 6))

plt.subplot(2, 1, 1)
plt.plot(t, x, label=COL)
plt.xlabel("Time (s)")
plt.ylabel("Signal")
plt.title(f"{COL} and Sliding Window Energy")
plt.grid(True, alpha=0.3)
plt.legend()

plt.subplot(2, 1, 2)
plt.plot(energy_times, energy_vals, marker="o", label="Energy")
plt.xlabel("Time (s)")
plt.ylabel("Energy")
plt.grid(True, alpha=0.3)
plt.legend()

plt.tight_layout()
plt.show()
