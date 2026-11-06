#!/usr/bin/env python3
"""
patch_entry.py  -  makes ilp_raw_entry.py and ilp_qta_entry.py from the originals.
The originals are NOT changed. In the copies only:
  1) one example per phase OCCURRENCE (segment) instead of per phase label
  2) per lidar: trend word (as before) + entry word (jump_up / jump_down / no_jump)
  3) results -> ilp_results_{raw,qta}_entry_{plain,pillar,combined}
  4) TASK from the command line:  TASK=pill python3 ilp_qta_entry.py
Needs entry_features.py in the same folder.
"""
import sys

RAW_FUNC = '''def prepare_popper_files(all_runs, phase):
    """ENTRY experiment: one example per phase occurrence,
    RAW trend + entry jump per lidar."""
    import entry_features as EF
    facts, pos_exs, neg_exs, predicates = [], [], [], set()
    for run in all_runs:
        df = pd.read_csv(os.path.join(DATA_DIR, run['filename']))
        for s in EF.segments(df):
            seg = s['seg'].reset_index(drop=True)
            if len(seg) < 2:
                continue
            state_id = f"{run['run_id']}_{s['phase']}_{s['k']}"
            any_fact = False
            for sensor in ALL_SENSORS:
                if sensor not in seg.columns:
                    continue
                label = get_dominant_label(seg[sensor].values, DELTA_THRESHOLD)
                if label is not None:
                    p = get_pred_name(sensor, label)
                    predicates.add(p)
                    facts.append(f'{p}({state_id}).')
                    any_fact = True
                e = EF.entry_label(seg, s['prev'], sensor)
                if e:
                    p = get_pred_name(sensor, e)
                    predicates.add(p)
                    facts.append(f'{p}({state_id}).')
                    any_fact = True
            if not any_fact:
                continue
            if s['phase'] == phase:
                pos_exs.append(f'pos(phase_correct({state_id})).')
            else:
                neg_exs.append(f'neg(phase_correct({state_id})).')
    return facts, pos_exs, neg_exs, predicates
'''

QTA_FUNC = '''def prepare(runs, phase):
    """ENTRY experiment: one example per phase occurrence,
    QTA trend + entry jump per lidar."""
    import entry_features as EF
    import pandas as _pd
    facts, pos, neg, preds = [], [], [], set()
    for run in runs:
        run_id = run['run_id']
        csv = EF.find_csv(run_id)
        if csv is None:
            print(f'  no cleaned CSV for {run_id}, skipped')
            continue
        for s in EF.segments(_pd.read_csv(csv)):
            seg = s['seg'].reset_index(drop=True)
            if len(seg) < 2 or s['phase'] in EXCLUDED_PHASES:
                continue
            sid = f"{run_id}_{s['phase']}_{s['k']}"
            any_fact = False
            for sensor in ALL_SENSORS:
                if sensor not in seg.columns:
                    continue
                p = pred_name(sensor, EF.apply_qta(seg[sensor].values))
                preds.add(p)
                facts.append(f'{p}({sid}).')
                any_fact = True
                e = EF.entry_label(seg, s['prev'], sensor)
                if e:
                    p = pred_name(sensor, e)
                    preds.add(p)
                    facts.append(f'{p}({sid}).')
            if not any_fact:
                continue
            if s['phase'] == phase:
                pos.append(f'pos(phase_correct({sid})).')
            else:
                neg.append(f'neg(phase_correct({sid})).')
    return facts, pos, neg, preds
'''

TAIL = '''
# ---- added by patch_entry.py --------------------------------------------
TASK = os.environ.get('TASK', TASK)
RESULTS_DIR = os.path.expanduser('~/rnd_ws/ilp_results_{method}_entry_'
                                 + {{'pw': 'plain', 'pill': 'pillar', 'all': 'combined'}}[TASK])
print(f'ENTRY experiment | method={method} | TASK={{TASK}} | results -> {{RESULTS_DIR}}')
# --------------------------------------------------------------------------

'''
MAIN = "if __name__ == '__main__':"


def replace_func(code, start, end, new, name):
    i = code.find(start)
    j = code.find(end, i)
    if i < 0 or j < 0 or code.count(start) != 1:
        sys.exit(f'STOP: could not find {name} exactly once. Nothing written.')
    return code[:i] + new + code[j + len(end):]


def patch(src, dst, start, end, new, method):
    code = open(src).read()
    if code.count(MAIN) != 1:
        sys.exit(f'STOP: "{MAIN}" not found exactly once in {src}. Nothing written.')
    code = replace_func(code, start, end, new, f'the prepare function in {src}')
    code = code.replace(MAIN, TAIL.format(method=method) + MAIN)
    open(dst, 'w').write(code)
    print(f'OK: {dst}')


patch('ilp_raw_loocv.py', 'ilp_raw_entry.py',
      'def prepare_popper_files(all_runs, phase):',
      '    return facts, pos_exs, neg_exs, predicates\n', RAW_FUNC, 'raw')
patch('ilp_qta_loocv.py', 'ilp_qta_entry.py',
      'def prepare(runs, phase):',
      '    return facts, pos, neg, preds\n', QTA_FUNC, 'qta')