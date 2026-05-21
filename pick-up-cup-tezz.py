# Software License Agreement (BSD License) 
# # Copyright (c) 2019, UFACTORY, Inc. 
# All rights reserved. 
# # Based on Vinman <vinman.wen@ufactory.cc> <vinman.cub@gmail.com>
#!/usr/bin/env python3

import os
import sys
import time

sys.path.append(os.path.join(os.path.dirname(__file__), "../../.."))

from xarm.wrapper import XArmAPI


ROBOT_IP = "192.168.1.204"

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

        self.connect_robot()

    def connect_robot(self):
        print(f"Connecting to robot at {ROBOT_IP}")

        self.arm.connect()
        self.arm.motion_enable(enable=True)
        self.arm.set_mode(0)
        self.arm.set_state(0)

        time.sleep(1)
        print("Robot is ready")

    def move_to(self, name, position, delay=1):
        print(f"Moving to {name}")

        self.arm.set_servo_angle(
            angle=position,
            wait=True
        )

        time.sleep(delay)

    def set_gripper(self, name, position, delay=1):
        print(f"{name}: gripper position {position}")

        self.arm.set_gripper_position(
            position,
            wait=True
        )

        time.sleep(delay)

    def pick_and_place(self):
        self.move_to("home position", HOME_POSITION)

        self.set_gripper("Opening gripper", GRIPPER_OPEN)

        self.move_to("pick position", PICK_POSITION, delay=3)

        self.set_gripper("Closing gripper", GRIPPER_CLOSE)

        self.move_to("lift position", LIFT_POSITION)

        self.move_to("place position", PLACE_POSITION)

        self.set_gripper("Opening gripper", GRIPPER_OPEN)

        self.move_to("retract position", RETRACT_POSITION)

        self.move_to("home position", HOME_POSITION)

        print("Pick and place movement finished")

    def disconnect_robot(self):
        print("Disconnecting robot")
        self.arm.disconnect()


if __name__ == "__main__":
    jessie = Jessie()

    try:
        jessie.pick_and_place()
    finally:
        jessie.disconnect_robot()