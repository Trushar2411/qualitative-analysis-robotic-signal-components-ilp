from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
INPUT_CSV = REPO_ROOT / "data" / "processed" / "csv" / "joint_states_filtered_wide.csv"
COL = "left_arm_joint2_eff"

# --- Load ---
df = pd.read_csv(INPUT_CSV)

# Ensure we have a time column
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

# Clean and sort
df = df.dropna(subset=["t_sec", COL]).sort_values("t_sec").reset_index(drop=True)

t = df["t_sec"].to_numpy()
x = df[COL].to_numpy()

# Optional: use magnitude instead of signed torque for easier interpretation
USE_ABSOLUTE_EFFORT = False
x_plot = np.abs(x) if USE_ABSOLUTE_EFFORT else x

# --- Sliding window energy ---
window_size = 20   # number of samples per window
step = 5           # shift between windows

energy_times = []
energy_vals = []

for start in range(0, len(x) - window_size + 1, step):
    end = start + window_size
    x_win = x[start:end]
    t_win = t[start:end]

    # Standard energy over the window
    energy = np.sum(x_win ** 2)

    energy_vals.append(energy)
    energy_times.append(np.mean(t_win))

energy_times = np.array(energy_times)
energy_vals = np.array(energy_vals)

# Optional qualitative labels for energy
q1 = np.quantile(energy_vals, 0.33)
q2 = np.quantile(energy_vals, 0.66)

energy_labels = []
for e in energy_vals:
    if e < q1:
        energy_labels.append("low")
    elif e < q2:
        energy_labels.append("medium")
    else:
        energy_labels.append("high")

# --- Plot ---
plt.figure(figsize=(12, 7))

# Top plot: effort / torque over time
plt.subplot(2, 1, 1)
plt.plot(t, x_plot, linewidth=1.8, label="Joint 2 Effort")
plt.xlabel("Time (s)")
plt.ylabel("Joint Effort (Nm)" if not USE_ABSOLUTE_EFFORT else "|Joint Effort| (Nm)")
plt.title("Joint 2 Effort Over Time")
plt.grid(True, alpha=0.3)
plt.legend()

# Bottom plot: sliding window energy
plt.subplot(2, 1, 2)
plt.plot(energy_times, energy_vals, marker="o", linewidth=1.8, label="Effort Energy")
plt.xlabel("Time (s)")
plt.ylabel("Energy (Nm²)")
plt.title("Sliding Window Effort Energy")
plt.grid(True, alpha=0.3)
plt.legend()

plt.tight_layout()
plt.show()

# --- Print energy summary ---
print("\nSliding-window energy summary:")
print(f"Minimum energy: {energy_vals.min():.3f}")
print(f"Maximum energy: {energy_vals.max():.3f}")
print(f"Mean energy:    {energy_vals.mean():.3f}")

print("\nWindow-wise qualitative energy labels:")
for tm, e, lab in zip(energy_times, energy_vals, energy_labels):
    print(f"time={tm:.2f} s, energy={e:.3f}, label={lab}")
