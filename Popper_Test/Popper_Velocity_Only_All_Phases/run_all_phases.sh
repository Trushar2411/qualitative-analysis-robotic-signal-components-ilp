#!/bin/bash
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
POPPER_ROOT="${1:-$HOME/qualitative-analysis-robotic-signal-components-ilp/Popper}"
SUMMARY="$ROOT/hypothesis_summary.txt"
RUNS="${RUNS:-10}"

> "$SUMMARY"

for PHASE_DIR in "$ROOT"/*/; do
    [ -f "$PHASE_DIR/bias.pl" ] || continue

    PHASE="$(basename "$PHASE_DIR")"

    {
        echo "=================================================="
        echo "PHASE: $PHASE"
        echo "=================================================="
    } >> "$SUMMARY"

    for i in $(seq 1 "$RUNS"); do
        echo "Running $PHASE: run $i/$RUNS"

        OUTPUT="$(
            cd "$POPPER_ROOT" &&
            uv run popper.py "$PHASE_DIR" --noisy -v 2>&1
        )"
        STATUS=$?

        echo "RUN $i" >> "$SUMMARY"

        if [ "$STATUS" -ne 0 ]; then
            echo "ERROR: Popper exited with status $STATUS" >> "$SUMMARY"
            echo "" >> "$SUMMARY"
            continue
        fi

        METRIC="$(
            printf '%s\n' "$OUTPUT" |
            awk '
                /\*\*\*\*\*\*\*\*\*\* SOLUTION \*\*\*\*\*\*\*\*\*\*/ {in_solution=1; next}
                in_solution && /Precision:/ {print; exit}
            '
        )"

        RULES="$(
            printf '%s\n' "$OUTPUT" |
            awk '
                /\*\*\*\*\*\*\*\*\*\* SOLUTION \*\*\*\*\*\*\*\*\*\*/ {in_solution=1; next}
                in_solution && /\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*/ {exit}
                in_solution && /:-/ {print}
            '
        )"

        if [ -n "$METRIC" ]; then
            echo "$METRIC" >> "$SUMMARY"
        else
            echo "NO FINAL SOLUTION METRICS FOUND" >> "$SUMMARY"
        fi

        if [ -n "$RULES" ]; then
            printf '%s\n' "$RULES" >> "$SUMMARY"
        else
            echo "NO HYPOTHESIS FOUND" >> "$SUMMARY"
        fi

        echo "" >> "$SUMMARY"
    done
done

echo ""
echo "Finished all velocity-only Popper runs."
echo "Summary saved to:"
echo "$SUMMARY"
