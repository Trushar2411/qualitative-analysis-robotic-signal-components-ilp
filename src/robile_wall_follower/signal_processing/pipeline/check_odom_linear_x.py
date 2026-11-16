import glob, os
import pandas as pd

FOLDERS = {"plain wall": "~/rnd_ws/data", "pillar": "~/rnd_ws/data_pillar"}

for name, folder in FOLDERS.items():
    files = sorted(glob.glob(os.path.join(os.path.expanduser(folder), "*.csv")))
    frames = []
    for f in files:
        df = pd.read_csv(f)
        if "odom_linear_x" not in df.columns or "action_label" not in df.columns:
            print("skip (missing columns):", os.path.basename(f))
            continue
        df["run"] = os.path.basename(f)
        frames.append(df)
    if not frames:
        continue
    d = pd.concat(frames)
    print("\n==========", name, "(", len(frames), "files ) ==========")
    t = d.groupby("action_label").agg(
        rows=("odom_linear_x", "size"),
        measured_mean=("odom_linear_x", "mean"),
        measured_sd=("odom_linear_x", "std"),
        command_mean=("cmd_linear_x", "mean"),
    ).round(3)
    print(t.to_string())
    print("\nzero rows:", (d["odom_linear_x"] == 0).mean().round(3) * 100, "%")
