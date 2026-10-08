#!/usr/bin/env python3
"""Visual replay of Franka HDF5 demonstrations on Windows/Linux.

Ubuntu setup: bash setup_ubuntu.sh
Run: python franka_replay.py source_demos.hdf5 --demo 0

This uses recorded positions, without physics integration. Cube/box geometry
and orientations are approximate. Default column order is arm joints 1..7,
then finger joints 1..2; verify against the generating environment if available.
Default playback rate 30 Hz is inferred from dt=1/60 and decimation=2 in the
current dataset card. --fps changes it, --speed changes playback speed only.
"""
import argparse
from pathlib import Path
import re
import sys
import time

import h5py
import numpy as np

JOINT_NAMES = [f"panda_joint{i}" for i in range(1, 8)] + [
    "panda_finger_joint1", "panda_finger_joint2"]


def natural_key(name):
    return [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", name)]


def read_demo(path, selected, order):
    with h5py.File(path, "r") as f:
        if "data" not in f:
            raise ValueError("Expected a data/ group. Run --inspect to check this file.")
        names = sorted([k for k in f["data"] if isinstance(f["data"][k], h5py.Group)], key=natural_key)
        if selected.isdigit():
            index = int(selected)
            if index >= len(names):
                raise ValueError(f"Demo index out of range. File contains {len(names)} demos.")
            selected = names[index]
        if selected not in names:
            raise ValueError(f"Unknown demo {selected!r}. Run --list.")
        g = f[f"data/{selected}"]
        arrays = {}
        for name, width in [("joint_pos", 9), ("cube_pos", 3), ("box_pos", 3)]:
            key = f"obs/{name}"
            if key not in g:
                raise ValueError(f"Missing data/{selected}/{key}. Run --inspect.")
            a = np.asarray(g[key], dtype=float)
            if a.ndim != 2 or a.shape[1] != width or not len(a):
                raise ValueError(f"{key}: expected nonempty (T, {width}), found {a.shape}.")
            if not np.isfinite(a).all():
                raise ValueError(f"{key} contains NaN or infinite values.")
            arrays[name] = a
        lengths = {len(a) for a in arrays.values()}
        if len(lengths) != 1:
            raise ValueError(f"Observation lengths differ: {lengths}.")
        # Camera datasets are deliberately not loaded into memory.
        print(f"Loaded {selected}: {len(arrays['joint_pos'])} recorded frames.")
        print("Column order:", ", ".join(order))
        print("Cube and box positions use the robot base frame.")
        return selected, arrays


def inspect_file(path, list_only=False):
    with h5py.File(path, "r") as f:
        print("Root attributes:", dict(f.attrs))
        if "data" not in f:
            print("Top-level keys:", list(f.keys()))
            return
        names = sorted(f["data"].keys(), key=natural_key)
        print(f"{len(names)} demos:", ", ".join(names))
        print("data attributes:", dict(f["data"].attrs))
        if names and not list_only:
            g = f["data"][names[0]]
            print(f"Schema of {names[0]}:")
            def describe(name, obj):
                if isinstance(obj, h5py.Dataset):
                    print(f"  {name}: {obj.shape} {obj.dtype}")
            g.visititems(describe)
            print("demo attributes:", dict(g.attrs))


def run_replay(args, name, arrays, order):
    import pybullet as p
    import pybullet_data
    client = p.connect(p.DIRECT if args.headless else p.GUI)
    if client < 0:
        raise RuntimeError("Could not open PyBullet. Try --headless to check the data.")
    try:
        p.setAdditionalSearchPath(pybullet_data.getDataPath())
        p.setGravity(0, 0, 0)
        p.setRealTimeSimulation(0)
        robot = p.loadURDF("franka_panda/panda.urdf", useFixedBase=True)
        joint_ids = {p.getJointInfo(robot, i)[1].decode(): i
                     for i in range(p.getNumJoints(robot))}
        for joint in order:
            if joint not in joint_ids:
                raise ValueError(f"Robot model has no joint named {joint}.")
        print("Replay sets recorded joint positions directly; no grasp/contact test is performed.")
        print("Scene dimensions/orientations are approximate, not original Isaac Lab assets.")
        print(f"Playback: {args.fps:g} recorded frames/s; speed {args.speed:g}x.")

        def block(half, xyz, rgba):
            visual = p.createVisualShape(p.GEOM_BOX, halfExtents=half, rgbaColor=rgba)
            return p.createMultiBody(baseMass=0, baseVisualShapeIndex=visual,
                                     basePosition=xyz)

        # Table top in observation coordinates, configurable if a file differs.
        block([0.6, 0.5, 0.025], [0.45, 0, args.table_z - 0.025], [0.65, 0.60, 0.52, 1])
        cube = block([0.02]*3, arrays["cube_pos"][0].tolist(), [0.9, 0.25, 0.15, 1])
        # Open box: visual-only compound shape centered at recorded box_pos.
        half = [[0.10,0.10,0.005], [0.005,0.10,0.04], [0.005,0.10,0.04],
                [0.10,0.005,0.04], [0.10,0.005,0.04]]
        offsets = [[0,0,-0.04], [-0.10,0,0], [0.10,0,0], [0,-0.10,0], [0,0.10,0]]
        vis = p.createVisualShapeArray(shapeTypes=[p.GEOM_BOX]*5, halfExtents=half,
                visualFramePositions=offsets, rgbaColors=[[0.2,0.45,0.75,1]]*5)
        box = p.createMultiBody(baseMass=0, baseVisualShapeIndex=vis,
                                basePosition=arrays["box_pos"][0].tolist())
        if not args.headless:
            p.configureDebugVisualizer(p.COV_ENABLE_GUI, 0)
            p.resetDebugVisualizerCamera(1.45, 45, -30, [0.4, 0, 0.25])
            print("Window controls: SPACE pause/resume, R restart, arrows step while paused, Q quit.")
            print("You can also stop with Ctrl+C in the terminal.")

        total = len(arrays["joint_pos"])
        limit = min(total, args.frames) if args.frames else total
        frame, paused, text_id = 0, False, -1
        while p.isConnected():
            if not args.headless:
                keys = p.getKeyboardEvents()
                pressed = lambda key: bool(keys.get(key, 0) & p.KEY_WAS_TRIGGERED)
                if pressed(ord('q')):
                    break
                if pressed(ord(' ')):
                    paused = not paused
                if pressed(ord('r')):
                    frame = 0
                if paused:
                    if pressed(p.B3G_LEFT_ARROW):
                        frame = max(0, frame - 1)
                    if pressed(p.B3G_RIGHT_ARROW):
                        frame = min(limit - 1, frame + 1)
            start = time.perf_counter()
            for column, joint in enumerate(order):
                p.resetJointState(robot, joint_ids[joint], float(arrays["joint_pos"][frame, column]))
            p.resetBasePositionAndOrientation(cube, arrays["cube_pos"][frame].tolist(), [0,0,0,1])
            p.resetBasePositionAndOrientation(box, arrays["box_pos"][frame].tolist(), [0,0,0,1])
            if not args.headless:
                text_id = p.addUserDebugText(
                    f"{name} | frame {frame+1}/{total} | t~{frame/args.fps:.2f}s | "
                    + ("PAUSED" if paused else "recorded replay"),
                    [0.05, 0, 0.9], textColorRGB=[0,0,0], textSize=1.2,
                    replaceItemUniqueId=text_id)
            # No stepSimulation: it would change the recorded configuration.
            if not paused:
                frame += 1
                if frame >= limit:
                    if args.headless or args.once:
                        print(f"Completed {limit} frames.")
                        break
                    frame = 0
            if not args.headless:
                delay = max(0, 1 / (args.fps * args.speed) - (time.perf_counter() - start))
                time.sleep(delay)
    finally:
        if p.isConnected():
            p.disconnect()


def main():
    parser = argparse.ArgumentParser(description="Replay Franka HDF5 observations in a 3D viewer.")
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--demo", default="0", help="Demo index or name, e.g. 0 or demo_0")
    parser.add_argument("--list", action="store_true", help="List demos, then exit")
    parser.add_argument("--inspect", action="store_true", help="Print file schema and metadata, then exit")
    parser.add_argument("--fps", type=float, default=30, help="Recorded rate; default 30 Hz inferred from dataset card")
    parser.add_argument("--speed", type=float, default=1, help="Playback multiplier, e.g. 0.5")
    parser.add_argument("--table-z", type=float, default=0, help="Approximate table surface height in base frame")
    parser.add_argument("--once", action="store_true", help="Play once instead of looping")
    parser.add_argument("--headless", action="store_true", help="Validate replay without a window, no delays")
    parser.add_argument("--frames", type=int, help="Limit number of frames")
    parser.add_argument("--joint-order", help="Comma-separated joint names in HDF5 column order")
    args = parser.parse_args()
    if not args.dataset.is_file():
        parser.error(f"File not found: {args.dataset}. Supply the full HDF5 path in quotes.")
    if args.fps <= 0 or args.speed <= 0 or (args.frames is not None and args.frames <= 0):
        parser.error("fps, speed and frames must be positive.")
    order = args.joint_order.split(',') if args.joint_order else JOINT_NAMES
    order = [x.strip() for x in order]
    if len(order) != 9 or set(order) != set(JOINT_NAMES):
        parser.error("joint-order must contain each of the seven arm and two finger joint names once.")
    try:
        if args.list or args.inspect:
            inspect_file(args.dataset, list_only=args.list and not args.inspect)
        else:
            name, arrays = read_demo(args.dataset, args.demo, order)
            run_replay(args, name, arrays, order)
    except KeyboardInterrupt:
        print("Stopped.")
    except (OSError, ValueError, RuntimeError, ImportError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
