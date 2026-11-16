"""
check_one_run.py  -  take ONE run, show all sensors through the 5 phases,
make the words (QTA + RAW, trend + jump) for every phase piece,
and check which of the final rules fire.

usage:  python3 check_one_run.py pill_good_02
"""
import sys, glob, os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import entry_features as EF                                       # same code as the project
from ilp_multisensor import raw_label, qta_scaled, jump_scaled    # same code as the project

RUN  = sys.argv[1] if len(sys.argv) > 1 else "pill_good_02"
DATA = os.path.expanduser("~/rnd_ws/data_cleaned_odom")
OUT  = os.path.expanduser(f"~/rnd_ws/phase_plots/{RUN}")
PH   = ["approaching_wall", "wall_following", "obstacle_detected", "obstacle_avoidance", "wall_reacquired"]

# speed limits: relative to the range over all good pillar runs (same as in ilp_multisensor.py)
allp = pd.concat(pd.read_csv(f) for f in glob.glob(os.path.join(DATA, "pill_good_*.csv")))
SC = {c: float(np.nanpercentile(allp[c], 95) - np.nanpercentile(allp[c], 5)) for c in ["side_speed", "total_speed"]}

LID = {"lidar_left": "L", "lidar_right": "R", "lidar_front_right": "FR", "lidar_front": "F"}
SH  = {"increasing": "inc", "decreasing": "dec", "constant": "const", "oscillating": "osc", "zero": "zero",
       "jump_up": "jump↑", "jump_down": "jump↓", "no_jump": "no jump", None: "-"}

# final rules (lidar + total speed, noisy, max 4 conditions)
QTA_RULES = {"approaching_wall":   [["L dec"]],
             "wall_following":     [["SPEED const"]],
             "obstacle_detected":  [["L jump↓", "SPEED jump↓", "SPEED dec"]],
             "obstacle_avoidance": [["L inc", "FR no jump"]],
             "wall_reacquired":    [["L jump↑"]]}
RAW_RULES = {"approaching_wall":   [["L dec"]],
             "wall_following":     [["L no jump", "R const"]],
             "obstacle_detected":  [["L const", "L jump↓"]],
             "obstacle_avoidance": [["L inc"]],
             "wall_reacquired":    [["L jump↑"]]}

files = glob.glob(os.path.join(DATA, RUN + "*.csv"))
if not files:
    sys.exit(f"no file for {RUN} in {DATA}")
df = pd.read_csv(files[0])

def fires(rules, words):
    return [ph for ph, rule in rules.items() if any(all(c in words for c in part) for part in rule)]

rows = []
for s in EF.segments(df):
    if s["phase"] not in PH:
        continue
    seg, prev = s["seg"].reset_index(drop=True), s["prev"]
    words = {"QTA": set(), "RAW": set()}
    shown = {}
    for col, n in LID.items():
        q = EF.apply_qta(seg[col].values).replace("is_", "")
        r = raw_label(seg[col].values, 0.01)
        e = EF.entry_label(seg, prev, col)
        for m, t in (("QTA", q), ("RAW", r)):
            if t: words[m].add(f"{n} {SH[t]}")
            if e: words[m].add(f"{n} {SH[e]}")
        shown[n] = (SH.get(q, q), SH.get(r, r), SH.get(e, e))
    for col, n in (("total_speed", "SPEED"), ("side_speed", "SIDE")):
        q = qta_scaled(seg[col].values, SC[col])
        r = raw_label(seg[col].values, 0.01 * SC[col])
        e = jump_scaled(seg, prev, col, SC[col])
        for m, t in (("QTA", q), ("RAW", r)):
            if t: words[m].add(f"{n} {SH[t]}")
            if e: words[m].add(f"{n} {SH[e]}")
        shown[n] = (SH.get(q, q), SH.get(r, r), SH.get(e, e))
    q_f, r_f = fires(QTA_RULES, words["QTA"]), fires(RAW_RULES, words["RAW"])
    rows.append(dict(
        phase=f"{s['phase']} #{s['k']}",
        seconds=len(seg) / 10,
        L_before=None if prev is None else round(prev["lidar_left"].iloc[-5:].mean(), 2),
        L_start=round(seg["lidar_left"].iloc[:5].mean(), 2),
        L_end=round(seg["lidar_left"].iloc[-5:].mean(), 2),
        speed=round(seg["total_speed"].mean(), 3),
        side=round(seg["side_speed"].mean(), 3),
        QTA_L=f"{shown['L'][0]} / {shown['L'][2]}",
        QTA_SPEED=f"{shown['SPEED'][0]} / {shown['SPEED'][2]}",
        QTA_FR=f"{shown['FR'][0]} / {shown['FR'][2]}",
        RAW_L=f"{shown['L'][1]} / {shown['L'][2]}",
        RAW_R=f"{shown['R'][1]} / {shown['R'][2]}",
        QTA_fires=", ".join(q_f) or "none",
        QTA_ok="✅" if q_f == [s["phase"]] else "❌",
        RAW_fires=", ".join(r_f) or "none",
        RAW_ok="✅" if r_f == [s["phase"]] else "❌"))

t = pd.DataFrame(rows)
pd.set_option("display.width", 250)
print(f"\n===== {RUN}: values per phase piece =====")
print(t[["phase", "seconds", "L_before", "L_start", "L_end", "speed", "side"]].to_string(index=False))
print("\n===== words (trend / jump) =====")
print(t[["phase", "QTA_L", "QTA_SPEED", "QTA_FR", "RAW_L", "RAW_R"]].to_string(index=False))
print("\n===== which final rule fires? (✅ = only its own rule fires) =====")
print(t[["phase", "QTA_fires", "QTA_ok", "RAW_fires", "RAW_ok"]].to_string(index=False))
print(f"\nQTA correct: {(t.QTA_ok == '✅').sum()}/{len(t)}    RAW correct: {(t.RAW_ok == '✅').sum()}/{len(t)}")

# ---------- figure: all sensors through the phases ----------
COL = {"approaching_wall": "#9ecae1", "wall_following": "#e5e5e5", "obstacle_detected": "#fb6a4a",
       "obstacle_avoidance": "#fdae6b", "wall_reacquired": "#74c476"}
tt = (pd.to_datetime(df["timestamp"]) - pd.to_datetime(df["timestamp"]).iloc[0]).dt.total_seconds()
P = [("lidar_left", "L  left [m]"), ("lidar_right", "R  right [m]"), ("lidar_front_right", "FR  front-right [m]"),
     ("lidar_front", "F  front [m]"), ("side_speed", "side_speed [m/s]"), ("total_speed", "total_speed [m/s]")]
fig, ax = plt.subplots(len(P), 1, figsize=(18, 15), sharex=True)
seg_id = (df["action_label"] != df["action_label"].shift()).cumsum()
for _, g in df.groupby(seg_id):
    ph = g["action_label"].iloc[0]
    if ph in COL:
        for a in ax:
            a.axvspan(tt[g.index[0]], tt[g.index[-1]] + 0.1, color=COL[ph], alpha=0.6, lw=0)
for a, (c, lab) in zip(ax, P):
    a.plot(tt, df[c], color="#14213D", lw=1.4)
    a.set_ylabel(lab, fontsize=11)
    a.grid(alpha=0.25)
    if "speed" in c:
        a.axhline(0, color="black", lw=0.7)
handles = [plt.Rectangle((0, 0), 1, 1, color=v, alpha=0.6) for v in COL.values()]
ax[0].legend(handles, COL.keys(), ncol=5, loc="upper center", bbox_to_anchor=(0.5, 1.32), fontsize=11)
ax[-1].set_xlabel("time since start [s]", fontsize=11)
fig.suptitle(f"{RUN}: all sensors through the five phases", fontsize=15, y=0.995)
fig.tight_layout()
os.makedirs(OUT, exist_ok=True)
png = os.path.join(OUT, f"check_one_run_{RUN}.png")
fig.savefig(png, dpi=130)
t.to_csv(os.path.join(OUT, f"check_one_run_{RUN}.csv"), index=False)
print(f"\nsaved: {png}")
