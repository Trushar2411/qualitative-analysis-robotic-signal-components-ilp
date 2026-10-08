#!/usr/bin/env python3
"""Extract Franka arm/finger signals and simulation-relative elapsed time.

Reads dt and decimation from the source HDF5 env_args metadata. No absolute
wall-clock timestamps are claimed. The mapping assumes each CSV row is one
control step (as is typical for these exported demonstrations).
"""

import argparse
import json
from pathlib import Path
import h5py
import numpy as np
import pandas as pd

COLUMN_MAP = {}
for i in range(7):
    COLUMN_MAP[f"obs_joint_pos_{i}"] = f"joint_{i+1}_position"
    COLUMN_MAP[f"obs_joint_vel_{i}"] = f"joint_{i+1}_velocity"
for i in range(2):
    COLUMN_MAP[f"obs_joint_pos_{i+7}"] = f"finger_{i+1}_position"
    COLUMN_MAP[f"obs_joint_vel_{i+7}"] = f"finger_{i+1}_velocity"


def get_interval(hdf5_path):
    with h5py.File(hdf5_path, "r") as f:
        meta = json.loads(f["data"].attrs["env_args"])
    sim_args = meta["sim_args"]
    return float(sim_args["dt"]) * int(sim_args["decimation"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Converted CSV or folder of CSVs")
    parser.add_argument(
        "--hdf5",
        type=Path,
        default=None,
        help="Original HDF5 file containing timing metadata",
    )
    parser.add_argument(
        "--dt",
        type=float,
        default=None,
        help="Known seconds between CSV rows (alternative to --hdf5)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "robot_joints",
    )
    args = parser.parse_args()
    if args.hdf5 is None and args.dt is None:
        parser.error(
            "Provide --hdf5 ORIGINAL.hdf5 or --dt SECONDS; time cannot be recovered from CSV alone"
        )
    interval = args.dt if args.dt is not None else get_interval(args.hdf5)
    if not np.isfinite(interval) or interval <= 0:
        parser.error("Sampling interval must be a positive finite number")
    paths = sorted(args.input.glob("*.csv")) if args.input.is_dir() else [args.input]
    if not paths:
        parser.error("No CSV files found")
    args.output.mkdir(parents=True, exist_ok=True)
    failures = []
    for path in paths:
        df = pd.read_csv(path)
        missing = sorted(set(COLUMN_MAP) - set(df.columns))
        if missing:
            print(f"SKIP {path.name}: missing {missing}")
            failures.append(path.name)
            continue
        result = df[list(COLUMN_MAP)].rename(columns=COLUMN_MAP).copy()
        result.insert(0, "time_seconds", np.arange(len(result)) * interval)
        out = args.output / path.name
        result.to_csv(out, index=False)
        duration = (len(result) - 1) * interval if len(result) else 0
        print(
            f"{path.name} -> {out}: {len(result)} samples; elapsed span {duration:.3f} s"
        )
    print(f"Assumed interval per CSV row: {interval:.9f} s")
    if failures:
        raise SystemExit(
            f"Joint extraction failed for {len(failures)} file(s): {failures}"
        )


if __name__ == "__main__":
    main()
