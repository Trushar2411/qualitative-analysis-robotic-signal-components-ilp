import glob, os
import pandas as pd

SET = "lidar+speed"
PHASES = ["approaching_wall", "wall_following", "obstacle_detected",
          "obstacle_avoidance", "wall_reacquired"]

summary, perphase = [], []
for folder in sorted(glob.glob("multisensor_results/*")):
    tag = os.path.basename(folder)
    rf, lf = os.path.join(folder, "rules_all_runs.csv"), os.path.join(folder, "loo_folds.csv")
    if not (os.path.exists(rf) and os.path.exists(lf)):
        continue
    rules = pd.read_csv(rf); rules = rules[rules["set"] == SET]
    loo = pd.read_csv(lf);   loo = loo[loo["set"] == SET]
    if rules.empty:
        continue
    setting = tag.split("_lidar")[0]            # e.g. strict_c3_b4, noisy_c3_b1
    for method in ["QTA", "RAW"]:
        r = rules[rules["method"] == method]
        l = loo[loo["method"] == method]
        tp = int((l["is_target"] & l["matched"]).sum())
        fn = int((l["is_target"] & ~l["matched"]).sum())
        fp = int((~l["is_target"] & l["matched"]).sum())
        summary.append(dict(setting=setting, method=method,
                            train_recall=round(r["recall"].mean(), 2),
                            train_wrong_fires=int(r["wrong_fires"].sum()),
                            no_solution=int((r["rule"] == "NO SOLUTION").sum()),
                            loo_recall=round(tp / (tp + fn), 2) if tp + fn else None,
                            loo_precision=round(tp / (tp + fp), 2) if tp + fp else None,
                            loo_false_alarms=fp))
        for _, row in r.iterrows():
            perphase.append(dict(setting=setting, method=method, phase=row["phase"], rule=row["rule"]))

s = pd.DataFrame(summary).drop_duplicates(["setting", "method"])
print("\n=== lidar + speed: Popper settings compared ===")
print("train_* = on the 7 runs it learned from;  loo_* = on hidden runs (honest)\n")
print(s.sort_values(["method", "setting"]).to_string(index=False))

p = pd.DataFrame(perphase).drop_duplicates(["setting", "method", "phase"])
print("\n=== rules per setting ===")
for (setting, method), g in p.groupby(["setting", "method"]):
    print(f"\n{setting} · {method}")
    for ph in PHASES:
        rr = g[g["phase"] == ph]["rule"]
        if len(rr):
            print(f"   {ph:<19} {rr.iloc[0]}")
s.to_csv("multisensor_results/settings_table_lidar_speed.csv", index=False)
print("\nsaved: multisensor_results/settings_table_lidar_speed.csv")
