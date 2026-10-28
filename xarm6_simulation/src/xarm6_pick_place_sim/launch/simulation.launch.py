"""Gazebo Classic + official xArm URDF/controllers + actual finger telemetry."""
from pathlib import Path
import os
from tempfile import NamedTemporaryFile

from ament_index_python.packages import get_package_share_directory, get_package_prefix
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction, RegisterEventHandler, SetEnvironmentVariable, LogInfo
from launch.conditions import IfCondition
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
import xacro
import yaml
from xarm6_pick_place_sim.core import add_telemetry_plugin, configure_gripper_mimic, set_base_height


def launch_setup(context):
    share = Path(get_package_share_directory('xarm6_pick_place_sim'))
    description_share = Path(get_package_share_directory('xarm_description'))
    control_share = Path(get_package_share_directory('xarm_controller'))
    # Merge the vendor's arm and gripper configurations without editing them.
    controllers = yaml.safe_load((control_share / 'config/xarm6_controllers.yaml').read_text())
    gripper = yaml.safe_load((control_share / 'config/xarm_gripper_controllers.yaml').read_text())
    manager = controllers['controller_manager']['ros__parameters']
    manager.update(gripper['controller_manager']['ros__parameters'])
    manager.update({'update_rate': 1000, 'use_sim_time': True})
    controllers.update({key: value for key, value in gripper.items() if key != 'controller_manager'})
    for value in controllers.values():
        value.setdefault('ros__parameters', {})['use_sim_time'] = True
    with NamedTemporaryFile(mode='w', suffix='.yaml', prefix='jessie_sim_controllers_', delete=False) as handle:
        yaml.safe_dump(controllers, handle)
        params = handle.name
    robot_xml = xacro.process_file(
        str(description_share / 'urdf/xarm_device.urdf.xacro'),
        mappings={
            'dof': '6', 'robot_type': 'xarm', 'add_gripper': 'true',
            'gripper_version': 'G1', 'prefix': '', 'hw_ns': 'xarm',
            'ros2_control_plugin': 'gazebo_ros2_control/GazeboSystem',
            'ros2_control_params': params,
        },
    ).toxml()
    base_height = LaunchConfiguration('base_height').perform(context)
    robot_xml = set_base_height(robot_xml, base_height)
    robot_xml = configure_gripper_mimic(
        robot_xml, mode=LaunchConfiguration('gripper_mimic_mode').perform(context))
    robot_xml = add_telemetry_plugin(robot_xml)
    publisher = Node(
        package='robot_state_publisher', executable='robot_state_publisher',
        parameters=[{'robot_description': robot_xml, 'use_sim_time': True}],
        output='screen',
    )
    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(str(
            Path(get_package_share_directory('gazebo_ros')) / 'launch/gazebo.launch.py')),
        launch_arguments={
            'world': str(share / 'worlds/motion.world'),
            'gui': LaunchConfiguration('gui'), 'server_required': 'true',
        }.items(),
    )
    spawn = Node(
        package='gazebo_ros', executable='spawn_entity.py', output='screen',
        arguments=['-entity', 'UF_ROBOT', '-topic', '/robot_description', '-timeout', '120'],
    )
    spawners = [Node(
        package='controller_manager', executable='spawner', output='screen',
        arguments=[controller, '--controller-manager', '/controller_manager',
                   '--controller-manager-timeout', '120'],
        parameters=[{'use_sim_time': True}],
    ) for controller in (
        'joint_state_broadcaster', 'xarm6_traj_controller', 'xarm_gripper_traj_controller')]
    runner = Node(
        package='xarm6_pick_place_sim', executable='run_sequence', output='screen',
        condition=IfCondition(LaunchConfiguration('record')),
        parameters=[{'use_sim_time': True,
                     'output_dir': LaunchConfiguration('output_dir')}],
    )
    plugin_dir = str(Path(get_package_prefix('xarm_gazebo')) / 'lib')
    plugin_path = os.pathsep.join(filter(None, [plugin_dir, os.environ.get('GAZEBO_PLUGIN_PATH', '')]))
    return [SetEnvironmentVariable('GAZEBO_PLUGIN_PATH', plugin_path),
            LogInfo(msg=f'Fixed robot base mounted {float(base_height):.3f} m above the floor.'),
            RegisterEventHandler(OnProcessExit(target_action=spawn, on_exit=spawners)),
            gazebo, publisher, spawn,
            runner]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('gui', default_value='true'),
        DeclareLaunchArgument('base_height', default_value='1.0',
                              description='Fixed base height above the z=0 floor, in metres'),
        DeclareLaunchArgument('gripper_mimic_mode', default_value='kinematic',
                              description='kinematic: direct position following; pid: vendor force/PID following'),
        DeclareLaunchArgument('record', default_value='false',
                              description='Run and record one motion sequence automatically'),
        DeclareLaunchArgument('output_dir', default_value=str(Path.home() / 'xarm_sim_data')),
        OpaqueFunction(function=launch_setup),
    ])
