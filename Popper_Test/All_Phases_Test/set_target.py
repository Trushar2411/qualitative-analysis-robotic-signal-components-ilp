from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parent
CSV = ROOT / "full_motion_joint_states.csv"

if len(sys.argv) != 2:
    raise SystemExit("Usage: python3 set_target.py <phase>")

target_phase = sys.argv[1]
df = pd.read_csv(CSV)

phases = list(dict.fromkeys(df["phase"].astype(str).tolist()))
if target_phase not in phases:
    raise SystemExit(f"Unknown phase: {target_phase}. Available: {phases}")

signals = [f"joint{j}_{kind}" for j in range(1,7)
           for kind in ("position","velocity","effort")]

def pred_name(signal, state):
    joint, kind = signal.split("_", 1)
    short = {"position":"pos", "velocity":"vel", "effort":"eff"}[kind]
    return f"j{joint.replace('joint','')}_{short}_{state}"

target = f"phase_{target_phase}"

pos, neg = [], []
for i in range(len(df)-1):
    if str(df.loc[i,"phase"]) != str(df.loc[i+1,"phase"]):
        continue
    atom = f"{target}(s{i})"
    if str(df.loc[i,"phase"]) == target_phase:
        pos.append(f"pos({atom}).")
    else:
        neg.append(f"neg({atom}).")

exs = [
    f"% Target: {target}/1",
    f"% Positive = {target_phase}; negative = every other phase.",
    ""
] + pos + [""] + neg + [""]
(ROOT/"exs.pl").write_text("\n".join(exs))

bias = [
    "max_vars(1).",
    "max_body(4).",
    "max_clauses(3).",
    "",
    f"head_pred({target},1).",
]
for signal in signals:
    for q in ("increases","decreases","constant"):
        bias.append(f"body_pred({pred_name(signal,q)},1).")

bias += ["", f"type({target},(state,))."]
for signal in signals:
    for q in ("increases","decreases","constant"):
        bias.append(f"type({pred_name(signal,q)},(state,)).")

bias += ["", f"direction({target},(in,))."]
for signal in signals:
    for q in ("increases","decreases","constant"):
        bias.append(f"direction({pred_name(signal,q)},(in,)).")

(ROOT/"bias.pl").write_text("\n".join(bias)+"\n")
print(f"Target set to {target_phase}: {len(pos)} positive, {len(neg)} negative")
