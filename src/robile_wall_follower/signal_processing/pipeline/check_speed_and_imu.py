import glob, os
import numpy as np
import pandas as pd

CLEAN = os.path.expanduser("~/rnd_ws/data_cleaned_odom")
RAW_FOLDERS = [os.path.expanduser("~/rnd_ws/data"), os.path.expanduser("~/rnd_ws/data_pillar")]
PHASES = ["approaching_wall", "wall_following", "obstacle_detected",
          "obstacle_avoidance", "wall_reacquired"]

def to_seconds(t):
    # timestamps are date-time text -> seconds since 1970
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
print("raw IMU rows:", len(raw))

rows = []
for f in sorted(glob.glob(os.path.join(CLEAN, "*.csv"))):
    name = os.path.basename(f)
    if "good" not in name:
        continue
    df = pd.read_csv(f)
    lab = next((c for c in ["action_label", "label", "phase"] if c in df.columns), None)
    if lab is None or "pos_x_odom" not in df.columns:
        print("skip:", name)
        continue
    df["timestamp"] = to_seconds(df["timestamp"])
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp")
    dt = df["timestamp"].diff()

    # total speed: distance moved per second, any direction (no heading needed)
    df["total_speed"] = np.hypot(df["pos_x_odom"].diff(), df["pos_y_odom"].diff()) / dt

    # sideways acceleration from the raw files, smoothed over ~1 s
    df = df.drop(columns=[c for c in df.columns if c.startswith("imu_accel_y")])
    df = pd.merge_asof(df, raw, on="timestamp", direction="nearest", tolerance=0.06)
    df["accel_y_smooth"] = df["imu_accel_y"].rolling(10, center=True, min_periods=3).mean()

    # mark the first 5 rows (0.5 s) of every phase segment
    seg = (df[lab] != df[lab].shift()).cumsum()
    df["first_half_s"] = df.groupby(seg).cumcount() < 5

    df["env"] = "pillar" if "pill" in name else "plain wall"
    df["phase"] = df[lab]
    rows.append(df[df["phase"].isin(PHASES)])

d = pd.concat(rows)
for env in ["plain wall", "pillar"]:
    s = d[d["env"] == env]
    if s.empty:
        continue
    print("\n==========", env, "(", len(s), "rows ) ==========")
    t = s.groupby("phase").agg(
        rows=("phase", "size"),
        total_speed=("total_speed", "mean"),
        total_speed_sd=("total_speed", "std"),
        accel_y_whole=("accel_y_smooth", "mean"),
        imu_rows=("imu_accel_y", "count"),
    )
    t["accel_y_first_0.5s"] = s[s["first_half_s"]].groupby("phase")["accel_y_smooth"].mean()
    t = t.reindex([p for p in PHASES if p in t.index]).round(3)
    print(t.to_string())
