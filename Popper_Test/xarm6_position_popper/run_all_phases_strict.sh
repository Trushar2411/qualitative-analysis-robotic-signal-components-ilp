#!/usr/bin/env bash
# Usage: bash run_all_phases_strict.sh [Popper directory] [timeout seconds] [runs]
# Strict Popper via uv. Generates position-only Prolog tasks automatically.
set -uo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
POPPER_DIR="${1:-/home/tezz/Trushar/qualitative-analysis-robotic-signal-components-ilp/Popper}"
TIMEOUT_SECONDS="${2:-120}"
RUNS="${3:-1}"
INPUT_CSV="${INPUT_CSV:-$ROOT/full_motion_joint_states(20261028-205807).csv}"
for number in "$TIMEOUT_SECONDS" "$RUNS"; do
  [[ "$number" =~ ^[1-9][0-9]*$ ]] || { echo 'Timeout and runs must be positive integers.' >&2; exit 2; }
done
[[ -f "$POPPER_DIR/popper.py" ]] || { echo "Popper not found: $POPPER_DIR/popper.py" >&2; exit 2; }
command -v uv >/dev/null || { echo 'uv missing from PATH' >&2; exit 2; }
command -v swipl >/dev/null || { echo 'SWI-Prolog missing from PATH' >&2; exit 2; }
command -v python3 >/dev/null || { echo 'Python missing from PATH' >&2; exit 2; }
[[ -f "$INPUT_CSV" ]] || { echo "CSV not found: $INPUT_CSV" >&2; exit 2; }
cd "$ROOT" || exit 2
python3 prepare_popper.py "$INPUT_CSV" --out tasks || exit 1
RESULT_DIR="$(mktemp -d "$ROOT/results_$(date +%Y%m%d_%H%M%S)_XXXXXX")" || exit 1
SUMMARY="$RESULT_DIR/hypothesis_summary.txt"
STATUS="$RESULT_DIR/run_status.tsv"
printf 'phase\trun\texit_code\tlog\n' > "$STATUS"
{
  printf 'Position-only Popper strict learning\nStarted: %s\n' "$(date -Iseconds)"
  printf 'CSV: %s\nPopper: %s\nTimeout: %s seconds\nRuns: %s\n' "$INPUT_CSV" "$POPPER_DIR" "$TIMEOUT_SECONDS" "$RUNS"
  printf 'Only position predicates; no velocity or effort.\n\n'
} > "$SUMMARY"
FAILED=0
for task in "$ROOT"/tasks/*/; do
  phase="$(basename "$task")"
  for ((run=1;run<=RUNS;run++)); do
    LOG="$RESULT_DIR/${phase}_run_${run}.log"
    echo "===== $phase | run $run/$RUNS ====="
    (cd "$POPPER_DIR" && uv run popper.py "$task" --timeout "$TIMEOUT_SECONDS") 2>&1 | tee "$LOG"
    codes=("${PIPESTATUS[@]}")
    code="${codes[0]}"
    [[ "${codes[1]}" -eq 0 ]] || { echo 'Could not write log.' >&2; exit 1; }
    [[ "$code" -eq 0 ]] || FAILED=1
    printf '%s\t%s\t%s\t%s\n' "$phase" "$run" "$code" "$LOG" >> "$STATUS"
    { printf '\n===== %s | RUN %s | EXIT %s =====\n' "$phase" "$run" "$code"; cat "$LOG"; } >> "$SUMMARY"
  done
done
printf '\nFinished: %s\n' "$(date -Iseconds)" >> "$SUMMARY"
printf '\nSummary: %s\nStatus: %s\n' "$SUMMARY" "$STATUS"
exit "$FAILED"
