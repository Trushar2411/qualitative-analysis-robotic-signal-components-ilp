import glob, os
import numpy as np
import pandas as pd

FOLDER = os.path.expanduser("~/rnd_ws/data_cleaned_odom")

for f in sorted(glob.glob(os.path.join(FOLDER, "*.csv"))):
    df = pd.read_csv(f)
    if "pos_x_odom" not in df.columns:
        print("skip (no odometry):", os.path.basename(f))
        continue
    t = (pd.to_datetime(df["timestamp"], errors="coerce") - pd.Timestamp("1970-01-01")).dt.total_seconds()
    dt = t.diff()
    speed = np.hypot(df["pos_x_odom"].diff(), df["pos_y_odom"].diff()) / dt
    speed[(dt <= 0) | (speed > 1.0)] = np.nan          # remove impossible spikes
    df["total_speed"] = speed.interpolate(limit_direction="both")
    df.to_csv(f, index=False)
    print(f"{os.path.basename(f):<40} total_speed added   median {df['total_speed'].median():.3f} m/s")
