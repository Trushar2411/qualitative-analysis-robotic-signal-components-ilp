import pandas as pd

# Read the CSV
df = pd.read_csv("full_motion_joint_states.csv")

# Remove the last column
df = df.iloc[:, :-1]

# Save the modified CSV
df.to_csv("full_motion_joint_states_modified.csv", index=False)