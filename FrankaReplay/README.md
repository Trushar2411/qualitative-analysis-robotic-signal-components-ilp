# Franka demonstration replay on Ubuntu

This package opens a 3D viewer of the Franka Panda pick-and-place demonstrations from:

https://huggingface.co/datasets/Ekshan267/franka-place-cube-in-box-mimic-dataset

The robot follows recorded joint positions. The cube and box follow their recorded positions. You can pause, inspect individual frames and slow down a demonstration. This can help you compare your ILP phase predictions with the visible motion.

## What this version does

This is a visual replay. The arm and object positions are set directly at each recorded frame. It does not simulate grasp forces, friction, collisions or a new control policy. The table, cube and box are approximate visual geometry, and cube/box orientations are fixed. A visible cube movement therefore comes from the recorded dataset, rather than a grasp computed by this viewer.

The viewer does not learn or apply Popper rules, automatically label phases, replay RGB camera images, or generate fault examples. Those would be separate additions. Use the original HDF5 file; a joint-only CSV has lost the object positions needed by this version.

## Package contents

| File | Purpose |
|---|---|
| `franka_replay.py` | Loads one demonstration and opens the viewer |
| `setup_ubuntu.sh` | Creates a Python 3.12 environment and installs dependencies |
| `requirements.txt` | Python dependencies |
| `README.md` | Installation, use, interpretation and troubleshooting |

The dataset and Python environment are not bundled. Setup and dataset download require internet access. After installation and download, replay uses local files.

## 1. Prepare Ubuntu

Use a normal Ubuntu desktop terminal. The instructions target Ubuntu 22.04 or later on an Intel/AMD 64-bit computer. No ROS installation, CUDA installation or dedicated NVIDIA GPU is required for this replay. A working graphical desktop with OpenGL support is needed for the viewer.

Install the system packages:

```bash
sudo apt update
sudo apt install -y python3-venv pipx unzip wget libgl1 libx11-6 libxext6 libxi6 libxrender1
```

Install `uv` if you do not already have it:

```bash
pipx install uv
pipx ensurepath
```

Close and reopen your terminal after `pipx ensurepath`. Verify:

```bash
uv --version
```

If the command is still not found, try:

```bash
~/.local/bin/uv --version
```

The setup script can find either location. If `uv` is already installed and working, skip its installation.

We use `uv` to select Python 3.12. This also works when Ubuntu's default `python3` is a newer version, such as 3.14. You do not need to replace the system Python. The Python package `pybullet-arm64==3.2.8` supplies Linux x86-64 wheels for Python 3.12, despite its name. It is a maintained PyBullet fork and exposes `import pybullet`.

## 2. Extract this package

Download `FrankaReplay_Ubuntu.zip` into your Downloads folder, then run:

```bash
mkdir -p ~/Trushar
unzip ~/Downloads/FrankaReplay_Ubuntu.zip -d ~/Trushar
cd ~/Trushar/FrankaReplay_Ubuntu
ls
```

If your Downloads folder or ZIP filename differs, use the actual path. You should see `franka_replay.py`, `setup_ubuntu.sh`, `requirements.txt` and `README.md`.

Run the following commands from `~/Trushar/FrankaReplay_Ubuntu`, unless a full script path is supplied.

## 3. Install the Python dependencies

```bash
bash setup_ubuntu.sh
```

The script uses `uv` to create `.venv` with Python 3.12. If necessary, `uv` downloads Python. It installs the dependencies in that environment and checks the imports. It does not use `sudo pip`.

You should see:

```text
Replay dependencies are ready.
Setup complete.
```

The script can be rerun to check or finish installation. It reuses an existing Python 3.12 environment.

## 4. Get one HDF5 dataset

For a first run, use the smaller `source_demos.hdf5`. It contains 14 source demonstrations and is about 307 MB. The larger `pick_n_place_258.hdf5` is about 5.13 GB and contains 258 generated demonstrations according to the dataset card.

Download the source dataset:

```bash
mkdir -p data
wget -c -O data/source_demos.hdf5 'https://huggingface.co/datasets/Ekshan267/franka-place-cube-in-box-mimic-dataset/resolve/main/source_demos.hdf5'
```

The `-c` option allows resuming an interrupted download by rerunning the same command.

Alternatively, download through the dataset's Files page and copy the file:

```bash
cp ~/Downloads/source_demos.hdf5 data/
```

If you already have `pick_n_place.hdf5`, keep its actual name and use that name in every command. A filename difference does not require renaming the data.

Check your files:

```bash
ls -lh data/
```

Do not try to extract an HDF5 file. It is the input file itself.

## 5. Inspect the file before opening the viewer

```bash
.venv/bin/python franka_replay.py data/source_demos.hdf5 --inspect
```

This prints the demonstration names, metadata and schema of the first demonstration without loading camera images. The required observations are:

| HDF5 path inside a demonstration | Shape | Interpretation |
|---|---|---|
| `obs/joint_pos` | `(T, 9)` | Seven arm joint angles and two finger joint displacements |
| `obs/cube_pos` | `(T, 3)` | Cube position in the robot base frame |
| `obs/box_pos` | `(T, 3)` | Box position in the robot base frame |

`T` is the number of recorded frames in that demonstration. Arm values are in radians; finger displacements and object positions are in metres. The default joint-column order is arm joints 1 through 7, then finger joints 1 and 2. The source file was checked against the PyBullet Franka model using this order.

List demonstrations separately:

```bash
.venv/bin/python franka_replay.py data/source_demos.hdf5 --list
```

Demonstration names may have gaps. The tested source file includes `demo_7` followed by `demo_9`. Use the names printed by `--list`.

## 6. Run your first replay

```bash
.venv/bin/python franka_replay.py data/source_demos.hdf5 --demo 0
```

A window opens showing the arm, a red cube and a blue open box. The demonstration repeats until you close it.

Click inside the viewer before using the keyboard controls:

| Control | Action |
|---|---|
| Space | Pause or resume |
| Left arrow | Go back one recorded frame while paused |
| Right arrow | Go forward one recorded frame while paused |
| R | Restart the current demonstration |
| Q | Close the viewer |
| Ctrl+C in the terminal | Stop the program |

When pausing immediately after playback, the next frame may appear before the pause takes effect. Arrow keys then let you inspect the exact configuration you want. `R` keeps the current paused/running state.

The viewer label shows the demonstration name, frame number and time relative to the start of that demonstration. This is not a wall-clock timestamp.

## 7. Use different playback options

Play a named demonstration:

```bash
.venv/bin/python franka_replay.py data/source_demos.hdf5 --demo demo_3
```

Play at half speed:

```bash
.venv/bin/python franka_replay.py data/source_demos.hdf5 --demo demo_3 --speed 0.5
```

Play at quarter speed:

```bash
.venv/bin/python franka_replay.py data/source_demos.hdf5 --demo demo_3 --speed 0.25
```

Play once, then close the window:

```bash
.venv/bin/python franka_replay.py data/source_demos.hdf5 --demo demo_3 --once
```

Replay only the first 100 frames, once:

```bash
.venv/bin/python franka_replay.py data/source_demos.hdf5 --demo 0 --frames 100 --once
```

Use an HDF5 file somewhere else on your computer:

```bash
.venv/bin/python franka_replay.py "/home/tezz/Downloads/pick_n_place.hdf5" --demo 0
```

Replace that example path with your actual path. Quotes are needed if a path contains spaces.

Use the full generated dataset:

```bash
.venv/bin/python franka_replay.py data/pick_n_place_258.hdf5 --demo 0
```

The viewer reads only the selected demonstration's required observations. It does not load the entire file or RGB recordings into memory.

## 8. Understand time and demonstration selection

The default recorded rate is 30 Hz. The checked source file stores a simulation timestep of `1/60` second and a decimation of 2, giving one recorded control frame every `1/30` second.

For zero-based frame `i`, the displayed relative time is:

```text
t = i / fps
```

`--speed 0.5` changes how quickly you watch the motion. It does not alter the recorded positions or their original time labels.

Only change `--fps` when the recording rate of your input file is different:

```bash
.venv/bin/python franka_replay.py data/source_demos.hdf5 --fps 30
```

The script does not automatically read the recording rate from metadata. Its default is set for this dataset. Graphical rendering may run slower than the requested speed on a slow machine; no frames are skipped.

`--demo 0` means the first demonstration in natural numeric order. `--demo 8` means the ninth entry in that order, which may have a different suffix if names have gaps. `--demo demo_9` selects that exact name.

## 9. Use the viewer for your ILP phase analysis

Start at half speed, then pause near a phase boundary. Inspect the fingers, cube and arm together, and record the frame/time where the motion changes.

Compare these visual observations with your predicted approach, pick, transport, place and retract labels. Record any disagreement as a frame interval for later investigation. A closed gripper alone does not establish that the object was picked up; the recorded cube trajectory gives additional evidence of a lift.

If your PLA windows are indexed by frame, retain each window's start and end frame so you can compare them with the replay. Align the phase predictions to the original episode before using the viewer's time labels.

This package does not display or execute learned hypotheses yet. The dataset card's grasp/place annotations also do not establish all five of your desired phase labels automatically.

## 10. Open it again on another day

```bash
cd ~/Trushar/FrankaReplay_Ubuntu
.venv/bin/python franka_replay.py data/source_demos.hdf5 --demo 0
```

You do not need to rerun setup or redownload the data.

Optional activation makes the commands shorter:

```bash
source .venv/bin/activate
python franka_replay.py data/source_demos.hdf5 --demo 0
deactivate
```

## Check the replay without a graphical window

```bash
.venv/bin/python franka_replay.py data/source_demos.hdf5 --demo 0 --headless
```

This loads the scene, applies every recorded frame without waiting, and exits. It prints `Completed ... frames.` on success. Headless mode verifies that the data can be replayed; it does not assess task success or save a video.

## All command-line options

```bash
.venv/bin/python franka_replay.py --help
```

| Option | Default | Meaning |
|---|---|---|
| `dataset` | Required | Path to the HDF5 input |
| `--demo` | `0` | Natural-order index or exact demo name |
| `--list` | Off | List demos and metadata, then exit |
| `--inspect` | Off | Print schema and metadata, then exit |
| `--fps` | `30` | Recorded frame rate used for timing |
| `--speed` | `1` | Playback multiplier |
| `--once` | Off | Close after one pass |
| `--frames` | All | Limit to the first N frames |
| `--headless` | Off | Run without a window or playback delays |
| `--table-z` | `0` | Approximate table surface height in metres, in the base frame |
| `--joint-order` | Arm 1–7, fingers 1–2 | Comma-separated joint names matching the nine input columns |

For an input with a verified different column order, supply that order explicitly. Example of the default:

```bash
.venv/bin/python franka_replay.py data/source_demos.hdf5 --joint-order 'panda_joint1,panda_joint2,panda_joint3,panda_joint4,panda_joint5,panda_joint6,panda_joint7,panda_finger_joint1,panda_finger_joint2'
```

Do not rearrange columns merely to make a trajectory look better; verify the input's generating environment or joint-name metadata first.

## Troubleshooting

### `uv: command not found`

Close/reopen the terminal after `pipx ensurepath`. The setup script also checks `~/.local/bin/uv`. If it is not installed:

```bash
pipx install uv
```

### `externally-managed-environment`

Use `bash setup_ubuntu.sh` or `.venv/bin/python -m pip ...`. Do not install these dependencies into Ubuntu's system Python. The supplied setup uses its own Python 3.12 environment.

### Existing `.venv` has the wrong Python or came from Windows

A virtual environment cannot be moved between Windows and Ubuntu. Preserve the old environment by renaming it, then rerun setup:

```bash
mv .venv ".venv.backup.$(date +%Y%m%d-%H%M%S)"
bash setup_ubuntu.sh
```

### `No matching distribution found` or an unexpected source build

This setup intentionally requests binary wheels. Check that the environment is Python 3.12 on Linux x86-64:

```bash
.venv/bin/python --version
uname -m
```

For a normal Intel/AMD Ubuntu computer, `uname -m` should print `x86_64`. A Linux ARM machine needs a different compatible package/build; this setup has not been validated for that architecture.

### `ModuleNotFoundError`

Use the supplied environment's Python rather than another environment:

```bash
bash setup_ubuntu.sh
.venv/bin/python franka_replay.py data/source_demos.hdf5 --demo 0
```

### `File not found`

Check your current directory and the filename:

```bash
pwd
ls -lh data/
```

Use an absolute path if needed. Filenames on Ubuntu are case-sensitive. If your file is named `pick_n_place.hdf5`, use that name rather than `pick_n_place_258.hdf5`.

### `file signature not found` or HDF5 cannot open the file

The download may be incomplete or may contain an HTML error page. Redownload from the dataset's Files page, confirm the download completed, and run `--inspect` again.

### The viewer cannot connect to X or open an OpenGL window

Run from a terminal inside your Ubuntu graphical desktop. A plain remote SSH terminal normally has no display. Check:

```bash
printenv DISPLAY
```

Use `--headless` to distinguish data/dependency problems from a graphics problem. WSL and remote display setups may need additional configuration and were not tested here.

### The GUI crashes but headless mode works

Try software rendering for that process:

```bash
LIBGL_ALWAYS_SOFTWARE=1 .venv/bin/python franka_replay.py data/source_demos.hdf5 --demo 0
```

This may help driver/OpenGL problems and may render more slowly. Check your Ubuntu graphics drivers if the problem persists.

### Keyboard controls do not respond

Click the viewer to give it keyboard focus. Pause with Space before using the arrow keys. Use `Ctrl+C` in the terminal if you need to stop.

### Objects appear to float or overlap

The object shapes and orientations in this viewer are approximate. Their positions follow the observations exactly, but these visuals do not reproduce the original assets' reference points or collision geometry. Adjust `--table-z` only if the table surface in your input uses a different height. Accurate contact reproduction requires the original environment or a carefully reconstructed physics model.

## Validation and sources

All 14 demonstrations in the downloaded `source_demos.hdf5` were replayed through PyBullet in Linux headless mode. One frame was rendered and inspected. The graphical Ubuntu window, input controls and the larger generated dataset still need checking on the user's machine. The shell setup was syntax-checked; the Ubuntu apt installation and complete setup command have not been executed in an Ubuntu desktop session here.

Dataset and current repository files:

- https://huggingface.co/datasets/Ekshan267/franka-place-cube-in-box-mimic-dataset
- https://huggingface.co/datasets/Ekshan267/franka-place-cube-in-box-mimic-dataset/tree/main

Dependency and setup documentation:

- https://pypi.org/project/pybullet-arm64/
- https://docs.astral.sh/uv/guides/install-python/
- https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/

For a physics simulation that tests new grasps or faults, the next task is to reconstruct the environment and execute controller commands. The dataset's `actions` are end-effector/gripper commands, so they cannot be treated directly as nine joint-position targets.
