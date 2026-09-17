#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
POPPER_ROOT="${1:-${POPPER_ROOT:-}}"
RUNS="${RUNS:-10}"
if [[ -z "$POPPER_ROOT" || ! -f "$POPPER_ROOT/popper.py" ]]; then
  echo "Usage: RUNS=10 bash run_all.sh /path/to/Popper" >&2
  echo "The Popper directory must contain popper.py and its uv environment." >&2
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
printf 'Velocity + effort | each deadband 0.01 | %s repetitions per phase\n\n' "$RUNS" > "$SUMMARY"
ERRORS=0
for number in {1..6}; do
  DATASET="dataset_$number"
  for folder in "$ROOT/datasets/$DATASET"/*/; do
    [[ -f "$folder/bias.pl" && -f "$folder/bk.pl" && -f "$folder/exs.pl" ]] || continue
    phase="$(basename "$folder")"
    if ! grep -q '^pos(' "$folder/exs.pl"; then
      printf 'DATASET: %s | PHASE: %s | SKIPPED: no positive transitions\n\n' "$DATASET" "$phase" >> "$SUMMARY"
      continue
    fi
    for ((run=1; run<=RUNS; run++)); do
      log="$ROOT/results/logs/${DATASET}_${phase}_run_${run}.log"
      printf '%s %s run %s/%s\n' "$DATASET" "$phase" "$run" "$RUNS"
      (cd "$POPPER_ROOT" && uv run popper.py "$folder" --noisy -v) > "$log" 2>&1
      status=$?
      {
        printf '==================================================\n'
        printf 'DATASET: %s | PHASE: %s | RUN: %s | EXIT: %s\n' "$DATASET" "$phase" "$run" "$status"
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
      if [[ "$status" -ne 0 ]]; then ERRORS=$((ERRORS + 1)); fi
    done
  done
done
echo "Summary: $SUMMARY"
echo "Complete raw outputs: $ROOT/results/logs"
if ((ERRORS)); then echo "$ERRORS Popper runs failed; inspect their logs." >&2; exit 1; fi
