import os
import pandas as pd

FOLDER = "multisensor_results/noisy_c3_b4_lidar+speed"
PHASES = ["approaching_wall", "wall_following", "obstacle_detected",
          "obstacle_avoidance", "wall_reacquired"]

t = pd.read_csv(os.path.join(FOLDER, "loo_folds.csv"))
t = t[t["set"] == "lidar+speed"]

rows = []
for method in ["QTA", "RAW"]:
    for phase in PHASES:
        s = t[(t["method"] == method) & (t["phase"] == phase)]
        tp = int((s["is_target"] & s["matched"]).sum())    # own phase, rule fired      (correct)
        fn = int((s["is_target"] & ~s["matched"]).sum())   # own phase, rule silent     (missed)
        fp = int((~s["is_target"] & s["matched"]).sum())   # other phase, rule fired    (false alarm)
        recall = tp / (tp + fn) if tp + fn else float("nan")
        precision = tp / (tp + fp) if tp + fp else float("nan")
        rows.append(dict(method=method, phase=phase, caught=f"{tp}/{tp+fn}",
                         false_alarms=fp, recall=round(recall, 2), precision=round(precision, 2)))

r = pd.DataFrame(rows)
print("\nLEAVE-ONE-RUN-OUT, lidar + speed  (rules tested on the hidden run only)\n")
print(r.to_string(index=False))
for method in ["QTA", "RAW"]:
    m = r[r["method"] == method]
    print(f"\n{method}: average recall {m['recall'].mean():.2f}   average precision {m['precision'].mean():.2f}")
