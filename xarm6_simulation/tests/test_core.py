"""Offline checks; run from the xarm6_simulation directory with unittest."""
import csv
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src/xarm6_pick_place_sim'))
from xarm6_pick_place_sim.core import (
    ALL_JOINTS, GRIPPER_JOINTS, add_telemetry_plugin, joint_row,
    phase_for_timestamp, sdk_to_rad, validate_motion,
    initial_gripper_target, gripper_settled,
    configure_gripper_mimic, joint_target_diagnostics,
    set_base_height,
)
from xarm6_pick_place_sim.export_bag import make_row, write_rows, labelled_rows
import yaml


class TestDataCollection(unittest.TestCase):
    def test_sdk_conversion_direction_and_endpoints(self):
        self.assertAlmostEqual(sdk_to_rad(700), 0.15)
        self.assertAlmostEqual(sdk_to_rad(520), 0.33)
        self.assertAlmostEqual(sdk_to_rad(850), 0)
        self.assertAlmostEqual(sdk_to_rad(0), 0.85)
        self.assertLess(sdk_to_rad(700), sdk_to_rad(520))

    def test_invalid_sdk_values(self):
        for value in (-1, 851, float('inf'), float('nan')):
            with self.assertRaises(ValueError):
                sdk_to_rad(value)

    def test_telemetry_plugin_reads_every_joint(self):
        xml = add_telemetry_plugin('<robot name="test"><link name="base"/></robot>')
        root = ET.fromstring(xml)
        plugin = root.find('gazebo/plugin')
        self.assertEqual(plugin.attrib['filename'], 'libgazebo_ros_joint_state_publisher.so')
        self.assertEqual([node.text for node in plugin.findall('joint_name')], ALL_JOINTS)
        self.assertEqual(len(ALL_JOINTS), len(set(ALL_JOINTS)))
        self.assertIsNotNone(root.find('link'))

    def test_phase_boundaries_and_gaps(self):
        phases = [dict(phase='pick', start_time_ns=10, end_time_ns=20),
                  dict(phase='lift', start_time_ns=25, end_time_ns=30)]
        self.assertIsNone(phase_for_timestamp(9, phases))
        self.assertEqual(phase_for_timestamp(10, phases)['phase'], 'pick')
        self.assertIsNone(phase_for_timestamp(20, phases))
        self.assertIsNone(phase_for_timestamp(24, phases))
        self.assertEqual(phase_for_timestamp(25, phases)['phase'], 'lift')
        self.assertIsNone(phase_for_timestamp(30, phases))

    def test_interrupted_phase_does_not_label_future_samples(self):
        phases = [dict(start_time_ns=10, end_time_ns=None)]
        self.assertIsNone(phase_for_timestamp(50, phases))

    def test_absent_effort_is_missing(self):
        msg = SimpleNamespace(name=['drive_joint'], position=[0.2], velocity=[0.1], effort=[])
        row = joint_row(msg)
        self.assertIsNone(row['drive_joint_effort'])
        self.assertEqual(row['drive_joint_position'], 0.2)

    def test_joint_mapping_uses_names_not_array_order(self):
        msg = SimpleNamespace(name=['right_finger_joint', 'joint2'],
                              position=[0.3, -0.5], velocity=[], effort=[])
        row = joint_row(msg)
        self.assertEqual(row['right_finger_joint_position'], 0.3)
        self.assertEqual(row['joint2_position'], -0.5)

    def test_configuration_matches_latest_script(self):
        path = Path(__file__).resolve().parents[1] / 'src/xarm6_pick_place_sim/config/motion.yaml'
        config = validate_motion(yaml.safe_load(path.read_text()))
        self.assertEqual(config['poses_deg']['pick'], [0, 39, -60, 0, -67, 0])
        self.assertEqual(config['poses_deg']['place'], [-15, 46, -68, 0, -69, 0])
        self.assertEqual(len(config['sequence']), 9)
        self.assertEqual(sum(s['phase'] == 'gripper_opening' for s in config['sequence']), 2)

    def test_invalid_motion_duration_rejected(self):
        config = {'poses_deg': {'home': [0] * 6}, 'gripper_sdk': {'open': 700},
                  'sequence': [{'phase': 'home', 'pose': 'home', 'duration': 0, 'dwell': 1}]}
        with self.assertRaises(ValueError):
            validate_motion(config)

    def test_initial_gripper_defaults_to_closed_in_older_configs(self):
        self.assertAlmostEqual(initial_gripper_target({'gripper_sdk': {'close': 520}}), 0.33)

    def test_invalid_initial_gripper_angle_rejected(self):
        for value in (-0.01, 0.86, float('nan'), float('inf')):
            with self.assertRaisesRegex(ValueError, 'initial_gripper_rad'):
                validate_motion({'initial_gripper_rad': value})

    def test_stability_gate_requires_a_full_second(self):
        samples = [(i * 10_000_000, {n: 0.33 for n in GRIPPER_JOINTS}) for i in range(101)]
        self.assertFalse(gripper_settled(samples[:-1], 0.33))
        self.assertTrue(gripper_settled(samples, 0.33))

    def test_stability_gate_rejects_oscillating_or_open_gripper(self):
        unstable = [(i * 10_000_000, {n: 0.33 + (0.005 if i % 2 else -0.005)
                                    for n in GRIPPER_JOINTS}) for i in range(101)]
        self.assertFalse(gripper_settled(unstable, 0.33))
        opened = [(stamp, {n: 0.15 for n in GRIPPER_JOINTS}) for stamp, _ in unstable]
        self.assertFalse(gripper_settled(opened, 0.33))

    def test_stability_gate_rejects_missing_finger_or_telemetry_gap(self):
        samples = [(i * 10_000_000, {n: 0.33 for n in GRIPPER_JOINTS}) for i in range(101)]
        del samples[50][1]['right_finger_joint']
        self.assertFalse(gripper_settled(samples, 0.33))
        gapped = [(i * 200_000_000, {n: 0.33 for n in GRIPPER_JOINTS}) for i in range(6)]
        self.assertFalse(gripper_settled(gapped, 0.33))

    def test_stability_gate_accepts_small_mimic_offsets_and_drift(self):
        samples = [(i * 10_000_000,
                    {n: 0.33 + (0.01 if n != 'drive_joint' else 0) + i * 0.000001
                     for n in GRIPPER_JOINTS}) for i in range(101)]
        self.assertTrue(gripper_settled(samples, 0.33))

    def test_repeated_open_events_remain_distinct_and_export_blank_effort(self):
        phases = [dict(phase='gripper_opening', phase_id=f'step_{i}', cycle=1,
                       status='completed', start_time_ns=start, end_time_ns=start+10)
                  for i, start in [(2, 100), (7, 200)]]
        msg = SimpleNamespace(name=GRIPPER_JOINTS,
                              position=[0.15] * 6, velocity=[0.0] * 6, effort=[],
                              header=SimpleNamespace(stamp=SimpleNamespace(sec=0, nanosec=105)))
        rows = [make_row(msg, stamp, phases) for stamp in (105, 150, 205)]
        self.assertEqual([r['phase_id'] for r in rows], ['step_2', '', 'step_7'])
        self.assertEqual(rows[1]['phase'], 'idle')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'test.csv'
            write_rows(path, rows, ALL_JOINTS)
            with path.open() as handle:
                exported = list(csv.DictReader(handle))
            self.assertEqual(exported[0]['drive_joint_effort'], '')
            self.assertEqual(exported[0]['joint1_position'], '')
            self.assertEqual(exported[0]['drive_joint_position'], '0.15')
            self.assertEqual(exported[0]['bag_time_ns'], '105')

    def test_idle_filter_preserves_phase_holds_and_original_timestamps(self):
        phases = [dict(phase='gripper_opening', phase_id='step_2', cycle=1,
                       status='completed', start_time_ns=100, end_time_ns=200)]
        msg = SimpleNamespace(name=['drive_joint'], position=[0.15], velocity=[0.0], effort=[],
                              header=SimpleNamespace(stamp=SimpleNamespace(sec=0, nanosec=150)))
        rows = [make_row(msg, stamp, phases) for stamp in (50, 100, 150, 199, 200, 250)]
        kept = labelled_rows(rows)
        self.assertEqual([row['bag_time_ns'] for row in kept], [100, 150, 199])
        self.assertTrue(all(row['phase'] == 'gripper_opening' for row in kept))
        self.assertTrue(all(row['drive_joint_position'] == 0.15 for row in kept))
        self.assertEqual(len(rows), 6)

    def mimic_fixture(self):
        root = ET.Element('robot', {'name': 'test'})
        for name in GRIPPER_JOINTS[1:]:
            plugin = ET.SubElement(ET.SubElement(root, 'gazebo'), 'plugin',
                                   {'name': name, 'filename': 'libgazebo_mimic_joint_plugin.so'})
            ET.SubElement(plugin, 'joint').text = 'drive_joint'
            ET.SubElement(plugin, 'mimicJoint').text = name
            ET.SubElement(plugin, 'hasPID').text = 'false'
            ET.SubElement(plugin, 'multiplier').text = '1.0'
            ET.SubElement(plugin, 'maxEffort').text = '10.0'
        other = ET.SubElement(ET.SubElement(root, 'gazebo'), 'plugin',
                              {'name': 'unrelated', 'filename': 'other_plugin.so'})
        ET.SubElement(other, 'hasPID')
        return ET.tostring(root, encoding='unicode')

    def test_kinematic_following_removes_pid_presence_only_for_fingers(self):
        root = ET.fromstring(configure_gripper_mimic(self.mimic_fixture()))
        plugins = root.findall('gazebo/plugin')
        self.assertEqual(len(plugins), 6)
        for plugin in plugins[:5]:
            self.assertIsNone(plugin.find('hasPID'))
            self.assertEqual(plugin.findtext('multiplier'), '1.0')
            self.assertEqual(plugin.findtext('maxEffort'), '10.0')
        self.assertIsNotNone(plugins[-1].find('hasPID'))

    def test_pid_mode_can_be_restored_without_duplicate_followers(self):
        direct = configure_gripper_mimic(self.mimic_fixture())
        pid = ET.fromstring(configure_gripper_mimic(direct, mode='pid'))
        self.assertTrue(all(p.find('hasPID') is not None for p in pid.findall('gazebo/plugin')[:5]))

    def test_missing_followers_or_unknown_mode_fail_before_simulation(self):
        with self.assertRaises(ValueError):
            configure_gripper_mimic('<robot/>')
        with self.assertRaises(ValueError):
            configure_gripper_mimic(self.mimic_fixture(), mode='unknown')

    def test_joint_timeout_diagnostic_exposes_actual_error_and_missing_joint(self):
        result = joint_target_diagnostics({'drive_joint': 0.33, 'right_finger_joint': 0.38},
                                          ['drive_joint', 'right_finger_joint', 'left_finger_joint'],
                                          [0.33, 0.33, 0.33])
        self.assertIn('drive_joint=0.330000', result)
        self.assertIn('error=+0.050000', result)
        self.assertIn('left_finger_joint=missing', result)

    def test_elevated_mount_preserves_joint_targets_and_other_transforms(self):
        xml = '''<robot name="test"><link name="world"/><link name="link_base"/>
        <joint name="world_joint" type="fixed"><parent link="world"/>
        <child link="link_base"/><origin xyz="0.1 -0.2 0" rpy="0 0 0.5"/></joint>
        <joint name="joint1" type="revolute"><origin xyz="0 0 0.267"/>
        <limit lower="-3" upper="3"/></joint></robot>'''
        root = ET.fromstring(set_base_height(xml, '1.0'))
        origin = root.find("joint[@name='world_joint']/origin")
        self.assertEqual(origin.get('xyz'), '0.1 -0.2 1.0')
        self.assertEqual(origin.get('rpy'), '0 0 0.5')
        self.assertEqual(root.find("joint[@name='joint1']/origin").get('xyz'), '0 0 0.267')
        self.assertEqual(root.find("joint[@name='joint1']/limit").get('upper'), '3')

    def test_mount_rejects_invalid_height_and_unexpected_model(self):
        for value in (0, -1, float('nan'), float('inf')):
            with self.assertRaisesRegex(ValueError, 'base_height'):
                set_base_height('<robot/>', value)
        with self.assertRaisesRegex(ValueError, 'world_joint'):
            set_base_height('<robot/>', 1.0)


if __name__ == '__main__':
    unittest.main()
