import glob, os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

CLEAN = os.path.expanduser("~/rnd_ws/data_cleaned_odom")
RAW_FOLDERS = [os.path.expanduser("~/rnd_ws/data"), os.path.expanduser("~/rnd_ws/data_pillar")]
OUT = os.path.expanduser("~/rnd_ws/phase_plots")

PHASE_COLORS = {
    "approaching_wall":   "#9ecae1",
    "wall_following":     "#d9d9d9",
    "obstacle_detected":  "#fb6a4a",
    "obstacle_avoidance": "#fdae6b",
    "wall_reacquired":    "#74c476",
}

def to_seconds(t):
    dt = pd.to_datetime(t, errors="coerce")
    return (dt - pd.Timestamp("1970-01-01")).dt.total_seconds()

# raw IMU from all raw files
raw = []
for folder in RAW_FOLDERS:
    for f in glob.glob(os.path.join(folder, "*.csv")):
        r = pd.read_csv(f)
        if "imu_accel_y" in r.columns and "timestamp" in r.columns:
            raw.append(r[["timestamp", "imu_accel_y"]].copy())
raw = pd.concat(raw)
raw["timestamp"] = to_seconds(raw["timestamp"])
raw = raw.dropna(subset=["timestamp"]).sort_values("timestamp")

files = sorted(f for f in glob.glob(os.path.join(CLEAN, "*.csv"))
               if "pill" in os.path.basename(f) and "good" in os.path.basename(f))
print("pillar good runs:", len(files))

for f in files:
    run = os.path.basename(f).replace(".csv", "")
    df = pd.read_csv(f)
    lab = next((c for c in ["action_label", "label", "phase"] if c in df.columns), None)
    df["timestamp"] = to_seconds(df["timestamp"])
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)

    # total speed, with impossible spikes removed (> 1 m/s or bad time step)
    dt = df["timestamp"].diff()
    ts = np.hypot(df["pos_x_odom"].diff(), df["pos_y_odom"].diff()) / dt
    ts[(dt <= 0) | (ts > 1.0)] = np.nan
    df["total_speed"] = ts

    # IMU sideways acceleration, smoothed over ~1 s, offset removed
    df = df.drop(columns=[c for c in df.columns if c.startswith("imu_accel_y")])
    df = pd.merge_asof(df, raw, on="timestamp", direction="nearest", tolerance=0.06)
    df["accel_y_smooth"] = df["imu_accel_y"].rolling(10, center=True, min_periods=3).mean()
    offset = df.loc[df[lab] == "wall_following", "accel_y_smooth"].median()
    df["accel_y_minus_offset"] = df["accel_y_smooth"] - offset

    t = df["timestamp"] - df["timestamp"].iloc[0]

    panels = [
        ("lidar_left", "left lidar [m]"),
        ("side_speed", "side_speed [m/s]\n(+ toward wall)"),
        ("total_speed", "total_speed [m/s]"),
        ("accel_y_minus_offset", "IMU accel_y\nminus offset [m/s²]"),
    ]
    fig, axes = plt.subplots(len(panels), 1, figsize=(16, 11), sharex=True)

    # coloured background per phase
    seg = (df[lab] != df[lab].shift()).cumsum()
    for _, g in df.groupby(seg):
        ph = g[lab].iloc[0]
        if ph not in PHASE_COLORS:
            continue
        for ax in axes:
            ax.axvspan(t[g.index[0]], t[g.index[-1]], color=PHASE_COLORS[ph], alpha=0.5, lw=0)

    for ax, (col, title) in zip(axes, panels):
        if col in df.columns:
            ax.plot(t, df[col], color="#14213D", lw=1.5)
        else:
            ax.text(0.5, 0.5, col + " not in file", transform=ax.transAxes, ha="center")
        ax.set_ylabel(title, fontsize=10)
        ax.grid(alpha=0.3)
        if col in ("side_speed", "accel_y_minus_offset"):
            ax.axhline(0, color="black", lw=0.8)

    handles = [plt.Rectangle((0, 0), 1, 1, color=c, alpha=0.5) for c in PHASE_COLORS.values()]
    axes[0].legend(handles, PHASE_COLORS.keys(), ncol=5, loc="upper center",
                   bbox_to_anchor=(0.5, 1.35), fontsize=10)
    axes[-1].set_xlabel("time since start [s]")
    fig.suptitle(run + f"   (IMU offset removed: {offset:.3f})", y=0.995)
    fig.tight_layout()

    os.makedirs(os.path.join(OUT, run), exist_ok=True)
    out = os.path.join(OUT, run, f"speed_imu_{run}.png")
    fig.savefig(out, dpi=120)
    plt.close(fig)

    # numbers: IMU in first 0.5 s of avoidance / reacquired (offset removed)
    first = df.groupby(seg).cumcount() < 5
    av = df.loc[first & (df[lab] == "obstacle_avoidance"), "accel_y_minus_offset"].mean()
    re = df.loc[first & (df[lab] == "wall_reacquired"), "accel_y_minus_offset"].mean()
    print(f"{run:<28} avoidance start: {av:+.3f}   reacquired start: {re:+.3f}   -> {out}")
