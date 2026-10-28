"""Export all split SQLite rosbag files using rosbag2's reader, without pandas."""
import argparse
import csv
import json
from pathlib import Path
import re

from .core import ALL_JOINTS, GRIPPER_JOINTS, joint_row, phase_for_timestamp


def make_row(msg, timestamp, phases):
    header_ns = msg.header.stamp.sec * 10**9 + msg.header.stamp.nanosec
    phase = phase_for_timestamp(timestamp, phases)
    return {
        'bag_time_ns': timestamp, 'bag_time_sec': f'{timestamp / 1e9:.9f}',
        'header_stamp_ns': header_ns, 'header_stamp_sec': f'{header_ns / 1e9:.9f}',
        'phase': phase['phase'] if phase else 'idle',
        'phase_id': phase['phase_id'] if phase else '',
        'cycle': phase['cycle'] if phase else '',
        'phase_status': phase['status'] if phase else '',
        **joint_row(msg),
    }


def write_rows(path, rows, joints):
    fields = ['bag_time_ns', 'bag_time_sec', 'header_stamp_ns', 'header_stamp_sec',
              'phase', 'phase_id', 'cycle', 'phase_status']
    fields += [f'{joint}_{field}' for joint in joints for field in ('position', 'velocity', 'effort')]
    with path.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def labelled_rows(rows):
    """Exclude idle/gap samples while retaining holds inside labelled phases."""
    return [row for row in rows if str(row.get('phase', '')).strip().lower() not in ('', 'idle')]


def export_bag(bag_dir, output_dir=None, phases=None):
    # Keep imports here so the row/phase logic can also be checked without ROS.
    import rosbag2_py
    from rclpy.serialization import deserialize_message
    from sensor_msgs.msg import JointState
    from std_msgs.msg import String

    bag_dir = Path(bag_dir).expanduser().resolve()
    output_dir = Path(output_dir) if output_dir else bag_dir.parent / 'csv'
    output_dir.mkdir(parents=True, exist_ok=True)
    reader = rosbag2_py.SequentialReader()
    reader.open(rosbag2_py.StorageOptions(uri=str(bag_dir), storage_id='sqlite3'),
                rosbag2_py.ConverterOptions(input_serialization_format='cdr', output_serialization_format='cdr'))
    samples = []
    starts = {}
    recovered = []
    while reader.has_next():
        topic, data, timestamp = reader.read_next()
        if topic == '/xarm/joint_states':
            samples.append((timestamp, deserialize_message(data, JointState)))
        elif topic == '/xarm_sim/phase_events':
            event = json.loads(deserialize_message(data, String).data)
            if event['event'] == 'start':
                starts[event['phase_id']] = event
            elif event['event'] == 'end':
                recovered.append(event)
                starts.pop(event['phase_id'], None)
    # Only explicit end events define labelled intervals. A hard-killed, unclosed
    # phase remains unlabelled unless phase_log.json supplies its end.
    if phases is None:
        log = bag_dir.parent / 'phase_log.json'
        phases = json.loads(log.read_text()) if log.exists() else recovered
    if not samples:
        raise RuntimeError('Bag contains no /xarm/joint_states samples.')
    phases = sorted(phases, key=lambda p: p['start_time_ns'])
    rows = [make_row(msg, stamp, phases) for stamp, msg in sorted(samples, key=lambda pair: pair[0])]
    sample_count = len(rows)
    rows = labelled_rows(rows)
    if not rows:
        raise RuntimeError('No labelled phase samples remain after removing idle rows; check the phase log.')
    write_rows(output_dir / 'full_motion_joint_states.csv', rows, ALL_JOINTS)
    write_rows(output_dir / 'gripper_joint_states.csv', rows, GRIPPER_JOINTS)
    for phase in phases:
        if str(phase['phase']).strip().lower() in ('', 'idle'):
            continue
        safe_name = re.sub(r'[^A-Za-z0-9_-]', '_', phase['phase'])
        name = f'{phase["phase_id"]}_{safe_name}_joint_states.csv'
        selected = [row for row in rows if row['phase_id'] == phase['phase_id']]
        write_rows(output_dir / name, selected, ALL_JOINTS)
    print(f'Exported {len(rows)} labelled joint samples to {output_dir}; '
          f'excluded {sample_count - len(rows)} idle/gap samples. Rosbag retains all samples.')
    return len(rows)


def main(args=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bag_dir', type=Path, help='rosbag directory containing metadata.yaml')
    parser.add_argument('--output-dir', type=Path)
    options = parser.parse_args(args)
    export_bag(options.bag_dir, options.output_dir)


if __name__ == '__main__':
    main()
