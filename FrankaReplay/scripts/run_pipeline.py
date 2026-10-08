#!/usr/bin/env python3
"""Convert HDF5 demonstrations, infer phases, and calculate PLA in a fresh run."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument(
        "--demo",
        action="append",
        help="Exact demonstration name; repeat to select several",
    )
    parser.add_argument(
        "--output", type=Path, help="New output directory; must not exist"
    )
    parser.add_argument(
        "--dt",
        type=float,
        help="Known control interval in seconds; otherwise read HDF5 metadata",
    )
    parser.add_argument("--window", type=int, default=5)
    parser.add_argument("--step", type=int, default=5)
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="Omit PLA plots; segmentation plots are retained",
    )
    args = parser.parse_args()
    dataset = args.dataset.expanduser().resolve()
    if not dataset.is_file():
        parser.error(f"Dataset not found: {dataset}")
    if args.window < 2 or args.step < 1:
        parser.error("Require --window >= 2 and --step >= 1")
    scripts = Path(__file__).resolve().parent
    output = (
        (
            args.output
            or scripts.parent
            / "outputs"
            / "runs"
            / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
        )
        .expanduser()
        .resolve()
    )
    if output.exists():
        parser.error(f"Output already exists: {output}; choose a fresh directory")
    output.mkdir(parents=True)
    timing = ["--dt", str(args.dt)] if args.dt is not None else ["--hdf5", str(dataset)]
    stages = [
        [
            "hdf5_csv.py",
            str(dataset),
            "--output",
            str(output / "converted"),
            *[item for demo in (args.demo or []) for item in ("--demo", demo)],
        ],
        [
            "extract_robot_joints.py",
            str(output / "converted"),
            *timing,
            "--output",
            str(output / "robot_joints"),
        ],
        [
            "segment_franka_phases_reduced.py",
            str(output / "robot_joints"),
            "--output",
            str(output / "segmented"),
        ],
        [
            "pla_franka_batch.py",
            str(output / "segmented"),
            "--output",
            str(output / "PLA"),
            "--window",
            str(args.window),
            "--step",
            str(args.step),
            *(["--no-plots"] if args.no_plots else []),
        ],
    ]
    manifest = {
        "dataset": str(dataset),
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "demonstrations": args.demo,
        "dt_override": args.dt,
        "window": args.window,
        "step": args.step,
        "status": "running",
        "commands": stages,
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    try:
        for stage in stages:
            subprocess.run(
                [sys.executable, str(scripts / stage[0]), *stage[1:]],
                check=True,
                env={**os.environ, "MPLBACKEND": "Agg"},
            )
    except subprocess.CalledProcessError as exc:
        manifest["status"] = "failed"
        manifest["failed_command"] = exc.cmd
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        print(
            f"Pipeline stopped; partial outputs and manifest: {output}", file=sys.stderr
        )
        return exc.returncode
    manifest["status"] = "complete"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Pipeline complete: {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
