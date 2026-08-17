from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]

RAW_DATA_DIR = REPO_ROOT / "Raw data"
PROCESSED_DATA_DIR = REPO_ROOT / "Processed data"

RAW_RUN_NAME = "pick_place_No_object_1"
FULL_MOTION_CSV = "full_motion_joint_states.csv"


def build_joint_dataframe(
    raw_df: pd.DataFrame,
    joint_number: int,
) -> pd.DataFrame:

    prefix = f"joint{joint_number}"

    required_columns = [
        "bag_time_ns",
        "bag_time_sec",
        "header_stamp_sec",
        f"{prefix}_position",
        f"{prefix}_velocity",
        f"{prefix}_effort",
        "phase",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in raw_df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing columns for {prefix}: "
            f"{', '.join(missing_columns)}"
        )

    joint_df = raw_df[required_columns].copy()

    joint_df.insert(0, "joint", prefix)

    joint_df = joint_df.rename(
        columns={
            f"{prefix}_position": "position",
            f"{prefix}_velocity": "velocity",
            f"{prefix}_effort": "effort",
        }
    )

    return joint_df


def create_processed_run(
    raw_run_dir: Path,
    processed_data_dir: Path = PROCESSED_DATA_DIR,
) -> Path:

    source_csv = raw_run_dir / "csv" / FULL_MOTION_CSV

    if not source_csv.exists():
        raise FileNotFoundError(
            f"Raw full-motion CSV not found: {source_csv}"
        )

    print(f"Reading: {source_csv}")

    raw_df = pd.read_csv(source_csv)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    output_dir = (
        processed_data_dir
        / f"{raw_run_dir.name}_processed_{timestamp}"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=False,
    )

    for joint_number in range(1, 7):

        joint_df = build_joint_dataframe(
            raw_df,
            joint_number,
        )

        output_csv = (
            output_dir
            / f"joint_{joint_number}.csv"
        )

        joint_df.to_csv(
            output_csv,
            index=False,
        )

        print(f"Created: {output_csv.name}")

    return output_dir


def main() -> None:

    raw_run_dir = (
        RAW_DATA_DIR
        / RAW_RUN_NAME
    ).resolve()

    if not raw_run_dir.exists():
        raise FileNotFoundError(
            f"Raw run folder not found: {raw_run_dir}"
        )

    output_dir = create_processed_run(
        raw_run_dir
    )

    print()
    print(f"Raw run used: {raw_run_dir}")
    print(
        f"Processed joint CSV files saved to: "
        f"{output_dir}"
    )


if __name__ == "__main__":
    main()