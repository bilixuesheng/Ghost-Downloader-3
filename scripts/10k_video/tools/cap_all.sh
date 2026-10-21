#!/bin/bash
S=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
for t in "$@"; do
  for attempt in 1 2; do
    RUN_TIMEOUT=200 $S/tools/cap_one.sh $t >/dev/null 2>&1
    if grep -q "scenario done" $S/shots/$t/cap.log 2>/dev/null; then break; fi
  done
  if [ "$t" = gd2 ]; then find $S/shots/gd2 -name "*.png" -print0 | xargs -0 python3 -I $S/tools/gd2_key.py >/dev/null; fi
  echo "$t: done=$(grep -c 'scenario done' $S/shots/$t/cap.log 2>/dev/null) frames=$(ls $S/shots/$t/*_f0*.png 2>/dev/null | wc -l) comps=$(grep -c '^components' $S/shots/$t/cap.log) speeds=$(grep -o 'MB/s' $S/shots/$t/tasks_f05.json $S/shots/$t/down_f05.json 2>/dev/null | wc -l) errs=$(grep -c -i 'error' $S/shots/$t/cap.log)"
done
