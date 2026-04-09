from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
IN_CSV = REPO_ROOT / "data" / "processed" / "csv" / "left_arm_joint2_vel_only.csv"
VEL_COL = "left_arm_joint2_vel"

# --- Motion detection settings ---
VEL_THRESH = 0.01   # rad/s (try 0.02 if it still includes idle)
PAD_SEC = 0.2       # seconds padding before/after detected motion

# --- Load ---
df = pd.read_csv(IN_CSV).dropna(subset=[VEL_COL]).copy()
t = df["t_sec"].to_numpy()
v = df[VEL_COL].to_numpy()

# --- Find moving interval ---
moving = np.abs(v) > VEL_THRESH
if not np.any(moving):
    raise ValueError(f"No motion detected. Lower VEL_THRESH (currently {VEL_THRESH}).")

idx = np.where(moving)[0]

dt = np.median(np.diff(t))
pad_n = int(round(PAD_SEC / dt))

start = max(idx[0] - pad_n, 0)
end = min(idx[-1] + pad_n, len(df) - 1)

df_move = df.iloc[start:end+1].copy()
df_move["t_move"] = df_move["t_sec"] - df_move["t_sec"].iloc[0]

# --- Save moving-only data ---
OUT_CSV = REPO_ROOT / "data" / "processed" / "csv" / "left_arm_joint2_vel_moving_only.csv"
df_move[["t_move", VEL_COL]].to_csv(OUT_CSV, index=False)
print(f"Saved moving-only CSV: {OUT_CSV}")

# --- FFT on moving-only segment ---
tm = df_move["t_move"].to_numpy()
xm = df_move[VEL_COL].to_numpy()

# estimate sampling rate again from trimmed data
dtm = np.diff(tm)
dtm = dtm[np.isfinite(dtm) & (dtm > 0)]
dt_med = np.median(dtm)
fs = 1.0 / dt_med
print(f"Estimated fs (moving-only) ≈ {fs:.3f} Hz")

# remove mean (DC), apply window
N = len(xm)
x_demean = xm - np.mean(xm)
window = np.hanning(N)
xw = x_demean * window

X = np.fft.rfft(xw)
freq = np.fft.rfftfreq(N, d=dt_med)

# magnitude scaling (reasonable for peak comparison)
mag = np.abs(X) / (np.sum(window) / 2.0)

# --- Plot FFT (frequency domain) ---
plt.figure()
plt.plot(freq, mag)
plt.xlabel("Frequency [Hz]")
plt.ylabel("Magnitude")
plt.title("FFT (moving only): left_arm_joint2_vel")
plt.grid(True)

# Optional: limit view to useful range (edit)
# plt.xlim(0, 10)

plt.show()
