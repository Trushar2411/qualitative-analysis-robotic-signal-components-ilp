#!/usr/bin/env bash
# Franka PLA: strict Popper learning for five phases.
# Usage: bash run_all_phases_strict.sh [popper_directory] [timeout_seconds] [runs]
# Example: bash run_all_phases_strict.sh \
#   /home/tezz/Trushar/qualitative-analysis-robotic-signal-components-ilp/Popper 120 10
# Run from any directory; this script must be beside tasks/.
set -uo pipefail

TASK_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_POPPER="$HOME/Trushar/qualitative-analysis-robotic-signal-components-ilp/Popper"
if (( $# > 3 )); then
    echo "Usage: bash $0 [popper_directory] [timeout_seconds=120] [runs=1]" >&2
    exit 2
fi
POPPER_DIR="$(cd -- "${1:-$DEFAULT_POPPER}" && pwd)" || exit 2
TIMEOUT_SECONDS="${2:-120}"
RUNS="${3:-1}"
for number in "$TIMEOUT_SECONDS" "$RUNS"; do
    if [[ ! "$number" =~ ^[1-9][0-9]*$ ]]; then
        echo 'Timeout and runs must be positive integers.' >&2
        exit 2
    fi
done
[[ -f "$POPPER_DIR/popper.py" ]] || { echo "Missing: $POPPER_DIR/popper.py" >&2; exit 2; }
[[ -d "$TASK_ROOT/tasks" ]] || { echo "Missing tasks directory: $TASK_ROOT/tasks" >&2; exit 2; }
command -v swipl >/dev/null 2>&1 || { echo 'SWI-Prolog (swipl) is missing from PATH.' >&2; exit 2; }
command -v uv >/dev/null 2>&1 || { echo 'uv is missing from PATH.' >&2; exit 2; }

PHASES=(approach pick transport place retract)
for phase in "${PHASES[@]}"; do
    for required in bias.pl exs.pl bk.pl; do
        [[ -f "$TASK_ROOT/tasks/$phase/$required" ]] || {
            echo "Missing: $TASK_ROOT/tasks/$phase/$required" >&2
            echo 'First generate tasks with: python3 prepare_popper.py all_signals_combined_PLA.csv --out tasks' >&2
            exit 2
        }
    done
done

RESULT_DIR="$(mktemp -d "$TASK_ROOT/results_strict_$(date +%Y%m%d_%H%M%S)_XXXXXX")" || exit 1
SUMMARY="$RESULT_DIR/hypothesis_summary.txt"
STATUS="$RESULT_DIR/run_status.tsv"
printf 'phase\trun\tpositives\tnegatives\texit_code\tlog\n' > "$STATUS"
{
    printf 'Franka PLA — Popper strict learning results\nStarted: %s\n' "$(date -Iseconds)"
    printf 'Popper directory: %s\nTimeout per run: %s seconds\nRuns per phase: %s\n' "$POPPER_DIR" "$TIMEOUT_SECONDS" "$RUNS"
    printf 'Runner: uv run popper.py | Learning mode: strict (no --noisy)\n'
    printf 'Results are training-set hypotheses; repeated runs are not independent validation.\n'
    printf 'Exit code 0 does not guarantee a hypothesis.\n'
} > "$SUMMARY"

FAILED=0
for phase in "${PHASES[@]}"; do
    TASK="$TASK_ROOT/tasks/$phase"
    NPOS=$(grep -c '^pos(' "$TASK/exs.pl" || true)
    NNEG=$(grep -c '^neg(' "$TASK/exs.pl" || true)
    for ((run=1; run<=RUNS; run++)); do
        LOG="$RESULT_DIR/${phase}_run_${run}.log"
        printf '\n===== %s | run %s/%s | +%s -%s =====\n' "$phase" "$run" "$RUNS" "$NPOS" "$NNEG"
        (cd -- "$POPPER_DIR" && uv run popper.py "$TASK" --timeout "$TIMEOUT_SECONDS") 2>&1 | tee "$LOG"
        CODES=("${PIPESTATUS[@]}")
        CODE="${CODES[0]}"
        if [[ "${CODES[1]}" -ne 0 ]]; then
            echo "Failed to write log: $LOG" >&2
            exit 1
        fi
        [[ "$CODE" -eq 0 ]] || FAILED=1
        printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$phase" "$run" "$NPOS" "$NNEG" "$CODE" "$LOG" >> "$STATUS"
        {
            printf '\n===== PHASE: %s | RUN: %s | EXIT CODE: %s =====\n' "$phase" "$run" "$CODE"
            cat -- "$LOG"
            printf '\n'
        } >> "$SUMMARY"
    done
done
printf '\nFinished: %s\n' "$(date -Iseconds)" >> "$SUMMARY"
printf '\nCombined hypotheses: %s\nRun status: %s\n' "$SUMMARY" "$STATUS"
if [[ "$FAILED" -ne 0 ]]; then
    echo 'Some runs failed. Check the logs and combined summary.' >&2
fi
exit "$FAILED"
