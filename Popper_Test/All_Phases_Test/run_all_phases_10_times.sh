#!/bin/bash
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
POPPER_DIR="${1:-$HOME/qualitative-analysis-robotic-signal-components-ilp/Popper}"
SUMMARY="$ROOT/all_phases_hypothesis_summary.txt"

PHASES=(
  home
  gripper_opening
  pick
  pick_delay
  gripper_closing
  lift
  place
  retract
  return_home
)

> "$SUMMARY"

for phase in "${PHASES[@]}"; do
    python3 "$ROOT/set_target.py" "$phase"

    echo "==================================================" >> "$SUMMARY"
    echo "PHASE: $phase" >> "$SUMMARY"
    echo "==================================================" >> "$SUMMARY"

    for i in $(seq 1 10); do
        echo "Running $phase: $i/10"

        OUTPUT=$(cd "$POPPER_DIR" && uv run popper.py "$ROOT" --noisy -v 2>&1)

        echo "RUN $i" >> "$SUMMARY"
        echo "$OUTPUT" | grep "Precision:" | tail -1 >> "$SUMMARY"

        echo "$OUTPUT" | awk '
            /SOLUTION/ {solution=1; next}
            solution && /:-/ {print}
            solution && /\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*/ {solution=0}
        ' >> "$SUMMARY"

        echo "" >> "$SUMMARY"
    done
done

echo "Finished."
echo "Summary: $SUMMARY"
