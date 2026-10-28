"""Execute the configured sequence and record telemetry with ROS simulation time."""
import csv
from collections import deque
import gc
import json
import math
from datetime import datetime
from pathlib import Path
import time

from ament_index_python.packages import get_package_share_directory
from action_msgs.msg import GoalStatus
from builtin_interfaces.msg import Duration
from control_msgs.action import FollowJointTrajectory
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy, qos_profile_sensor_data
from rclpy.serialization import serialize_message
from rosgraph_msgs.msg import Clock
import rosbag2_py
from sensor_msgs.msg import JointState
from std_msgs.msg import String
from tf2_msgs.msg import TFMessage
from trajectory_msgs.msg import JointTrajectoryPoint
import yaml

from .core import (ALL_JOINTS, ARM_JOINTS, GRIPPER_JOINTS, sdk_to_rad,
                   validate_motion, initial_gripper_target, gripper_settled,
                   joint_target_diagnostics)


class SimulationSequence(Node):
    def __init__(self):
        super().__init__('jessie_sim_sequence')
        if not self.has_parameter('use_sim_time'):
            self.declare_parameter('use_sim_time', True)
        if not self.get_parameter('use_sim_time').value:
            raise RuntimeError('This simulation runner requires use_sim_time:=true.')
        default_config = Path(get_package_share_directory('xarm6_pick_place_sim')) / 'config/motion.yaml'
        self.declare_parameter('config_file', str(default_config))
        self.declare_parameter('output_dir', str(Path.home() / 'xarm_sim_data'))
        self.declare_parameter('cycles', 1)
        self.declare_parameter('startup_timeout', 180.0)
        self.declare_parameter('action_wall_timeout', 180.0)
        self.declare_parameter('settle_tolerance_rad', 0.02)
        self.config_path = Path(self.get_parameter('config_file').value).expanduser()
        with self.config_path.open() as handle:
            self.config = validate_motion(yaml.safe_load(handle))
        self.cycles = int(self.get_parameter('cycles').value)
        if self.cycles < 1:
            raise ValueError('cycles must be a positive integer.')
        self.writer = None
        self.output_dir = None
        self.latest = {}
        self.latest_wall = 0.0
        self.gripper_history = deque(maxlen=512)
        self.phases = []
        self.current_phase = None
        self.joint_messages = 0
        self.cached_description = None
        self.cached_tf_static = []
        self.arm = ActionClient(self, FollowJointTrajectory,
                                '/xarm6_traj_controller/follow_joint_trajectory')
        self.gripper = ActionClient(self, FollowJointTrajectory,
                                    '/xarm_gripper_traj_controller/follow_joint_trajectory')
        self.joint_pub = self.create_publisher(JointState, '/xarm/joint_states', 20)
        self.gripper_pub = self.create_publisher(JointState, '/xarm/gripper_joint_states', 20)
        self.event_pub = self.create_publisher(String, '/xarm_sim/phase_events', 20)
        latched = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE,
                             durability=DurabilityPolicy.TRANSIENT_LOCAL)
        # This topic comes from our Gazebo plugin, including all five mimic joints.
        self.subscriptions_kept = [
            self.create_subscription(JointState, '/xarm_sim/joint_states', self.on_joints,
                                     qos_profile_sensor_data),
            self.create_subscription(Clock, '/clock', self.on_clock, qos_profile_sensor_data),
            self.create_subscription(String, '/robot_description', self.on_description, latched),
            self.create_subscription(TFMessage, '/tf_static', self.on_tf_static, latched),
            self.create_subscription(TFMessage, '/tf', self.on_tf, qos_profile_sensor_data),
        ]

    def now_ns(self):
        return self.get_clock().now().nanoseconds

    def write(self, topic, msg, stamp=None):
        if self.writer is not None:
            timestamp = self.now_ns() if stamp is None else stamp
            if timestamp > 0:
                self.writer.write(topic, serialize_message(msg), timestamp)

    def on_clock(self, msg):
        self.write('/clock', msg, msg.clock.sec * 10**9 + msg.clock.nanosec)

    def on_description(self, msg):
        self.cached_description = msg
        self.write('/robot_description', msg)

    def on_tf_static(self, msg):
        self.cached_tf_static.append(msg)
        self.write('/tf_static', msg)

    def on_tf(self, msg):
        self.write('/tf', msg)

    def on_joints(self, msg):
        self.latest = {name: msg.position[i] for i, name in enumerate(msg.name)
                       if i < len(msg.position)}
        self.latest_wall = time.monotonic()
        header_ns = msg.header.stamp.sec * 10**9 + msg.header.stamp.nanosec
        if self.gripper_history and header_ns <= self.gripper_history[-1][0]:
            self.gripper_history.clear()
        self.gripper_history.append((header_ns, dict(self.latest)))
        # Publish and record the actual Gazebo samples; no inferred mimic values.
        self.joint_pub.publish(msg)
        gripper = JointState()
        gripper.header = msg.header
        selected = [(i, n) for i, n in enumerate(msg.name) if n in GRIPPER_JOINTS]
        gripper.name = [name for _, name in selected]
        for field in ('position', 'velocity', 'effort'):
            values = getattr(msg, field)
            # JointState arrays must either contain every selected joint or be empty.
            setattr(gripper, field, [values[i] for i, _ in selected]
                    if all(i < len(values) for i, _ in selected) else [])
        self.gripper_pub.publish(gripper)
        if self.writer is not None:
            self.joint_messages += 1
            self.write('/xarm/joint_states', msg)
            self.write('/xarm/gripper_joint_states', gripper)

    def pump_until(self, predicate, timeout, description):
        deadline = time.monotonic() + timeout
        while rclpy.ok():
            if predicate():
                return
            if time.monotonic() > deadline:
                raise TimeoutError(description)
            rclpy.spin_once(self, timeout_sec=0.05)
        raise RuntimeError('ROS shutdown interrupted the sequence.')

    def wait_ready(self):
        self.get_logger().info('Waiting for simulation clock, all 12 joints and both controllers...')

        def ready():
            return (self.now_ns() > 0
                    and time.monotonic() - self.latest_wall < 2.0
                    and all(name in self.latest and math.isfinite(self.latest[name])
                            for name in ALL_JOINTS)
                    and self.cached_description is not None
                    and 'gazebo_ros2_control/GazeboSystem' in self.cached_description.data
                    and self.arm.server_is_ready() and self.gripper.server_is_ready())

        self.pump_until(ready, float(self.get_parameter('startup_timeout').value),
                        'Simulation not ready. Check Gazebo, telemetry plugin and controller logs.')

    def open_recording(self):
        base = Path(self.get_parameter('output_dir').value).expanduser().resolve()
        self.output_dir = base / ('pick_place_sim_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
        self.output_dir.mkdir(parents=True, exist_ok=False)
        (self.output_dir / 'csv').mkdir()
        (self.output_dir / 'motion_used.yaml').write_text(yaml.safe_dump(self.config, sort_keys=False))
        self.writer = rosbag2_py.SequentialWriter()
        self.writer.open(
            rosbag2_py.StorageOptions(uri=str(self.output_dir / 'rosbag'), storage_id='sqlite3'),
            rosbag2_py.ConverterOptions(input_serialization_format='cdr', output_serialization_format='cdr'),
        )
        topics = {
            '/xarm/joint_states': 'sensor_msgs/msg/JointState',
            '/xarm/gripper_joint_states': 'sensor_msgs/msg/JointState',
            '/clock': 'rosgraph_msgs/msg/Clock',
            '/xarm_sim/phase_events': 'std_msgs/msg/String',
            '/robot_description': 'std_msgs/msg/String',
            '/tf': 'tf2_msgs/msg/TFMessage', '/tf_static': 'tf2_msgs/msg/TFMessage',
        }
        for name, msg_type in topics.items():
            self.writer.create_topic(rosbag2_py.TopicMetadata(
                name=name, type=msg_type, serialization_format='cdr'))
        if self.cached_description is not None:
            self.write('/robot_description', self.cached_description)
        for msg in self.cached_tf_static:
            self.write('/tf_static', msg)
        self.get_logger().info(f'Recording to {self.output_dir}')

    def sim_wait(self, seconds):
        start = self.now_ns()
        end = start + round(float(seconds) * 10**9)
        self.pump_until(lambda: self.now_ns() >= end, max(60.0, float(seconds) * 30),
                        'Simulation time stopped advancing; unpause Gazebo.')

    def save_phases(self):
        if self.output_dir is None:
            return
        csv_dir = self.output_dir / 'csv'
        (self.output_dir / 'phase_log.json').write_text(json.dumps(self.phases, indent=2))
        with (csv_dir / 'phase_timestamps.csv').open('w', newline='') as handle:
            fields = ['phase_id', 'cycle', 'step', 'phase', 'start_time_ns', 'end_time_ns', 'status']
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows({k: p.get(k) for k in fields} for p in self.phases)

    def emit_phase(self, event):
        data = dict(self.current_phase, event=event, event_time_ns=self.now_ns())
        msg = String(data=json.dumps(data))
        self.event_pub.publish(msg)
        self.write('/xarm_sim/phase_events', msg, data['event_time_ns'])
        self.save_phases()

    def start_phase(self, cycle, step_index, step):
        self.current_phase = {
            'phase_id': f'cycle_{cycle:03d}_step_{step_index:02d}',
            'cycle': cycle, 'step': step_index, 'phase': step['phase'],
            'start_time_ns': self.now_ns(), 'end_time_ns': None, 'status': 'running',
        }
        self.phases.append(self.current_phase)
        self.emit_phase('start')
        self.get_logger().info(f'Cycle {cycle}, step {step_index}: {step["phase"]}')

    def end_phase(self, status):
        if self.current_phase is not None:
            self.current_phase['end_time_ns'] = self.now_ns()
            self.current_phase['status'] = status
            self.emit_phase('end')
            self.current_phase = None

    def execute_target(self, client, names, values, duration):
        goal = FollowJointTrajectory.Goal()
        goal.trajectory.joint_names = names
        point = JointTrajectoryPoint()
        point.positions = [float(v) for v in values]
        point.velocities = [0.0] * len(names)
        total_ns = round(float(duration) * 10**9)
        point.time_from_start = Duration(sec=total_ns // 10**9, nanosec=total_ns % 10**9)
        goal.trajectory.points = [point]
        timeout = float(self.get_parameter('action_wall_timeout').value)
        sent = client.send_goal_async(goal)
        self.pump_until(sent.done, timeout, 'Controller did not acknowledge the trajectory.')
        handle = sent.result()
        if handle is None or not handle.accepted:
            raise RuntimeError('Controller rejected trajectory.')
        try:
            result = handle.get_result_async()
            self.pump_until(result.done, timeout, 'Trajectory timed out (Gazebo paused or controller stalled).')
            response = result.result()
            if (response.status != GoalStatus.STATUS_SUCCEEDED
                    or response.result.error_code != FollowJointTrajectory.Result.SUCCESSFUL):
                raise RuntimeError(f'Trajectory failed: {response.result.error_string} '
                                   f'(status={response.status}, code={response.result.error_code})')
            tolerance = float(self.get_parameter('settle_tolerance_rad').value)
            # Every vendor G1 mimic uses multiplier=1, offset=0. Check the actual
            # finger readings too, so a missing mimic plugin cannot pass silently.
            observed_names = GRIPPER_JOINTS if names == ['drive_joint'] else names
            observed_targets = [values[0]] * len(GRIPPER_JOINTS) if names == ['drive_joint'] else values
            try:
                self.pump_until(
                    lambda: (time.monotonic() - self.latest_wall < 2.0
                             and all(name in self.latest
                                     and abs(self.latest[name] - target) <= tolerance
                                     for name, target in zip(observed_names, observed_targets))),
                    20.0, 'Actual Gazebo joints did not reach target.',
                )
            except TimeoutError as exc:
                raise TimeoutError(
                    'Actual Gazebo joints did not reach target. '
                    + joint_target_diagnostics(self.latest, observed_names, observed_targets)
                ) from exc
        except BaseException:
            if rclpy.ok():
                cancel = handle.cancel_goal_async()
                try:
                    self.pump_until(cancel.done, 3.0, 'Trajectory cancellation timed out.')
                except (RuntimeError, TimeoutError):
                    pass
            raise

    def run(self):
        self.wait_ready()
        self.initialize_gripper()
        self.open_recording()
        success = False
        try:
            self.sim_wait(1.0)
            for cycle in range(1, self.cycles + 1):
                if cycle > 1:
                    # The prior cycle ends open. Record an explicit reset rather
                    # than letting the next first-opening step become a no-op.
                    reset = {'phase': 'gripper_reset'}
                    self.start_phase(cycle, 0, reset)
                    self.initialize_gripper()
                    self.end_phase('completed')
                for index, step in enumerate(self.config['sequence'], 1):
                    self.start_phase(cycle, index, step)
                    if 'pose' in step:
                        values = [math.radians(v) for v in self.config['poses_deg'][step['pose']]]
                        self.execute_target(self.arm, ARM_JOINTS, values, step['duration'])
                    else:
                        position = self.config['gripper_sdk'][step['gripper']]
                        self.execute_target(self.gripper, ['drive_joint'], [sdk_to_rad(position)], step['duration'])
                    self.sim_wait(step['dwell'])
                    self.end_phase('completed')
            self.sim_wait(1.0)
            if self.joint_messages == 0:
                raise RuntimeError('No telemetry was recorded.')
            success = True
        finally:
            self.end_phase('aborted')
            self.save_phases()
            # Humble closes/finalizes SequentialWriter through its destructor.
            self.writer = None
            gc.collect()
            metadata = {
                'completed': success, 'cycles_requested': self.cycles,
                'joint_messages': self.joint_messages,
                'initial_gripper_rad': initial_gripper_target(self.config),
                'initialization': 'Gripper commanded and settled before recording; later cycle resets are labelled gripper_reset.',
                'time_base': 'ROS simulation time; nanoseconds',
                'telemetry_source': 'Gazebo joint-state plugin, all 12 actual simulated joints',
                'effort': 'Not published by the Gazebo joint-state plugin; CSV fields are empty.',
                'scene': 'zero-gravity motion test; no object or grasp/contact validation',
            }
            (self.output_dir / 'run_info.json').write_text(json.dumps(metadata, indent=2))
            try:
                from .export_bag import export_bag
                export_bag(self.output_dir / 'rosbag', self.output_dir / 'csv', self.phases)
                self.get_logger().info(f'Rosbag and CSV files saved: {self.output_dir}')
            except Exception as exc:
                self.get_logger().error(f'Bag saved; CSV export failed: {exc}. Use export_bag to retry.')
                if success:
                    raise

    def initialize_gripper(self):
        target = initial_gripper_target(self.config)
        self.get_logger().info(f'Initializing gripper at {target:.3f} rad before the next cycle...')
        self.gripper_history.clear()
        self.execute_target(self.gripper, ['drive_joint'], [target], 3.0)
        tolerance = float(self.get_parameter('settle_tolerance_rad').value)
        self.pump_until(
            lambda: (time.monotonic() - self.latest_wall < 2.0
                     and gripper_settled(self.gripper_history, target, tolerance=tolerance)),
            float(self.get_parameter('startup_timeout').value),
            'Gripper did not settle at its initial angle; check Gazebo and the mimic plugin.',
        )
        self.get_logger().info(f'Gripper settled at {target:.3f} rad.')


def main(args=None):
    rclpy.init(args=args)
    node = None
    exit_code = 0
    try:
        node = SimulationSequence()
        node.run()
    except KeyboardInterrupt:
        exit_code = 130
    except Exception as exc:
        if node is not None:
            node.get_logger().error(str(exc))
        else:
            print(f'Simulation runner: {exc}')
        exit_code = 1
    finally:
        if node is not None:
            node.writer = None
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
