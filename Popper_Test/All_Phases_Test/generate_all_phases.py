from pathlib import Path
import pandas as pd
import sys


SCRIPT_DIR = Path(__file__).resolve().parent

CSV = Path(
    sys.argv[1]
    if len(sys.argv) > 1
    else SCRIPT_DIR / "full_motion_joint_states.csv"
)

OUT_ROOT = Path(
    sys.argv[2]
    if len(sys.argv) > 2
    else SCRIPT_DIR / "All_Phases_Test"
)

OUT_ROOT.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(CSV)

PHASES = [
    "home",
    "gripper_opening",
    "pick",
    "pick_delay",
    "gripper_closing",
    "lift",
    "place",
    "retract",
    "return_home",
]

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


# --------------------------------------------------
# Generate one Popper dataset for every phase
# --------------------------------------------------

for target_phase in PHASES:

    target_name = f"phase_{target_phase}"

    OUT = OUT_ROOT / target_phase
    OUT.mkdir(parents=True, exist_ok=True)

    bk = [
        f"% Qualitative BK for target phase: {target_phase}",
        "% sN describes the transition from row N to row N+1.",
        "% Phase labels are NOT included in BK.",
        "",
    ]

    pos_examples = []
    neg_examples = []

    for i in range(len(df) - 1):

        # Never create a state across a phase boundary
        if df.loc[i, "phase"] != df.loc[i + 1, "phase"]:
            continue

        state_id = f"s{i}"

        # ------------------------------------------
        # Convert all 18 raw signals to qualitative
        # predicates
        # ------------------------------------------

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

        # ------------------------------------------
        # Examples
        # ------------------------------------------

        if df.loc[i, "phase"] == target_phase:

            pos_examples.append(
                f"pos({target_name}({state_id}))."
            )

        else:

            neg_examples.append(
                f"neg({target_name}({state_id}))."
            )

    # ----------------------------------------------
    # bk.pl
    # ----------------------------------------------

    (OUT / "bk.pl").write_text(
        "\n".join(bk) + "\n"
    )

    # ----------------------------------------------
    # exs.pl
    # ----------------------------------------------

    exs = [
        f"% Target phase: {target_phase}",
        f"% Positive = {target_phase}",
        "% Negative = every other phase",
        "",
    ]

    exs += pos_examples
    exs += [""]
    exs += neg_examples
    exs += [""]

    (OUT / "exs.pl").write_text(
        "\n".join(exs)
    )

    # ----------------------------------------------
    # bias.pl
    # ----------------------------------------------

    bias = [
        "max_vars(1).",
        "max_body(4).",
        "max_clauses(3).",
        "",
        f"head_pred({target_name},1).",
    ]

    for signal in signals:

        for q in (
            "increases",
            "decreases",
            "constant",
        ):

            bias.append(
                f"body_pred({pred_name(signal, q)},1)."
            )

    bias.append("")

    bias.append(
        f"type({target_name},(state,))."
    )

    for signal in signals:

        for q in (
            "increases",
            "decreases",
            "constant",
        ):

            bias.append(
                f"type({pred_name(signal, q)},(state,))."
            )

    bias.append("")

    bias.append(
        f"direction({target_name},(in,))."
    )

    for signal in signals:

        for q in (
            "increases",
            "decreases",
            "constant",
        ):

            bias.append(
                f"direction({pred_name(signal, q)},(in,))."
            )

    (OUT / "bias.pl").write_text(
        "\n".join(bias) + "\n"
    )

    print(
        f"{target_phase:18s} "
        f"positive={len(pos_examples):3d} "
        f"negative={len(neg_examples):3d}"
    )


print()
print(f"Created all Popper datasets in: {OUT_ROOT}")