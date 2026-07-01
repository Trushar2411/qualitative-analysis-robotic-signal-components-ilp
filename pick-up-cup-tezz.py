#!/usr/bin/env python3

import os
import sys
import time
import signal
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(__file__), "../../.."))

from xarm.wrapper import XArmAPI
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message


ROBOT_IP = "192.168.1.204"

# ROS topic to record
TOPICS_TO_RECORD = ["/joint_states"]

# Output folder
BASE_OUTPUT_DIR = Path("pick_place_recordings")

# Joint positions
HOME_POSITION = [0, -53.6, 4.3, 0, 49.4, 0]
PICK_POSITION = [0, 33, -40, 0, -80, 0]
LIFT_POSITION = [-22, 25, -72, 0, -45, 0]
PLACE_POSITION = [-21, 45, -67, 0, -67, 0]
RETRACT_POSITION = [-21, 16, -67, 0, -42, 0]

# Gripper positions
GRIPPER_OPEN = 700
GRIPPER_CLOSE = 520


def handle_err_warn_changed(item):
    print(f"ErrorCode: {item['error_code']}, WarnCode: {item['warn_code']}")


class Jessie:
    def __init__(self):
        self.arm = XArmAPI(ROBOT_IP, do_not_open=True)
        self.arm.register_error_warn_changed_callback(handle_err_warn_changed)

        self.output_dir = self.create_output_folder()
        self.bag_dir = self.output_dir / "rosbag"
        self.csv_dir = self.output_dir / "csv"
        self.csv_dir.mkdir(parents=True, exist_ok=True)

        self.bag_process = None
        self.phase_log = []

        self.connect_robot()

    def create_output_folder(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder = BASE_OUTPUT_DIR / f"pick_place_{timestamp}"
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def connect_robot(self):
        print(f"Connecting to robot at {ROBOT_IP}")

        self.arm.connect()
        self.arm.motion_enable(enable=True)
        self.arm.set_mode(0)
        self.arm.set_state(0)

        time.sleep(1)
        print("Robot is ready")

    def start_rosbag_recording(self):
        print("Starting rosbag recording...")

        cmd = [
            "ros2",
            "bag",
            "record",
            "-o",
            str(self.bag_dir),
            *TOPICS_TO_RECORD,
        ]

        self.bag_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid,
        )

        time.sleep(2)
        print(f"Recording bag to: {self.bag_dir}")

    def stop_rosbag_recording(self):
        if self.bag_process is None:
            return

        print("Stopping rosbag recording...")

        os.killpg(os.getpgid(self.bag_process.pid), signal.SIGINT)
        self.bag_process.wait()

        time.sleep(2)
        print("Rosbag recording stopped")

    def mark_phase_start(self, phase_name):
        start_time_ns = time.time_ns()
        self.phase_log.append(
            {
                "phase": phase_name,
                "start_time_ns": start_time_ns,
                "end_time_ns": None,
            }
        )
        print(f"Started phase: {phase_name}")

    def mark_phase_end(self):
        if self.phase_log:
            self.phase_log[-1]["end_time_ns"] = time.time_ns()
            print(f"Ended phase: {self.phase_log[-1]['phase']}")

    def move_to(self, name, position, delay=1):
        self.mark_phase_start(name)

        print(f"Moving to {name}")

        self.arm.set_servo_angle(
            angle=position,
            wait=True,
        )

        time.sleep(delay)

        self.mark_phase_end()

    def set_gripper(self, name, position, delay=1):
        print(f"{name}: gripper position {position}")

        self.arm.set_gripper_position(
            position,
            wait=True,
        )

        time.sleep(delay)

    def pick_and_place(self):
        self.start_rosbag_recording()

        try:
            self.move_to("home", HOME_POSITION)

            self.set_gripper("Opening gripper", GRIPPER_OPEN)

            self.move_to("pick", PICK_POSITION, delay=3)

            self.set_gripper("Closing gripper", GRIPPER_CLOSE)

            self.move_to("lift", LIFT_POSITION)

            self.move_to("place", PLACE_POSITION)

            self.set_gripper("Opening gripper", GRIPPER_OPEN)

            self.move_to("retract", RETRACT_POSITION)

            # Final home movement is recorded in the full CSV,
            # but not split as a separate phase.
            print("Moving back to home after retract")
            self.arm.set_servo_angle(
                angle=HOME_POSITION,
                wait=True,
            )

            time.sleep(1)

            print("Pick and place movement finished")

        finally:
            self.stop_rosbag_recording()
            self.save_phase_log()
            self.convert_bag_to_csv()

    def save_phase_log(self):
        phase_file = self.csv_dir / "phase_timestamps.csv"
        pd.DataFrame(self.phase_log).to_csv(phase_file, index=False)
        print(f"Saved phase timestamps to: {phase_file}")

    def convert_bag_to_csv(self):
        print("Converting rosbag to CSV...")

        db_files = sorted(self.bag_dir.glob("*.db3"))

        if not db_files:
            print("No .db3 rosbag file found")
            return

        all_rows = []

        for db_file in db_files:
            print(f"Reading bag database: {db_file}")

            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()

            cursor.execute("SELECT id, name, type FROM topics")
            topics = cursor.fetchall()

            topic_info = {
                topic_id: {
                    "name": name,
                    "type": msg_type,
                    "msg_class": get_message(msg_type),
                }
                for topic_id, name, msg_type in topics
            }

            cursor.execute("SELECT topic_id, timestamp, data FROM messages ORDER BY timestamp")

            for topic_id, timestamp, data in cursor.fetchall():
                topic_name = topic_info[topic_id]["name"]

                if topic_name != "/joint_states":
                    continue

                msg_type = topic_info[topic_id]["msg_class"]
                msg = deserialize_message(data, msg_type)

                row = {
                    "bag_time_ns": timestamp,
                    "bag_time_sec": timestamp * 1e-9,
                    "header_stamp_sec": msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9,
                }

                for i, joint_name in enumerate(msg.name):
                    row[f"{joint_name}_position"] = (
                        msg.position[i] if i < len(msg.position) else None
                    )
                    row[f"{joint_name}_velocity"] = (
                        msg.velocity[i] if i < len(msg.velocity) else None
                    )
                    row[f"{joint_name}_effort"] = (
                        msg.effort[i] if i < len(msg.effort) else None
                    )

                all_rows.append(row)

            conn.close()

        if not all_rows:
            print("No /joint_states data found in bag")
            return

        df = pd.DataFrame(all_rows)
        df = df.sort_values("bag_time_ns").reset_index(drop=True)

        df["phase"] = "unlabelled"

        for phase in self.phase_log:
            phase_name = phase["phase"]
            start = phase["start_time_ns"]
            end = phase["end_time_ns"]

            if end is None:
                continue

            mask = (df["bag_time_ns"] >= start) & (df["bag_time_ns"] <= end)
            df.loc[mask, "phase"] = phase_name

        full_csv = self.csv_dir / "full_motion_joint_states.csv"
        df.to_csv(full_csv, index=False)
        print(f"Saved full CSV to: {full_csv}")

        for phase_name in ["home", "pick", "lift", "place", "retract"]:
            phase_df = df[df["phase"] == phase_name]

            phase_csv = self.csv_dir / f"{phase_name}_joint_states.csv"
            phase_df.to_csv(phase_csv, index=False)

            print(f"Saved {phase_name} CSV to: {phase_csv}")

    def disconnect_robot(self):
        print("Disconnecting robot")
        self.arm.disconnect()


if __name__ == "__main__":
    jessie = Jessie()

    try:
        jessie.pick_and_place()
    finally:
        jessie.disconnect_robot()