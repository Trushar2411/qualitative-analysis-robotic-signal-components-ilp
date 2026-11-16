PIPELINE - ILP phase rules for Kelo Robile wall / pillar following
Always run scripts from this folder:  cd ~/rnd_ws/src/robile_wall_follower/signal_processing/pipeline
Python: ~/popper_env/bin/python <script>

0  PREPARE DATA
   fix_lidar_range.py      cap "no return" (65.53 m) at 10 m, restore missing lidar columns   -> ~/rnd_ws/data_cleaned
   qta_visualizer.py       QTA labels per window (needed by the QTA ILP scripts)              -> ~/rnd_ws/qta_results
   add_odometry.py         odometry -> side_speed, forward_speed, turn_rate_odom              -> ~/rnd_ws/data_cleaned_odom

1  CHOOSE SENSORS
   cpd_check.py            change point detection: which signals change where phases change   -> cpd_results/
   screen_signals.py       report card + phase score for every recorded signal                -> ~/rnd_ws/phase_plots/signal_screening.csv

2  RULES, TREND WORDS ONLY (first attempt)
   ilp_raw_loocv.py, ilp_qta_loocv.py                                                         -> ~/rnd_ws/ilp_results_{raw,qta}_10runs_*

3  RULES, TREND + JUMP WORDS (final, lidar only)
   entry_features.py       shared helper: phase pieces, jump words, QTA labelling
   ilp_raw_entry.py, ilp_qta_entry.py     (TASK = pw / pill / all)                            -> ~/rnd_ws/ilp_results_{raw,qta}_entry_*

4  FAIR TEST
   loo_entry.py            leave-one-run-out, lidar only                                      -> loo_results/

5  MULTI-SENSOR (lidar + odometry)
   ilp_multisensor.py      rules + leave-one-run-out, lidar only vs lidar + odometry          -> multisensor_results/

6  CHECK THE RULES
   count_rule.py           which part of each rule fits each phase piece (PHASE=...)          -> ~/rnd_ws/phase_plots/rule_check_*.csv
   check_reacquired.py     what lidar_left does in wall_reacquired
   test_entry_rules_on_bad_runs.py, test_rules_on_bad_runs.py, why_bad.py                     -> bad_run_test/

7  PLOTS
   plot_each_phase.py      each phase on its own, all pillar runs, 4 lidars
   one_run_one_sensor.py   one run, one sensor, phases marked (RUN=..., SENSOR=...)
   trend_vs_jump.py        trend words vs jump words, left lidar
   trend_vs_jump_all.py    same for all 4 lidars                                              -> ~/rnd_ws/phase_plots/<run>/
   plot_motion_phases.py   IMU / odometry signals per phase

logs/      outputs of earlier runs
../_to_delete/   old or replaced scripts (delete when everything works)
../_check_first/ scripts from before; check before deleting (signal_processor.py may have built data_cleaned)
