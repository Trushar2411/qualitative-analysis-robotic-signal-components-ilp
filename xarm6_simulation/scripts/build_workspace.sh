#!/usr/bin/env bash
# Run after installing ROS 2 Humble and the apt prerequisites in README.md.
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
sim_workspace="${1:-$HOME/jessie_sim_ws}"
if [[ ! -f /opt/ros/humble/setup.bash ]]; then
  echo 'ROS 2 Humble was not found. See README.md for the required platform.' >&2
  exit 1
fi
# ROS setup scripts are not compatible with nounset in every release.
set +u
source /opt/ros/humble/setup.bash
set -u

mkdir -p -- "$sim_workspace/src"
vendor_dir="$sim_workspace/src/xarm_ros2"
if [[ ! -e "$vendor_dir" ]]; then
  git clone --recursive --branch humble https://github.com/xArm-Developer/xarm_ros2.git "$vendor_dir"
  git -C "$vendor_dir" checkout ac736c92b02de7ca7e0be6f737d77d46707464d8
  git -C "$vendor_dir" submodule update --init --recursive
else
  echo "Using existing xarm_ros2 checkout at $vendor_dir (no checkout or reset performed)."
fi

package_source="$project_dir/src/xarm6_pick_place_sim"
package_target="$sim_workspace/src/xarm6_pick_place_sim"
if [[ ! -e "$package_target" && ! -L "$package_target" ]]; then
  ln -s -- "$package_source" "$package_target"
elif [[ "$(readlink -f -- "$package_target")" != "$(readlink -f -- "$package_source")" ]]; then
  echo "Package already exists at $package_target; refusing to overwrite it." >&2
  exit 1
fi
cd -- "$sim_workspace"
rosdep install --from-paths src --ignore-src --rosdistro humble -r -y
colcon build --symlink-install --packages-up-to xarm6_pick_place_sim --cmake-args -DBUILD_TESTING=OFF
echo "Build finished. In a fresh terminal: source $sim_workspace/install/setup.bash"
