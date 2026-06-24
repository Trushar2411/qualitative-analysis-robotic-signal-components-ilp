#!/usr/bin/env python3

import rclpy
import time
import subprocess
import signal
import os
from datetime import datetime

from rclpy.node import Node
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint


HOME_POSITION = [0, -53.6, 4.3, 0, 49.4, 0]
PICK_POSITION = [0, 33, -40, 0, -80, 0]
LIFT_POSITION = [-22, 25, -72, 0, -45, 0]
PLACE_POSITION = [-21, 45, -67, 0, -67, 0]
RETRACT_POSITION = [-21, 16, -67, 0, -42, 0]

GRIPPER_OPEN = 0.85
GRIPPER_CLOSE = 0.25


def deg_to_rad(joints):
    return [j * 3.14159265359 / 180.0 for j in joints]


class JessieSim(Node):
    def __init__(self):
        super().__init__("jessie_sim_pick_place")

        self.arm_pub = self.create_publisher(
            JointTrajectory,
            "/xarm6_traj_controller/joint_trajectory",
            10
        )

        self.gripper_pub = self.create_publisher(
            JointTrajectory,
            "/xarm_gripper_traj_controller/joint_trajectory",
            10
        )

        self.arm_joint_names = [
            "joint1",
            "joint2",
            "joint3",
            "joint4",
            "joint5",
            "joint6"
        ]

        self.gripper_joint_names = ["drive_joint"]

        time.sleep(2)

    def move_to(self, name, position, duration=3.0):
        self.get_logger().info(f"Moving to {name}")

        traj = JointTrajectory()
        traj.joint_names = self.arm_joint_names

        point = JointTrajectoryPoint()
        point.positions = deg_to_rad(position)
        point.time_from_start.sec = int(duration)

        traj.points.append(point)
        self.arm_pub.publish(traj)

        time.sleep(duration + 1)

    def set_gripper(self, name, position, duration=1.5):
        self.get_logger().info(f"{name}: {position}")

        traj = JointTrajectory()
        traj.joint_names = self.gripper_joint_names

        point = JointTrajectoryPoint()
        point.positions = [position]
        point.time_from_start.sec = int(duration)

        traj.points.append(point)
        self.gripper_pub.publish(traj)

        time.sleep(duration + 1)

    def pick_and_place(self):
        self.move_to("home position", HOME_POSITION)

        self.set_gripper("Opening gripper", GRIPPER_OPEN)

        self.move_to("pick position", PICK_POSITION)

        self.set_gripper("Closing gripper", GRIPPER_CLOSE)

        self.move_to("lift position", LIFT_POSITION)

        self.move_to("place position", PLACE_POSITION)

        self.set_gripper("Opening gripper", GRIPPER_OPEN)

        self.move_to("retract position", RETRACT_POSITION)

        self.move_to("home position", HOME_POSITION)

        self.get_logger().info("Simulated pick and place finished")


def start_rosbag():
    dataset_dir = os.path.expanduser("~/xarm_datasets")
    os.makedirs(dataset_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bag_name = os.path.join(dataset_dir, f"pick_place_dataset_{timestamp}")

    topics = [
        "/joint_states",
        "/dynamic_joint_states",
        "/xarm6_traj_controller/state",
        "/xarm6_traj_controller/joint_trajectory",
        "/xarm_gripper_traj_controller/joint_trajectory"
    ]

    cmd = ["ros2", "bag", "record", "-o", bag_name] + topics

    print(f"Starting rosbag recording: {bag_name}")

    process = subprocess.Popen(
        cmd,
        preexec_fn=os.setsid
    )

    time.sleep(2)
    return process, bag_name


def stop_rosbag(process):
    print("Stopping rosbag recording")

    os.killpg(os.getpgid(process.pid), signal.SIGINT)
    process.wait()

    print("Rosbag saved")


def main():
    rclpy.init()
    node = JessieSim()

    bag_process = None
    bag_name = None

    try:
        bag_process, bag_name = start_rosbag()

        node.pick_and_place()

    finally:
        if bag_process is not None:
            stop_rosbag(bag_process)

        node.destroy_node()
        rclpy.shutdown()

        if bag_name is not None:
            print(f"Dataset saved at: {bag_name}")


if __name__ == "__main__":
    main()