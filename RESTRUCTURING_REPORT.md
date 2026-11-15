# Repository restructuring report

## Baseline and audit

Source branch `xarm`, commit `f57d5682ccbac35d36df916dfe6d1fd8aed0c61d`. Review branch `codex/xarm-research-restructure`. The baseline contained 2,745 tracked files and one Popper gitlink. A separate local evaluator output directory, `Pipeline/xarm6_unlabelled_rule_evaluator_updated/unlabelled_evaluation/`, already contained seven untracked files. It was excluded from the restructuring.

The recursive inventory included 51 Python files, 12 shell scripts, 32 Markdown files, 422 Prolog files, 1,047 CSV files, 438 logs, 658 PNGs, and ROS launch, package, world and motion configuration files. The versioned inventory, including deeper folders and exact filenames, can be recovered with `git ls-tree -r --name-only f57d568`. Popper's own checkout and documentation belong to the upstream submodule.

| Original directory | Contents and disposition |
| --- | --- |
| `Raw data/` | Six September runs plus earlier object/no-object recordings, CSVs, and bag metadata |
| `Processed data/` | Per-joint CSVs for one September run and earlier runs |
| `dataset/` | Six flat CSVs consumed by independent and pooled placement builders |
| `outputs/` | Historical position PLA, velocity PLA, combined PLA, and effort-energy outputs under `OLD/` |
| `Pipeline/` | November inputs, grouped PLA fits and plots, comparison tables, and the unlabelled evaluator with its own rules and run outputs |
| `trial/` | Three standalone full-motion PLA script variants with inputs and saved outputs |
| `Popper_Test/` | Sixteen distinct xArm and Franka experiment directories with generators, launchers, tasks, manifests, and saved runs |
| `Check_motion/`, `Checking_motion/` | Fixed-rule checkers with separate signal assumptions and bundled data |
| `FrankaReplay/` | Replay, HDF5 input, inferred-phase and PLA workflows, saved intermediates, and archives |
| `scripts/` | Collection, preprocessing, PLA, and effort-energy analysis |
| `xarm6_simulation/` | Colcon package, launch/configuration, offline tests, and a sample recording |
| `Popper/` | Git submodule pinned to `5c608d3ec87e4975866042fe326e9a317277e021` |

The original root README omitted the latest simulator, paired experiments, and comparison bundle. Several guides assumed a ZIP or a previous Linux home directory. The processed-data guide overlooked a committed September run. The position-only Popper guide predated its saved October run.

The audit identified 193 groups of identical Git blobs. For example, the November CSV is present in both `Pipeline/` and the PLA experiment directory, and the paired run CSVs occur in the learning outputs, evaluator, and saved comparison. The three copies of each paired result CSV match byte-for-byte. Identical files can serve different entry points or provenance roles. Deduplication and removal of any historical variant were deferred. An absent import provides little evidence about manually invoked entry points. Numbered datasets and historical output variants remain independently identifiable.

Git LFS tracks `FrankaReplay/data/source_demos.hdf5` through the existing `.gitattributes` rule. Its local 307,248,908-byte payload was checked against the pointer's SHA-256. The largest other tracked blob is the November PLA reconstruction at about 3.5 MB. ROS bag metadata exists in the checkout. The DB3, MCAP, and bag payload patterns are ignored and there are no tracked bag payloads.

## Final structure and reversible move map

The [final directory tree](README.md#repository-structure) separates raw and per-joint CSVs under `data/`, saved analysis and comparison outputs under `results/`, and standalone PLA trials under `archive/`. Existing ROS, learning, Franka, and fixed-rule entry points retain their directory relationships. The simulator's workspace uses a symlink to its ROS package. The evaluator resolves rules and the threshold manifest beside its script. Keeping those groups in place avoids altering a workspace or selecting a different hypothesis source.

Every file under each old prefix maps to the same suffix under the new prefix. For example, `Pipeline/comparison/raw_vs_pla_boundary_errors.csv` becomes `results/comparisons/xarm6/raw_vs_pla_boundary_errors.csv`. Reverse the prefix substitutions to recover the old paths. The 1,419 moved files include four READMEs revised at their destinations. No tracked file was removed.

| Old prefix | New prefix | Files |
| --- | --- | ---: |
| `Raw data/` | `data/raw/` | 180 |
| `Processed data/` | `data/processed/` | 67 |
| `dataset/` | `data/raw/six_placement_csvs/` | 6 |
| `outputs/` | `results/` | 1,115 |
| `Pipeline/comparison/` | `results/comparisons/xarm6/` | 8 |
| `trial/` | `archive/full_motion_pla_trials/` | 43 |

The preprocessing script now resolves `data/raw/` and `data/processed/` from the repository root. The four per-joint analysis scripts resolve inputs from `data/processed/` and write their existing output subdirectories under `results/`. The real-robot recorder's path constant now points to `data/raw/`. The position-only xArm Popper shell launcher defaults to the repository's `Popper/` and retains its explicit path override. Environment-specific paths embedded in historic manifests, logs, and reports were preserved as provenance.

The [root README](README.md) was rewritten. The [reproduction guide](docs/reproduction.md) consolidates the paired workflow, scoring and provenance. The four moved READMEs retain their data, output or trial scope. In-place edits cover the collection/analysis index, earlier fixed-rule checker cross-reference, two simulation guides, Popper index, both six-placement guides, and the raw, PLA and position-only xArm guides. Other folder-specific guides and upstream Popper docs were retained. License files and `.gitignore` were preserved.

## Entry points and artifacts

| Workflow | Required inputs and settings | Expected artifacts |
| --- | --- | --- |
| `xarm6_simulation/scripts/build_workspace.sh` and `simulation.launch.py` | Ubuntu 22.04, ROS 2 Humble, Gazebo Classic 11, vendor workspace, packaged motion YAML, `record:=true` | ROS bag, phase events, labelled CSVs, run metadata and configuration under `~/xarm_sim_data/` |
| `ros2 run xarm6_pick_place_sim export_bag` | Intact ROS bag directory and phase log or recorded phase events. Optional output directory | Labelled full-motion, gripper and phase-occurrence CSVs |
| `scripts/preprocessing/create_joint_processed_data.py` | Full-motion xArm CSV and NumPy/Pandas analysis environment. Optional `--raw-run` | Six CSVs in a timestamped `data/processed/` run |
| `scripts/analysis/` | Per-joint inputs, existing window/deadband defaults, optional `--processed-run` | PLA and SWEE CSVs/plots in timestamped `results/` runs |
| `Pipeline/create_pla_window20_combined.py` | November recording, phase IDs, position/velocity data, 20-sample fits. Use `--out-dir` for a fresh run | Phase intervals, window features, reconstructed trends, plots and ZIP |
| `prepare_raw_nextstep_popper.py`, `prepare_pla_popper.py` | Raw recording or reconstructed trend table, default deadbands/windows and seed 42 | Eight phase task directories per representation with facts, bias and examples, plus metadata |
| `run_raw_nextstep_10x.py`, `run_pla_noisy_10x.py` | Prepared tasks, pinned Popper, supported Python, uv and SWI-Prolog. Ten repeats with per-phase timeout in the documented example | Per-phase logs, merged hypotheses and per-run CSVs in explicit output directories |
| `compare_unlabelled.py` | Raw telemetry and paired hypothesis CSVs, optional aligned phase-blind trend data and reference labels, bundled threshold manifest | Activations, candidate episodes, timeline and run metadata. Reference labels enable scores and matched boundary errors |
| [Six-placement builders and launchers](Popper_Test/README.md) | Six bundled CSVs, independent or pooled tasks, Popper environment | Separate task sets, run logs and summaries |
| [Franka pipeline](FrankaReplay/README.md) | LFS HDF5, platform-supported replay environment, existing phase and PLA options | Converted/segmented CSVs, plots, PLA summaries and manifest |
| [Motion checkers](Checking_motion/README.md) and [standalone trials](archive/full_motion_pla_trials/README.md) | Bundled or explicitly selected CSVs and per-script defaults | Fixed-rule match reports or standalone PLA summaries and plots |

## Verification

- Compared all baseline paths against the planned move map. The only tracked content differences were documentation, six Python path/help-text edits, and one shell default-path edit. All dataset, hypothesis, Prolog task, configuration and saved result contents matched Git's baseline after checkout line-ending normalization. The LFS payload matched its content identifier.
- Compiled all 51 first-party Python sources without running module-level routines. Checked all 12 first-party shell scripts with `bash -n`. All 23 offline simulator unit tests passed.
- Ran per-joint preprocessing to a temporary output and obtained six CSVs. Imported and ran all four per-joint analysis entry points against the retained September export, with output redirected to temporary storage. They emitted 6 velocity, 6 position, 6 effort-energy, and 12 combined output CSVs.
- Regenerated the November PLA fit from 4,455 samples. The phase interval CSV matched exactly as text. The reconstruction and window-feature tables matched in labels, shape and numeric values to within 2.8e-16 maximum absolute difference. The regenerated raw and PLA task folders each matched all 24 saved Prolog files as text after newline normalization.
- Ran the evaluator with embedded phases on the November recording and saved fresh outputs outside the repository. It emitted per-phase and macro scores and matched episode boundaries. This diagnostic used the recording associated with the training tasks.
- Computed the README's means directly from the two 80-row saved result CSVs. Precision, recall, F1, MCC and balanced accuracy were computed per row from its confusion counts. Balanced accuracy averages sensitivity and specificity. Hypothesis size uses the saved `size` field. All 80 rows per representation were marked `ok`. The resulting means use each run/phase row equally and differ from some entries in the historical aggregate tables. The aggregate tables and figures were preserved without edits.
- Checked local Markdown links and heading anchors in the project documentation with an automated scan. External references in older guides were outside this link check.

## Remaining reproducibility work

- Run the simulator, colcon build, ROS bag recording and re-export on the target Ubuntu/Humble/Gazebo Classic stack. This checkout's Windows environment did not have that stack. The real-arm and older simulation recorders were reviewed statically.
- Run repeated learning in the pinned Popper environment. The checkout declares Python 3.14 or newer and solver dependencies. The offline checks used Python 3.12. The submodule worktree is present, but ordinary parent-repository status could not traverse its Git metadata under the Windows sandbox. The recorded parent gitlink was retained.
- Establish the exact input, aggregation and boundary-matching protocol used by the historical aggregate comparison tables. The separate unlabelled run contains no true phase annotations. Recordings with independent annotations and matched scoring units are needed for a controlled comparison.
- Confirm local Franka replay and the full set of historical launchers in their target environments. The HDF5 payload was verified by hash. Historical uploaded filenames in the November manifests differ from this checkout, and the task reproduction checked the in-repository equivalents.
- Supply a local input directory to the gripper-width relabeller. Its historical `pick_place_csv/` default is absent. For bag re-export, obtain the original bag payload.
- If new local evaluator runs should be ignored, an opt-in rule is `/Pipeline/xarm6_unlabelled_rule_evaluator_updated/unlabelled_evaluation/`. Keeping fresh outputs in the scratch directories shown in the reproduction guide also avoids accidental commits.
