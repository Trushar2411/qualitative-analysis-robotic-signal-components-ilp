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
        self.arm.set_mode(0)
        self.arm.set_state(state=0)

#        ####
#        # Arm 2
#        ####
#        self.arm2 = XArmAPI('192.168.1.209', do_not_open=True)
#        self.arm2.register_error_warn_changed_callback(handle_err_warn_changed)
#        self.arm2.connect()
#
#        # enable motion
#        self.arm2.motion_enable(enable=True)
#        self.arm2.set_mode(0)
#        self.arm2.set_state(state=0)
#
#        self.arm1_moving = False
#        self.arm2_moving = False

    def move_arms_sync(self):
        arm1_thread = threading.Thread(target=self.move_arm1)
        # arm2_thread = threading.Thread(target=self.move_arm2)
        self.arm1_moving = True
        # self.arm2_moving = True
        arm1_thread.start()
        # time.sleep(5.)
        # arm2_thread.start()
        while self.arm1_moving:
            time.sleep(0.1)

    def move_home(self, arm):
        arm.set_position(187.5, 16.9, 218, 179.9, 0, -1.4)

    def move_arm1(self):
        self.arm1_moving = True
        print('Moving arm 1')
        self.move_home(self.arm)
        self.arm.set_servo_angle(angle=[-180, -53.6, 4.2, 0., 49.4, -357.])
        self.move_home(self.arm)
        self.arm1_moving = False

    def move_arm2(self):
        self.arm2_moving = True 
        print('Moving arm 2')
        self.move_home(self.arm2)
        self.arm2.set_servo_angle(angle=[-180, -53.6, 4.2, 0., 49.4, 0.])
        self.move_home(self.arm2)
        self.arm2_moving = False

    def disconnect_arms(self):
        self.arm.disconnect()
        # self.arm2.disconnect()

if __name__ == '__main__':
    jessie = Jessie()
    jessie.move_arms_sync()
    jessie.disconnect_arms()
