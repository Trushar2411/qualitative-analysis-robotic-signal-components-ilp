#!/usr/bin/env python3
"""Repeat 8 RAW Noisy Popper phase tasks, preserve logs, merge final hypotheses.

Usage:
 python run_noisy_10x.py generated_raw_nextstep /path/to/Popper 120 --runs 10
 python run_noisy_10x.py generated_raw_nextstep /path/to/Popper --merge-only
"""
import argparse
import collections
import csv
import json
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PHASES = ('home','gripper_opening','pick','gripper_closing','lift','place','retract','return_home')
METRIC_RE = re.compile(r'Precision:\s*([\d.]+)\s+Recall:\s*([\d.]+)\s+TP:(\d+)\s+FN:(\d+)\s+TN:(\d+)\s+FP:(\d+)\s+Size:(\d+)\s+MDL:([\d.-]+)', re.I)
RULE_RE = re.compile(r'^\s*(?:\d+(?:\.\d+)?s\s+)?([a-z][a-z0-9_]*\([^\n]*?\)\s*:-\s*[^\n]*?\.|[a-z][a-z0-9_]*\([^\n]*?\)\.)\s*$')

def parse_final_solution(log):
    # Only extract hypothesis after the LAST final SOLUTION marker.
    markers=list(re.finditer(r'\*{3,}\s*SOLUTION\s*\*{3,}',log,re.I))
    if not markers:
        return None, None
    tail=log[markers[-1].end():]
    metrics_match=METRIC_RE.search(tail)
    metrics=None
    if metrics_match:
        vals=metrics_match.groups()
        metrics=dict(zip(('precision','recall','tp','fn','tn','fp','size','mdl'),
                         [float(vals[0]),float(vals[1]),*map(int,vals[2:7]),float(vals[7])]))
    clauses=[]
    for line in tail.splitlines():
        if '*****' in line and clauses: break
        m=RULE_RE.match(line)
        if m:
            clause=m.group(1).strip()
            clauses.append(re.sub(r'\s+', ' ',clause))
    return ('\n'.join(clauses) or None),metrics

def canonicalize(hypothesis):
    if not hypothesis: return ''
    clauses=[]
    for line in hypothesis.splitlines():
        line=re.sub(r'\s+','',line).rstrip('.')
        # Strip Popper variable indices to standard V0,V1... when alpha names already are V0.
        if ':-' in line:
            head,body=line.split(':-',1)
            atoms=re.findall(r'[a-z][a-z0-9_]*\([^()]*\)',body)
            if atoms and ','.join(atoms)==body:
                line=head+':-'+','.join(sorted(atoms))
        clauses.append(line+'.')
    return '\n'.join(sorted(clauses))

def merge(output,runs):
    rows=[]
    for phase in PHASES:
        for idx in range(1,runs+1):
            folder=output/f'run_{idx:02d}'
            lp=folder/'logs'/f'{phase}.log'
            status_file=folder/'statuses.json'
            status={}
            if status_file.exists():
                try: status=json.loads(status_file.read_text()).get(phase,{})
                except (ValueError, OSError): pass
            log=lp.read_text(errors='replace') if lp.exists() else ''
            hypothesis,metrics=parse_final_solution(log)
            rows.append({'run':idx,'phase':phase,'status':status.get('status','missing' if not lp.exists() else 'unknown'),
                         'returncode':status.get('returncode',''),'seconds':status.get('seconds',''),
                         'hypothesis':hypothesis or '', 'canonical_hypothesis':canonicalize(hypothesis),
                         **(metrics or {})})
    output.mkdir(parents=True,exist_ok=True)
    cols=['run','phase','status','returncode','seconds','precision','recall','tp','fn','tn','fp','size','mdl','hypothesis','canonical_hypothesis']
    with (output/'all_results.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(rows)
    lines=['# RAW adjacent-step Noisy Popper: repeated-run merged results','',
           'Identical input examples and bias on each run. Repeats are **not** independent evaluations.','',
           'Hypothesis frequencies count equivalent exact rule sets, ignoring body-literal and clause ordering.','']
    freq_rows=[]
    for phase in PHASES:
        subset=[r for r in rows if r['phase']==phase]
        success=[r for r in subset if r['canonical_hypothesis']]
        lines += [f'## {phase}',f'Final solutions: {len(success)}/{runs}. Unique hypotheses: {len(set(r["canonical_hypothesis"] for r in success))}.','']
        counter=collections.Counter(r['canonical_hypothesis'] for r in success)
        for rank,(rule,count) in enumerate(counter.most_common(),1):
            matches=[r for r in success if r['canonical_hypothesis']==rule]
            prec=[r['precision'] for r in matches if 'precision' in r]
            recalls=[r['recall'] for r in matches if 'recall' in r]
            meanp=sum(prec)/len(prec) if prec else None
            meanr=sum(recalls)/len(recalls) if recalls else None
            freq_rows.append({'phase':phase,'rank':rank,'frequency':count,'fraction_of_all_runs':count/runs,
                              'mean_training_precision':meanp,'mean_training_recall':meanr,'hypothesis':rule})
            lines.extend([f'### Rule set {rank}: {count}/{runs} runs',
                          f'Training precision: {meanp:.3f}; training recall: {meanr:.3f}' if meanp is not None and meanr is not None else 'Metrics unavailable',
                          '```prolog',rule,'```',''])
        if not success: lines += ['No final Popper SOLUTION found. Inspect per-run logs.','']
        for r in subset:
            lines.append(f'- Run {r["run"]:02d}: {r["status"]}, return code {r["returncode"]}, solution {"yes" if r["hypothesis"] else "no"}')
        lines.append('')
    with (output/'hypothesis_frequencies.csv').open('w',newline='') as f:
        cols_freq=['phase','rank','frequency','fraction_of_all_runs','mean_training_precision','mean_training_recall','hypothesis']
        w=csv.DictWriter(f,fieldnames=cols_freq);w.writeheader();w.writerows(freq_rows)
    (output/'merged_hypotheses.md').write_text('\n'.join(lines)+'\n')
    (output/'all_results.json').write_text(json.dumps(rows,indent=2)+'\n')
    print(f'\nSaved: {output / "merged_hypotheses.md"}')
    print(f'       {output / "hypothesis_frequencies.csv"}')
    print(f'       {output / "all_results.csv"}')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('tasks',type=Path)
    p.add_argument('popper',type=Path)
    p.add_argument('timeout',nargs='?',type=int,default=120,help='Popper --timeout per phase in seconds')
    p.add_argument('--runs',type=int,default=10)
    p.add_argument('--output',type=Path,default=None)
    p.add_argument('--merge-only',action='store_true')
    p.add_argument('--python',action='store_true',help='Use current python rather than uv run')
    p.add_argument('--overwrite',action='store_true',help='Rerun phases with existing logs')
    args=p.parse_args()
    tasks=args.tasks.expanduser().resolve(); popper=args.popper.expanduser().resolve()
    output=(args.output or tasks/'repeated_runs').expanduser().resolve()
    if args.runs<1:p.error('--runs must be >=1')
    if not args.merge_only:
        if not (popper/'popper.py').is_file():p.error(f'Not found: {popper / "popper.py"} (supply Popper directory, not popper.py)')
        for phase in PHASES:
            if not all((tasks/phase/filename).is_file() for filename in ('bk.pl','exs.pl','bias.pl')):
                p.error(f'Missing bk.pl, exs.pl or bias.pl in {tasks/phase}')
        command_base=([sys.executable,str(popper/'popper.py')] if args.python or shutil.which('uv') is None
                      else ['uv','run','popper.py'])
        for run in range(1,args.runs+1):
            run_dir=output/f'run_{run:02d}'; (run_dir/'logs').mkdir(parents=True,exist_ok=True)
            status_path=run_dir/'statuses.json'
            statuses=json.loads(status_path.read_text()) if status_path.exists() else {}
            for phase in PHASES:
                log_path=run_dir/'logs'/f'{phase}.log'
                if log_path.exists() and not args.overwrite:
                    print(f'Skipping existing run {run:02d} / {phase}',flush=True)
                    continue
                cmd=[*command_base,str(tasks/phase),'--noisy','--timeout',str(args.timeout)]
                print(f'Run {run:02d}/{args.runs}, phase {phase} ...',flush=True)
                start=time.monotonic()
                try:
                    result=subprocess.run(cmd,cwd=popper,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
                    logfile=result.stdout;rc=result.returncode
                    status='ok' if rc==0 else 'error'
                except Exception as exc:
                    logfile=f'Runner error: {exc}\n';rc=-1;status='error'
                elapsed=time.monotonic()-start
                log_path.write_text(logfile)
                rule,metrics=parse_final_solution(logfile)
                statuses[phase]={'status':status,'returncode':rc,'seconds':round(elapsed,3),
                                 'has_final_solution':bool(rule),'timestamp_utc':datetime.now(timezone.utc).isoformat()}
                status_path.write_text(json.dumps(statuses,indent=2)+'\n')
                print(f'  {status}, {elapsed:.1f}s, final solution: {"yes" if rule else "no"}',flush=True)
            merge(output,args.runs)
    merge(output,args.runs)

if __name__=='__main__':main()
