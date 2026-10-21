#!/bin/bash
# cap_one.sh <tag>  — capture one version per versions.tsv
S=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
line=$(grep -P "^\Q$1\E\t" $S/tools/versions.tsv | head -1)
[ -z "$line" ] && { echo "no entry $1"; exit 1; }
IFS=$'\t' read -r tag env entry scen extra <<< "$line"
case $entry in @*) entry=$S/${entry#@};; esac
case $env in A|B|C|D|E|G2) PY=$S/envs/$env/bin/python;; *) PY=$env;; esac
envs=()
for kv in $extra; do [ "${kv%%=*}" = CAP_ARGS ] && { export CAP_ARGS="${kv#*=}"; continue; }; k=${kv%%=*}; v=${kv#*=}; case $k in CAP_PRELUDE) v=$S/scen/$v;; EXTRA_PYTHONPATH) v=$S/$v;; esac; envs+=("$k=$v"); done
rm -rf $S/shots/$tag
env "${envs[@]}" $S/tools/run_ver.sh $S/ver/$tag $PY $entry $S/shots/$tag $S/scen/$scen
