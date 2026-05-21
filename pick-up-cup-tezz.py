#!/usr/bin/env python3
# Software License Agreement (BSD License)
#
# Copyright (c) 2019, UFACTORY, Inc.
# All rights reserved.
#
# Based on Vinman <vinman.wen@ufactory.cc> <vinman.cub@gmail.com>

import os
import sys
import time
import threading
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

from xarm.wrapper import XArmAPI

def handle_err_warn_changed(item):
    print('ErrorCode: {}, WarnCode: {}'.format(item['error_code'], item['warn_code']))

class Jessie(object):
    def __init__(self):
        ####
        # Arm 1
        ####
        self.arm = XArmAPI('192.168.1.204', do_not_open=True)
        self.arm.register_error_warn_changed_callback(handle_err_warn_changed)
        self.arm.connect()

        # enable motion
        self.arm.motion_enable(enable=True)
        # set mode: position control mode
        self.arm.set_mode(0)
        # set state: sport state
        self.arm.set_state(state=0)

        self.arm1_moving = False

    def move_arms_sync(self):
        arm1_thread = threading.Thread(target=self.move_arm1_traj1)
        self.arm1_moving = True
        arm1_thread.start()
        while self.arm1_moving: #or self.arm2_moving
            time.sleep(0.1)

    def move_arm1_traj1(self):
        self.arm1_moving = True
        print('Moving arm 1')
        # self.arm.set_servo_angle(angle=[-180, -47.7, -42.9, 0.0, 90, -355]) # Common Start pose
        # time.sleep(0.6)
        gripper_action_code = self.arm.set_gripper_position(790, wait=True)
        print(f'Gripper action code={gripper_action_code}')
        time.sleep(2.0)
        self.arm.set_servo_angle(angle=[-180, 2.4, -93.3, 0.0, 77.5, -355])
        time.sleep(3.0)
        self.arm.set_servo_angle(angle=[-180, 11.4, -93.3, 0.6, 77, -355])
        time.sleep(3.0)
        gripper_action_code = self.arm.set_gripper_position(100, wait=True)
        print(f'Gripper action code={gripper_action_code}')
        time.sleep(3.0)
        self.arm.set_servo_angle(angle=[-180, 2.4, -93.3, 0.0, 77.5, -355])
        time.sleep(0.5)
        self.arm1_moving = False

    def disconnect_arms(self):
        self.arm.disconnect()

if __name__ == '__main__':
    jessie = Jessie()
    jessie.move_arms_sync()
    jessie.disconnect_arms()
