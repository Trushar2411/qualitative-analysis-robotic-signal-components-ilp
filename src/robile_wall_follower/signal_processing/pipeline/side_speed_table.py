import glob, os
import pandas as pd

FOLDER = os.path.expanduser("~/rnd_ws/data_cleaned_odom")
PHASES = ["approaching_wall", "wall_following", "obstacle_detected",
          "obstacle_avoidance", "wall_reacquired"]

files = sorted(glob.glob(os.path.join(FOLDER, "*.csv")))
print("files found:", len(files))

rows = []
for f in files:
    df = pd.read_csv(f)
    label_col = next((c for c in ["action_label", "label", "phase"] if c in df.columns), None)
    if label_col is None or "side_speed" not in df.columns:
        print("skip:", os.path.basename(f))
        continue
    name = os.path.basename(f)
    if "good" not in name:
        continue
    env = "pillar" if "pill" in name else "plain wall"
    d = df[df[label_col].isin(PHASES)][[label_col, "side_speed"]].copy()
    d.columns = ["phase", "side_speed"]
    d["env"] = env
    d["run"] = name
    rows.append(d)

d = pd.concat(rows)

for env in ["plain wall", "pillar"]:
    sub = d[d["env"] == env]
    if sub.empty:
        continue
    t = sub.groupby("phase")["side_speed"].agg(
        rows="size", mean="mean", sd="std", min="min", max="max").round(3)
    t = t.reindex([p for p in PHASES if p in t.index])
    print("\n==========", env, "(", sub["run"].nunique(), "runs ) ==========")
    print("side_speed in m/s   (+ = toward wall/left, - = away)")
    print(t.to_string())

out = os.path.expanduser("~/rnd_ws/phase_plots/side_speed_per_run.csv")
per_run = d.groupby(["env", "run", "phase"])["side_speed"].mean().round(3).unstack()
per_run = per_run[[p for p in PHASES if p in per_run.columns]]
per_run.to_csv(out)
print("\nper-run averages saved to:", out)
