#!/bin/sh
# Wait for a job started by detach.sh, without touching it.
#
#   wait.sh RUN_DIR [MAX_SECONDS]
#
# Returns when the job's exit-status file exists, when its wrapper pid is
# gone, or after MAX_SECONDS. Without MAX_SECONDS it waits until the job ends.
# Prints one line and exits with:
#   0  finished; the line gives the job's exit status
#   3  still running when MAX_SECONDS passed
#   4  the pid is gone and exit-status does not exist: the job died
#   2  usage error or missing pid file
set -eu

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
  echo "usage: wait.sh RUN_DIR [MAX_SECONDS]" >&2
  exit 2
fi
run=$1
max=${2:-}
if [ ! -s "$run/pid" ]; then
  echo "no pid file in $run" >&2
  exit 2
fi
pid=$(cat "$run/pid")
start=$(date +%s)

while [ ! -f "$run/exit-status" ] && kill -0 "$pid" 2>/dev/null; do
  if [ -n "$max" ] && [ $(( $(date +%s) - start )) -ge "$max" ]; then
    echo "running: pid $pid after ${max}s"
    exit 3
  fi
  sleep 5
done

# The wrapper writes exit-status just before it exits; allow it a moment.
i=0
while [ ! -f "$run/exit-status" ] && [ "$i" -lt 5 ]; do
  sleep 1
  i=$((i + 1))
done
if [ -f "$run/exit-status" ]; then
  echo "finished: exit status $(cat "$run/exit-status")"
  exit 0
fi
echo "died: pid $pid is gone and $run/exit-status does not exist"
exit 4
