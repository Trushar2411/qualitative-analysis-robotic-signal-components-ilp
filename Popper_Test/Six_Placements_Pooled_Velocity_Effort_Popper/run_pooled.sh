#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
POPPER_ROOT="${1:-${POPPER_ROOT:-}}"
RUNS="${RUNS:-10}"
if [[ -z "$POPPER_ROOT" || ! -f "$POPPER_ROOT/popper.py" ]]; then
  echo "Usage: RUNS=10 bash run_pooled.sh /absolute/path/to/Popper" >&2
  exit 2
fi
if ! [[ "$RUNS" =~ ^[1-9][0-9]*$ ]]; then
  echo "RUNS must be a positive integer" >&2
  exit 2
fi
if ! command -v uv >/dev/null || ! command -v swipl >/dev/null; then
  echo "Both uv and SWI-Prolog (swipl) must be on PATH." >&2
  exit 2
fi

mkdir -p "$ROOT/results/logs"
SUMMARY="$ROOT/results/hypothesis_summary.txt"
printf 'POOLED SIX DATASETS | velocity + effort | deadband 0.01 | %s runs/phase\n\n' "$RUNS" > "$SUMMARY"
FAILURES=0
TASKS=0
for folder in "$ROOT/tasks"/*/; do
  [[ -f "$folder/bias.pl" && -f "$folder/bk.pl" && -f "$folder/exs.pl" ]] || continue
  phase="$(basename "$folder")"
  TASKS=$((TASKS + 1))
  for ((run=1; run<=RUNS; run++)); do
    log="$ROOT/results/logs/${phase}_run_${run}.log"
    printf '%s run %s/%s\n' "$phase" "$run" "$RUNS"
    (cd "$POPPER_ROOT" && uv run popper.py "$folder" --noisy -v) > "$log" 2>&1
    status=$?
    {
      printf '==================================================\n'
      printf 'PHASE: %s | RUN: %s | EXIT: %s\n' "$phase" "$run" "$status"
      if [[ "$status" -eq 0 ]]; then
        awk '
          /\*\*\*\*\*\*\*\*\*\* SOLUTION \*\*\*\*\*\*\*\*\*\*/ {in_solution=1; next}
          in_solution && /\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*/ {exit}
          in_solution && (/Precision:/ || /:-/) {print; found=1}
          END {if (!found) print "NO FINAL SOLUTION FOUND (see log)"}
        ' "$log"
      else
        printf 'ERROR: see %s\n' "$log"
      fi
      printf '\n'
    } >> "$SUMMARY"
    if [[ "$status" -ne 0 ]]; then FAILURES=$((FAILURES + 1)); fi
  done
done
if (( TASKS != 8 )); then echo "Expected 8 phase tasks; found $TASKS" >&2; exit 2; fi
echo "Summary: $SUMMARY"
echo "Complete raw outputs: $ROOT/results/logs"
if ((FAILURES)); then echo "$FAILURES Popper runs failed; inspect their logs." >&2; exit 1; fi
