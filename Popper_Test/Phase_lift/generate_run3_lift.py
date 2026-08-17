from pathlib import Path
import pandas as pd
import sys

SCRIPT_DIR = Path(__file__).resolve().parent

CSV = Path(
    sys.argv[1]
    if len(sys.argv) > 1
    else SCRIPT_DIR / "full_motion_joint_states.csv"
)

OUT = Path(
    sys.argv[2]
    if len(sys.argv) > 2
    else SCRIPT_DIR / "Run3_phase_lift"
)

OUT.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(CSV)

signals = [
    f"joint{j}_{kind}"
    for j in range(1, 7)
    for kind in ("position", "velocity", "effort")
]

thresholds = {
    "position": 0.002,
    "velocity": 0.01,
    "effort": 0.05,
}

def pred_name(signal, state):
    joint, kind = signal.split("_", 1)
    j = joint.replace("joint", "")
    short = {
        "position": "pos",
        "velocity": "vel",
        "effort": "eff",
    }[kind]

    return f"j{j}_{short}_{state}"


bk = [
    "% Generated qualitative BK for Run 3 - Lift.",
    "% sN describes the change from row N to row N+1.",
    "% Phase labels are intentionally NOT included in BK.",
    "",
]

pos_examples = []
neg_examples = []

for i in range(len(df) - 1):

    # Skip transitions crossing between phases
    if df.loc[i, "phase"] != df.loc[i + 1, "phase"]:
        continue

    state_id = f"s{i}"

    for signal in signals:
        kind = signal.split("_", 1)[1]

        delta = float(
            df.loc[i + 1, signal]
            - df.loc[i, signal]
        )

        eps = thresholds[kind]

        if delta > eps:
            q = "increases"

        elif delta < -eps:
            q = "decreases"

        else:
            q = "constant"

        bk.append(
            f"{pred_name(signal, q)}({state_id})."
        )

    # -------- TARGET: LIFT --------

    if df.loc[i, "phase"] == "lift":
        pos_examples.append(
            f"pos(phase_lift({state_id}))."
        )

    else:
        neg_examples.append(
            f"neg(phase_lift({state_id}))."
        )


# ---------------- BK ----------------

(OUT / "bk.pl").write_text(
    "\n".join(bk) + "\n"
)


# ---------------- EXAMPLES ----------------

exs = [
    "% Positive examples = lift transitions",
    "% Negative examples = non-lift transitions",
    "",
]

exs += pos_examples
exs += [""]
exs += neg_examples
exs += [""]

(OUT / "exs.pl").write_text(
    "\n".join(exs)
)


# ---------------- BIAS ----------------

bias = [
    "max_vars(1).",
    "max_body(4).",
    "max_clauses(3).",
    "",
    "head_pred(phase_lift,1).",
]

for signal in signals:
    for q in (
        "increases",
        "decreases",
        "constant",
    ):
        bias.append(
            f"body_pred({pred_name(signal,q)},1)."
        )


bias.append("")
bias.append(
    "type(phase_lift,(state,))."
)

for signal in signals:
    for q in (
        "increases",
        "decreases",
        "constant",
    ):
        bias.append(
            f"type({pred_name(signal,q)},(state,))."
        )


bias.append("")
bias.append(
    "direction(phase_lift,(in,))."
)

for signal in signals:
    for q in (
        "increases",
        "decreases",
        "constant",
    ):
        bias.append(
            f"direction({pred_name(signal,q)},(in,))."
        )


(OUT / "bias.pl").write_text(
    "\n".join(bias) + "\n"
)


print(f"Created {OUT/'bk.pl'}")
print(f"Created {OUT/'exs.pl'}")
print(f"Created {OUT/'bias.pl'}")

print(
    f"Positive lift examples: "
    f"{len(pos_examples)}"
)

print(
    f"Negative non-lift examples: "
    f"{len(neg_examples)}"
)