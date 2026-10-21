#!/bin/bash
# run_ver.sh <workdir> <python> <entry> <outdir> <scenario>
# Runs one checkout under Xvfb with a throwaway HOME and copy of the tree, driven by tools/gdcap.py.
# Meant for a disposable container/VM: it edits /etc/hosts, wipes $CAP_HOME and $RUNDIR, clears Qt IPC.
S=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
WD=$1; PY=$2; ENTRY=$3; OUT=$4; SCEN=$5
export HOME=${CAP_HOME:-/home/ghost}
RUNDIR=${RUNDIR:-/opt/Ghost-Downloader}
for d in "$HOME" "$RUNDIR"; do
  if [ -e "$d" ] && [ ! -e "$d/.gdcap" ]; then echo "refusing to wipe $d (not created by run_ver.sh)"; exit 2; fi
done
if [ -z "$KEEP_HOME" ]; then rm -rf "$HOME"; fi
mkdir -p "$HOME/Downloads" "$OUT"; touch "$HOME/.gdcap"
grep -q dl.example.com /etc/hosts || echo "127.0.0.1 dl.example.com" >> /etc/hosts
for v in $(env | grep -i -E "^[^=]*proxy[^=]*=" | cut -d= -f1); do unset "$v"; done
export LANG=zh_CN.UTF-8 LANGUAGE=zh_CN LC_ALL=zh_CN.UTF-8
export QT_SCALE_FACTOR=${QT_SCALE_FACTOR:-2}
export XDG_CONFIG_HOME=$HOME/.config XDG_DATA_HOME=$HOME/.local/share XDG_CACHE_HOME=$HOME/.cache
export PYTHONPATH=${EXTRA_PYTHONPATH:-}
export PYTHONDONTWRITEBYTECODE=1
rm -rf "$RUNDIR"; mkdir -p "$RUNDIR"; touch "$RUNDIR/.gdcap"
(cd "$WD" && git ls-files -z | xargs -0 cp --parents -t "$RUNDIR" 2>/dev/null)
cd "$RUNDIR"
# old versions refuse to start while a stale single-instance shared memory segment exists
ipcrm -a 2>/dev/null; rm -rf /dev/shm/qipc* /tmp/qipc* 2>/dev/null
timeout ${RUN_TIMEOUT:-300} xvfb-run -a -s "-screen 0 3840x2400x24 -dpi 96" "$PY" $S/tools/gdcap.py "$ENTRY" "$OUT" "$SCEN" $CAP_ARGS 2>&1 | grep -v -E "^\s*$|QFluentWidgets Pro|qfluentwidgets.com" | tail -${TAILN:-40}
