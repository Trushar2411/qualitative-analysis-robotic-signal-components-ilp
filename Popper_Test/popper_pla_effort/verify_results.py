#!/usr/bin/env python3
"""Independently check final unary joint-trend rules against the supplied CSV."""
import argparse
import csv
import re
from pathlib import Path

root = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('results_dir', type=Path)
args = parser.parse_args()
rows = list(csv.DictReader((root/'pla_effort_phase_summary.csv').open()))
logs = sorted(args.results_dir.glob('*_run_*.log'))
if not logs:
    parser.error('No phase run logs found in results_dir')
reports = []
for log in logs:
    phase = log.name.rsplit('_run_',1)[0]
    output = log.read_text()
    if 'SOLUTION **********' not in output:
        reports.append(dict(phase=phase,log=log.name,status='no final solution',tp='',fn='',tn='',fp='',precision='',recall=''))
        continue
    final = output.rsplit('SOLUTION **********',1)[1]
    rules = re.findall(r'phase_'+re.escape(phase)+r'\((\w+)\)\s*:-\s*([^\n]+)\.',final)
    bodies = []
    for variable,body in rules:
        matches = list(re.finditer(r'j([1-5])_(ramp_up|ramp_down|constant)\((\w+)\)',body))
        remainder = re.sub(r'j[1-5]_(?:ramp_up|ramp_down|constant)\(\w+\)','',body)
        if not matches or remainder.replace(',','').strip() or any(m[3]!=variable for m in matches):
            raise ValueError(f'Unsupported rule syntax in {log}: {body}')
        bodies.append([(int(m[1]),m[2]) for m in matches])
    if not bodies:
        raise ValueError(f'Final solution has no supported rules: {log}')
    tp=fn=tn=fp=0
    for row in rows:
        predicted=any(all(row[f'joint{j}']==trend for j,trend in body) for body in bodies)
        actual=row['phase']==phase
        tp+=predicted and actual; fn+=not predicted and actual
        fp+=predicted and not actual; tn+=not predicted and not actual
    reports.append(dict(phase=phase,log=log.name,status='independently checked',tp=tp,fn=fn,tn=tn,fp=fp,
                        precision=tp/(tp+fp) if tp+fp else 0,recall=tp/(tp+fn) if tp+fn else 0))
destination=args.results_dir/'verified_scores.csv'
with destination.open('w',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(reports[0]));writer.writeheader();writer.writerows(reports)
print(destination)
for r in reports: print(r)
