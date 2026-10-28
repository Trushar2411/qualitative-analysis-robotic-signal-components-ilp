"""ROS-independent validation, units, telemetry description and phase matching."""
import math
import xml.etree.ElementTree as ET

ARM_JOINTS = [f'joint{i}' for i in range(1, 7)]
GRIPPER_JOINTS = [
    'drive_joint', 'left_finger_joint', 'left_inner_knuckle_joint',
    'right_outer_knuckle_joint', 'right_finger_joint', 'right_inner_knuckle_joint',
]
ALL_JOINTS = ARM_JOINTS + GRIPPER_JOINTS


def sdk_to_rad(value):
    value = float(value)
    if not math.isfinite(value) or not 0 <= value <= 850:
        raise ValueError('Gripper SDK position must be between 0 and 850.')
    # Matches XArmDriver::_xarm_gripper_pos_convert with max_pos=850.
    return (850.0 - value) / 1000.0


def validate_motion(config):
    initial = initial_gripper_target(config)
    if not math.isfinite(initial) or not 0 <= initial <= 0.85:
        raise ValueError('initial_gripper_rad must be between 0 and 0.85 radians.')
    poses = config['poses_deg']
    for name, pose in poses.items():
        if len(pose) != 6 or not all(math.isfinite(float(v)) for v in pose):
            raise ValueError(f'{name}: expected six finite joint angles.')
    for value in config['gripper_sdk'].values():
        sdk_to_rad(value)
    if not config['sequence']:
        raise ValueError('Motion sequence is empty.')
    for step in config['sequence']:
        if bool('pose' in step) == bool('gripper' in step):
            raise ValueError('Each step must specify either pose or gripper.')
        if not isinstance(step['phase'], str) or not step['phase'].strip():
            raise ValueError('Every step needs a phase name.')
        for key, minimum, strict in [('duration', 0, True), ('dwell', 0, False)]:
            value = float(step[key])
            if not math.isfinite(value) or value < minimum or (strict and value == 0):
                raise ValueError(f'Invalid {key} in {step}.')
        if 'pose' in step:
            poses[step['pose']]
        else:
            config['gripper_sdk'][step['gripper']]
    return config


def initial_gripper_target(config):
    """Default old configuration files to their configured closed target too."""
    if 'initial_gripper_rad' in config:
        return float(config['initial_gripper_rad'])
    return sdk_to_rad(config['gripper_sdk'].get('close', 520))


def gripper_settled(samples, target, tolerance=0.02, window_ns=10**9, max_range=0.002):
    """Require a full second of actual, stable finger readings near the target.

    samples contains (simulator_header_timestamp_ns, joint_position_dict).
    A single in-tolerance sample does not prove the mechanism has settled.
    """
    if len(samples) < 2:
        return False
    end = samples[-1][0]
    start = end - window_ns
    # Include the sample just before the boundary so the full window is covered.
    first = next((i for i, sample in enumerate(samples) if sample[0] >= start), None)
    if first is None or (first == 0 and samples[0][0] > start):
        return False
    window = list(samples)[max(0, first - 1):]
    stamps = [stamp for stamp, _ in window]
    if any(b <= a or b - a > 100_000_000 for a, b in zip(stamps, stamps[1:])):
        return False
    for name in GRIPPER_JOINTS:
        values = [positions.get(name, math.nan) for _, positions in window]
        if (any(not math.isfinite(value) or abs(value - target) > tolerance for value in values)
                or max(values) - min(values) > max_range):
            return False
    return True


def add_telemetry_plugin(robot_xml):
    """Read actual Gazebo joint positions/velocities, including mimic fingers."""
    robot = ET.fromstring(robot_xml)
    gazebo = ET.SubElement(robot, 'gazebo')
    plugin = ET.SubElement(gazebo, 'plugin', {
        'name': 'xarm_sim_all_joint_telemetry',
        'filename': 'libgazebo_ros_joint_state_publisher.so',
    })
    ros = ET.SubElement(plugin, 'ros')
    ET.SubElement(ros, 'namespace').text = '/xarm_sim'
    ET.SubElement(ros, 'remapping').text = 'joint_states:=joint_states'
    ET.SubElement(plugin, 'update_rate').text = '100'
    for joint in ALL_JOINTS:
        ET.SubElement(plugin, 'joint_name').text = joint
    return ET.tostring(robot, encoding='unicode')


def configure_gripper_mimic(robot_xml, mode='kinematic'):
    """Select the vendor plugin's supported position-following or PID mode.

    This changes the Gazebo mechanism, never the recorded joint-state values.
    The vendor plugin selects PID by the *presence* of hasPID, even if its
    textual value is false, so kinematic mode removes that element entirely.
    """
    if mode not in ('kinematic', 'pid'):
        raise ValueError('gripper_mimic_mode must be kinematic or pid.')
    robot = ET.fromstring(robot_xml)
    expected = set(GRIPPER_JOINTS) - {'drive_joint'}
    followers = []
    for plugin in robot.findall('gazebo/plugin'):
        if plugin.get('filename') != 'libgazebo_mimic_joint_plugin.so':
            continue
        if plugin.findtext('joint') != 'drive_joint':
            continue
        name = plugin.findtext('mimicJoint')
        if name not in expected:
            continue
        followers.append(name)
        if mode == 'kinematic':
            for element in list(plugin.findall('hasPID')):
                plugin.remove(element)
        elif plugin.find('hasPID') is None:
            ET.SubElement(plugin, 'hasPID')
    if set(followers) != expected or len(followers) != len(expected):
        raise ValueError('Expected five unique xArm gripper mimic plugins; check the installed vendor model.')
    return ET.tostring(robot, encoding='unicode')


def set_base_height(robot_xml, height):
    """Elevate the fixed world-to-base mount in both Gazebo and ROS TF.

    Moving the URDF mount keeps the published transforms consistent with the
    simulated links. Do not also add the same offset to spawn_entity's -z.
    """
    height = float(height)
    if not math.isfinite(height) or height <= 0:
        raise ValueError('base_height must be a finite positive height in metres.')
    robot = ET.fromstring(robot_xml)
    mount = robot.find("joint[@name='world_joint']")
    if (mount is None or mount.get('type') != 'fixed'
            or mount.find('parent') is None or mount.find('parent').get('link') != 'world'
            or mount.find('child') is None or mount.find('child').get('link') != 'link_base'):
        raise ValueError('Expected the unprefixed fixed world_joint from world to link_base.')
    origin = mount.find('origin')
    if origin is None:
        origin = ET.SubElement(mount, 'origin', {'rpy': '0 0 0'})
    xyz = origin.get('xyz', '0 0 0').split()
    if len(xyz) != 3:
        raise ValueError('Invalid world_joint mount origin.')
    xyz[2] = str(height)
    origin.set('xyz', ' '.join(xyz))
    return ET.tostring(robot, encoding='unicode')


def joint_target_diagnostics(positions, names, targets):
    details = []
    for name, target in zip(names, targets):
        position = positions.get(name)
        if position is None:
            details.append(f'{name}=missing')
        else:
            details.append(f'{name}={position:.6f} (target={target:.6f}, error={position-target:+.6f})')
    return '; '.join(details)


def phase_for_timestamp(timestamp_ns, phases):
    """Keep gaps idle; aborted phases only cover time up to their recorded end."""
    for phase in phases:
        start, end = phase['start_time_ns'], phase.get('end_time_ns')
        if end is not None and start <= timestamp_ns < end:
            return phase
    return None


def joint_row(msg):
    row = {}
    for i, name in enumerate(msg.name):
        for field in ('position', 'velocity', 'effort'):
            values = getattr(msg, field)
            row[f'{name}_{field}'] = values[i] if i < len(values) else None
    return row
