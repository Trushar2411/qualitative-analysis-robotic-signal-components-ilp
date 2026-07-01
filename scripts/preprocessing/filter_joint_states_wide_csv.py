from pathlib import Path

import pandas as pd
from rosbags.highlevel import AnyReader
from rosbags.typesys import Stores, get_typestore

REPO_ROOT = Path(__file__).resolve().parents[2]
BAG_PATH = REPO_ROOT / "pick_place_recordings" / "pick_place_20260701_143554" / "rosbag" / "rosbag_0.db3"
OUTPUT_CSV = REPO_ROOT / "data" / "processed" / "csv" / "joint_states_filtered_wide.csv"

typestore = get_typestore(Stores.ROS2_HUMBLE)
rows = []

with AnyReader([BAG_PATH], default_typestore=typestore) as reader:
    connections = [conn for conn in reader.connections if conn.topic == "/joint_states"]

    for connection, timestamp, rawdata in reader.messages(connections):
        msg = reader.deserialize(rawdata, connection.msgtype)

        if len(msg.velocity) == 0 and len(msg.effort) == 0:
            continue

        if len(msg.position) > 0 and all(abs(position) < 1e-12 for position in msg.position):
            continue

        row = {"timestamp": timestamp}
        for i, name in enumerate(msg.name):
            if i < len(msg.position):
                row[f"{name}_pos"] = msg.position[i]
            if i < len(msg.velocity):
                row[f"{name}_vel"] = msg.velocity[i]
            if i < len(msg.effort):
                row[f"{name}_eff"] = msg.effort[i]

        rows.append(row)

df = pd.DataFrame(rows)
if df.empty:
    raise ValueError(f"No usable /joint_states messages found in {BAG_PATH}")

# Re-aggregate by timestamp in case multiple partial joint-state messages share a time.
df = (
    df.groupby("timestamp", as_index=False)
    .first()
    .sort_values("timestamp")
    .reset_index(drop=True)
)
t0 = df["timestamp"].iloc[0]
df["t_sec"] = (df["timestamp"] - t0) * 1e-9

OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(OUTPUT_CSV, index=False)
print(f"Saved: {OUTPUT_CSV}")
