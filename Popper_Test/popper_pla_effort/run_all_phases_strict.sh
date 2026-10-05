#!/usr/bin/env bash
# Place this script beside the tasks/ folder.
# Usage: bash run_all_phases_strict.sh /path/to/Popper [timeout_seconds] [runs]
# Always uses uv with strict learning (no --noisy flag).
set -uo pipefail

TASK_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ $# -lt 1 || $# -gt 3 ]]; then
    echo "Usage: bash $0 /path/to/Popper [timeout_seconds=120] [runs=1]" >&2
    exit 2
fi
POPPER_DIR="$(cd -- "$1" && pwd)" || exit 2
TIMEOUT_SECONDS="${2:-120}"
RUNS="${3:-1}"
for number in "$TIMEOUT_SECONDS" "$RUNS"; do
    if [[ ! "$number" =~ ^[1-9][0-9]*$ ]]; then
        echo 'Timeout and runs must be positive integers.' >&2
        exit 2
    fi
done
[[ -f "$POPPER_DIR/popper.py" ]] || { echo 'Popper directory must contain popper.py.' >&2; exit 2; }
[[ -d "$TASK_ROOT/tasks" ]] || { echo 'Put this script beside the tasks/ folder from popper_phases.zip.' >&2; exit 2; }
command -v swipl >/dev/null || { echo 'SWI-Prolog is missing from PATH.' >&2; exit 2; }

command -v uv >/dev/null || { echo 'uv is missing from PATH.' >&2; exit 2; }
COMMAND=(uv run popper.py)

# A fresh directory keeps earlier results intact.
RESULT_DIR="$(mktemp -d "$TASK_ROOT/results_$(date +%Y%m%d_%H%M%S)_XXXXXX")" || exit 1
SUMMARY="$RESULT_DIR/hypothesis_summary.txt"
STATUS="$RESULT_DIR/run_status.tsv"
printf 'phase\trun\texit_code\tlog\n' > "$STATUS"
{
    printf 'Popper phase results\nStarted: %s\n' "$(date -Iseconds)"
    printf 'Popper directory: %s\nTimeout per task: %s seconds\nRuns per phase: %s\n' "$POPPER_DIR" "$TIMEOUT_SECONDS" "$RUNS"
    printf 'Runner: uv | Learning: strict\n\n'
    printf 'Each section contains complete Popper output, including rules and scores when produced.\n'
    printf 'Exit code 0 does not guarantee a learned hypothesis. Repeated runs use the same data.\n'
} > "$SUMMARY"

shopt -s nullglob
TASKS=("$TASK_ROOT"/tasks/*/)
[[ ${#TASKS[@]} -gt 0 ]] || { echo 'No phase task directories found.' >&2; exit 2; }
FAILED=0
for task in "${TASKS[@]}"; do
    phase="$(basename -- "$task")"
    for required in bias.pl exs.pl bk.pl; do
        [[ -f "$task/$required" ]] || { echo "Missing $task/$required" >&2; exit 2; }
    done
    for ((run=1; run<=RUNS; run++)); do
        LOG="$RESULT_DIR/${phase}_run_${run}.log"
        ARGS=("$task" --timeout "$TIMEOUT_SECONDS")
        printf '\nRunning %s (%s/%s)\n' "$phase" "$run" "$RUNS"
        (cd -- "$POPPER_DIR" && "${COMMAND[@]}" "${ARGS[@]}") 2>&1 | tee "$LOG"
        CODES=("${PIPESTATUS[@]}")
        CODE="${CODES[0]}"
        [[ ${CODES[1]} == 0 ]] || { echo 'Could not save the output log.' >&2; exit 1; }
        [[ "$CODE" == 0 ]] || FAILED=1
        printf '%s\t%s\t%s\t%s\n' "$phase" "$run" "$CODE" "$LOG" >> "$STATUS"
        {
            printf '\n===== PHASE: %s | RUN: %s | EXIT CODE: %s =====\n' "$phase" "$run" "$CODE"
            cat -- "$LOG"
            printf '\n'
        } >> "$SUMMARY"
    done
done
printf '\nFinished: %s\n' "$(date -Iseconds)" >> "$SUMMARY"
printf '\nCombined results: %s\nRun status: %s\n' "$SUMMARY" "$STATUS"
if [[ "$FAILED" != 0 ]]; then
    echo 'Some runs failed. Their errors are retained in the summary and logs.' >&2
fi
exit "$FAILED"
