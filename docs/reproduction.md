# Reproducing xArm6 experiments

The commands below use Bash from the repository root and assume the analysis environment from the [README](../README.md#installation-and-reproduction). Use a new output directory for each run.

The offline checks exercised the PLA fit, both task generators and the evaluator with embedded phases. ROS 2 collection and Popper training require their target environments. [Verification details](../RESTRUCTURING_REPORT.md#verification)

## Simulation and recording

Install the Ubuntu 22.04, ROS 2 Humble and Gazebo Classic prerequisites in the [simulation guide](../xarm6_simulation/README.md). Use a terminal with the system Python for ROS.

```bash
bash xarm6_simulation/scripts/build_workspace.sh
source /opt/ros/humble/setup.bash
source ~/jessie_sim_ws/install/setup.bash
ros2 launch xarm6_pick_place_sim simulation.launch.py record:=true
```

The launch reads the packaged [motion configuration](../xarm6_simulation/src/xarm6_pick_place_sim/config/motion.yaml). The recorder writes a ROS bag, phase-event log, configuration snapshot, and CSVs under `~/xarm_sim_data/`. The build, live recording, and bag export require the target ROS 2 environment.

## Phase-labelled telemetry

The [packaged run](../xarm6_simulation/pick_place_sim_20261028_212105_162803/csv/) includes full-motion and per-occurrence CSVs and a phase timestamp table. The simulator labels exported samples using half-open phase-event intervals. With an intact local bag and its run metadata, rerun the same segmentation and CSV export with `ros2 run xarm6_pick_place_sim export_bag /path/to/run/rosbag --output-dir /path/to/new-csv-directory`. Bag payloads are absent from the repository. The separate [September xArm recordings](../data/raw/README.md) already include labels and can be split into [per-joint CSVs](../data/processed/README.md).

The commands below use the [November recording](../Pipeline/full_motion_joint_states%2820261111-191003%29.csv). This is a separate input from the packaged October recording. The PLA script groups rows by the supplied phase occurrence IDs and emits a phase interval CSV alongside its fit. August and September analysis variants have their own [entry points](../scripts/README.md). The [Franka guide](../FrankaReplay/README.md) documents a separate heuristic that infers boundaries from gripper motion.

## Generate raw and PLA tasks

```bash
run_dir="$(mktemp -d)"
recording='Pipeline/full_motion_joint_states(20261111-191003).csv'
raw_experiment=Popper_Test/xarm6_raw_nextstep_popper_10runs
pla_experiment=Popper_Test/xarm6_pla_noisy_popper_10runs

python "$raw_experiment/prepare_raw_nextstep_popper.py" "$recording" --out "$run_dir/raw-tasks"
python Pipeline/create_pla_window20_combined.py "$recording" --out-dir "$run_dir/pla-fit"
python "$pla_experiment/prepare_pla_popper.py" \
  "$run_dir/pla-fit/pla_window20_reconstructed.csv" --out "$run_dir/pla-tasks"
```

Raw facts encode adjacent-sample differences within one phase occurrence. Default deadbands are 0.0001 for positions and velocities and 0.001 for effort, in the source signal units per sample. The phase-aligned PLA script fits 20-sample non-overlapping windows of position and velocity and assigns trends using fitted-change thresholds of 0.002 and 0.01, respectively. PLA task preparation reads the reconstructed trend columns and uses 20-sample windows, retaining a trailing window with at least 80% of the requested size. Both task builders use up to 12 screened predicates per phase, a default 2:1 maximum negative-to-positive ratio, and seed 42. They produce a manifest and per-phase `bk.pl`, `exs.pl`, and `bias.pl`.

## Learn rules

```bash
python "$raw_experiment/run_raw_nextstep_10x.py" "$run_dir/raw-tasks" "$PWD/Popper" \
  120 --runs 10 --output "$run_dir/raw-runs"
python "$pla_experiment/run_pla_noisy_10x.py" "$run_dir/pla-tasks" "$PWD/Popper" \
  120 --runs 10 --output "$run_dir/pla-runs"
```

Each runner invokes Popper in noisy mode and records per-phase logs, status, hypothesis frequencies, and merged summaries. Its timeout is per phase. These training commands require a working Popper environment and were left for execution there. For previously generated tasks and results, see the [raw experiment](../Popper_Test/xarm6_raw_nextstep_popper_10runs/README.md) and [PLA experiment](../Popper_Test/xarm6_pla_noisy_popper_10runs/README.md).

## Evaluate and compare rules

The evaluator reads two result CSVs. By default it applies the most frequent hypothesis per phase to each representation. The example uses the checked-in hypotheses and a recording with embedded phase labels. Use a separate recording and independent phase annotations to evaluate generalization.

```bash
python Pipeline/xarm6_unlabelled_rule_evaluator_updated/compare_unlabelled.py "$recording" \
  --ground-truth embedded --out "$run_dir/scored"
```

For a fresh training run, add `--raw-results "$run_dir/raw-runs/all_results.csv"` and `--pla-results "$run_dir/pla-runs/all_results.csv"`. The default PLA evaluator approximates slope in phase-blind 20-sample windows. For an aligned set of precomputed phase-blind trends, pass `--pla-csv`. The phase-aligned reconstruction used for training relies on labels and can introduce their boundaries into a test. Keep that distinction when comparing scores. The evaluator applies centered offline smoothing before episode extraction.

With reference phases, compare `ground_truth_accuracy.csv` and `accuracy_macro.csv` for classification, and `matched_boundary_errors.csv` for timing. The macro table includes precision, recall, F1, MCC, and specificity. The evaluator does not emit balanced accuracy or a complexity table. On telemetry without reference phases, omit `--ground-truth` and inspect timeline, activations, and proposed episodes. See the [evaluator guide](../Pipeline/xarm6_unlabelled_rule_evaluator_updated/README.md) for required channels and other options.

## Interpreting saved results

- The [saved comparison bundle](../results/comparisons/xarm6/) includes the raw and PLA repeated-run CSVs, aggregate classification and complexity tables, boundary errors, and figures. The generating command and aggregation protocol for the classification and boundary tables could not be established from the checked-in files. Treat those tables as historical records.
- The [unlabelled evaluation](../Pipeline/xarm6_unlabelled_rule_evaluator_updated/results/run_info.json) used a separate input named `full_motion_joint_states_shrikar_joint5_from_joint4.csv`, the majority hypothesis, a phase-blind slope approximation, and a joint-5 position threshold override of 0.00001. It records no ground truth.
- The saved task manifests give historical source paths from another environment. Their original uploaded filenames differ from the names in this checkout. See the [restructuring report](../RESTRUCTURING_REPORT.md) for the checks used to assess the checked-in inputs.
