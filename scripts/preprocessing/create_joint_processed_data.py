from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA_DIR = REPO_ROOT / "Raw data"
PROCESSED_DATA_DIR = REPO_ROOT / "Processed data"
FULL_MOTION_CSV = "full_motion_joint_states.csv"


def find_latest_raw_run(raw_data_dir: Path = RAW_DATA_DIR) -> Path:
    if not raw_data_dir.exists():
        raise FileNotFoundError(f"Raw data folder not found: {raw_data_dir}")

    runs = [
        path
        for path in raw_data_dir.iterdir()
        if path.is_dir() and (path / "csv" / FULL_MOTION_CSV).exists()
    ]

    if not runs:
        raise FileNotFoundError(
            f"No raw runs found in {raw_data_dir} containing csv/{FULL_MOTION_CSV}"
        )

    return max(runs, key=lambda path: path.stat().st_mtime)


def build_joint_dataframe(raw_df: pd.DataFrame, joint_number: int) -> pd.DataFrame:
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
    missing_columns = [column for column in required_columns if column not in raw_df.columns]

    if missing_columns:
        raise ValueError(
            f"Missing columns for {prefix}: {', '.join(missing_columns)}"
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


def create_processed_run(raw_run_dir: Path, processed_data_dir: Path = PROCESSED_DATA_DIR) -> Path:
    source_csv = raw_run_dir / "csv" / FULL_MOTION_CSV
    if not source_csv.exists():
        raise FileNotFoundError(f"Raw full-motion CSV not found: {source_csv}")

    raw_df = pd.read_csv(source_csv)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = processed_data_dir / f"{raw_run_dir.name}_processed_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=False)

    for joint_number in range(1, 7):
        joint_df = build_joint_dataframe(raw_df, joint_number)
        output_csv = output_dir / f"joint_{joint_number}.csv"
        joint_df.to_csv(output_csv, index=False)

    return output_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create per-joint processed CSV files from a raw pick-and-place run."
    )
    parser.add_argument(
        "--raw-run",
        type=Path,
        default=None,
        help=(
            "Path to a run folder inside Raw data. "
            "Defaults to the latest raw run containing csv/full_motion_joint_states.csv."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raw_run_dir = args.raw_run if args.raw_run is not None else find_latest_raw_run()
    raw_run_dir = raw_run_dir.resolve()

    output_dir = create_processed_run(raw_run_dir)
    print(f"Raw run used: {raw_run_dir}")
    print(f"Processed joint CSV files saved to: {output_dir}")


if __name__ == "__main__":
    main()
