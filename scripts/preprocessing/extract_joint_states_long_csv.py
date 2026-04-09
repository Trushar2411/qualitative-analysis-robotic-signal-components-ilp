from pathlib import Path

import pandas as pd
from rosbags.highlevel import AnyReader
from rosbags.typesys import Stores, get_typestore

REPO_ROOT = Path(__file__).resolve().parents[2]
BAG_PATH = REPO_ROOT / "data" / "raw" / "rosbags" / "rosbag2_2026_02_21-13_05_45"
OUTPUT_CSV = REPO_ROOT / "data" / "processed" / "csv" / "joint_states.csv"

typestore = get_typestore(Stores.ROS2_HUMBLE)
data = []

with AnyReader([BAG_PATH], default_typestore=typestore) as reader:
    connections = [conn for conn in reader.connections if conn.topic == "/joint_states"]

    for connection, timestamp, rawdata in reader.messages(connections):
        msg = reader.deserialize(rawdata, connection.msgtype)

        for i, name in enumerate(msg.name):
            data.append(
                {
                    "timestamp": timestamp,
                    "joint": name,
                    "position": msg.position[i] if i < len(msg.position) else None,
                    "velocity": msg.velocity[i] if i < len(msg.velocity) else None,
                    "effort": msg.effort[i] if i < len(msg.effort) else None,
                }
            )

df = pd.DataFrame(data)
OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(OUTPUT_CSV, index=False)

print(f"CSV saved successfully: {OUTPUT_CSV}")
