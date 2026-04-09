from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
INPUT_CSV = REPO_ROOT / "data" / "processed" / "csv" / "joint_states_filtered_wide.csv"
OUT_CSV = REPO_ROOT / "data" / "processed" / "csv" / "left_arm_joint2_pos_only.csv"
COL = "left_arm_joint2_pos"

# --- Load ---
df = pd.read_csv(INPUT_CSV)

# Ensure we have a time column
if "t_sec" not in df.columns:
    if "timestamp" not in df.columns:
        raise ValueError("CSV must contain either 't_sec' or 'timestamp'.")
    t0 = df["timestamp"].iloc[0]
    df["t_sec"] = (df["timestamp"] - t0) * 1e-9

if COL not in df.columns:
    raise ValueError(f"Column '{COL}' not found. Available columns include: "
                     f"{', '.join([c for c in df.columns if 'left_arm_joint2' in c][:20])} ...")

# Keep only time + signal, drop NaNs
sig = df[["t_sec", COL]].dropna().copy()

# Optional: remove infinities
sig = sig[np.isfinite(sig[COL].to_numpy())]

# --- Save extracted data file ---
sig.to_csv(OUT_CSV, index=False)
print(f"Saved extracted signal to: {OUT_CSV}")

t = sig["t_sec"].to_numpy()
x = sig[COL].to_numpy()

# --- Estimate sampling rate (assumes roughly uniform sampling) ---
dt = np.diff(t)
dt = dt[np.isfinite(dt) & (dt > 0)]
if len(dt) < 5:
    raise ValueError("Not enough samples / valid timestamps to estimate sampling rate.")
dt_med = np.median(dt)
fs = 1.0 / dt_med
print(f"Estimated sampling rate fs ≈ {fs:.3f} Hz (median dt = {dt_med:.6f} s)")

# --- FFT ---
# Remove mean (DC offset) so spectrum is cleaner
x_demean = x - np.mean(x)

N = len(x_demean)
window = np.hanning(N)  # reduces spectral leakage
xw = x_demean * window

X = np.fft.rfft(xw)
freq = np.fft.rfftfreq(N, d=dt_med)

# Magnitude (scaled roughly; good enough for comparison/peaks)
mag = np.abs(X) / (np.sum(window) / 2.0)

# --- Plots ---
plt.figure()
plt.plot(t, x)
plt.xlabel("Time [s]")
plt.ylabel("left_arm_joint2_pos [rad]")
plt.title("Time domain: left_arm_joint2_pos")
plt.grid(True)

plt.figure()
plt.plot(freq, mag)
plt.xlabel("Frequency [Hz]")
plt.ylabel("Magnitude")
plt.title("Frequency domain (FFT): left_arm_joint2_pos")
plt.grid(True)

# Optional: focus on low frequencies (edit as you like)
# plt.xlim(0, 10)

plt.show()
