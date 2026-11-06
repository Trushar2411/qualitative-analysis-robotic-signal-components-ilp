#!/usr/bin/env python3
"""
patch_levels.py  -  makes ilp_raw_levels.py and ilp_qta_levels.py from the
originals. The originals are NOT changed. In the copies only:
  1) each lidar also gets its level fact (near / at_target / far) from levels.json
  2) results go to ilp_results_{raw,qta}_levels_{plain,pillar,combined}
  3) TASK can be given on the command line:  TASK=pill python3 ilp_qta_levels.py
"""
import sys

TAIL = '''
# ---- added by patch_levels.py -------------------------------------------
import json as _json
TASK = os.environ.get('TASK', TASK)
LEVELS = _json.load(open(os.path.expanduser('~/rnd_ws/levels/levels.json')))
RESULTS_DIR = os.path.expanduser('~/rnd_ws/ilp_results_{method}_levels_'
                                 + {{'pw': 'plain', 'pill': 'pillar', 'all': 'combined'}}[TASK])
print(f'LEVELS experiment | method={method} | TASK={{TASK}} | results -> {{RESULTS_DIR}}')
# --------------------------------------------------------------------------

'''

RAW_OLD = """                facts.append(
                    f'{pred}({state_id}).')
                any_fact = True
"""
RAW_NEW = RAW_OLD + """                _short = '_'.join(run_id.split('_')[:3])
                _lvl = LEVELS.get(_short, {}).get(current_phase, {}).get(sensor)
                if _lvl:
                    _lp = get_pred_name(sensor, _lvl)
                    predicates.add(_lp)
                    facts.append(f'{_lp}({state_id}).')
"""

QTA_OLD = """                facts.append(f'{p}({sid}).')
                any_fact = True
"""
QTA_NEW = QTA_OLD + """                _short = '_'.join(run_id.split('_')[:3])
                _lvl = LEVELS.get(_short, {}).get(cur, {}).get(sensor)
                if _lvl:
                    _lp = pred_name(sensor, _lvl)
                    preds.add(_lp)
                    facts.append(f'{_lp}({sid}).')
"""

MAIN = "if __name__ == '__main__':"


def patch(src, dst, old, new, method):
    code = open(src).read()
    if code.count(old) != 1:
        sys.exit(f'STOP: expected the fact-writing block exactly once in {src}, found {code.count(old)}. Nothing written.')
    if code.count(MAIN) != 1:
        sys.exit(f'STOP: expected "{MAIN}" exactly once in {src}. Nothing written.')
    code = code.replace(old, new)
    code = code.replace(MAIN, TAIL.format(method=method) + MAIN)
    open(dst, 'w').write(code)
    print(f'OK: {dst}')


patch('ilp_raw_loocv.py', 'ilp_raw_levels.py', RAW_OLD, RAW_NEW, 'raw')
patch('ilp_qta_loocv.py', 'ilp_qta_levels.py', QTA_OLD, QTA_NEW, 'qta')