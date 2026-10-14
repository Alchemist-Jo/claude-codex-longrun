#!/bin/sh
# Start a command detached from the calling agent, in its own session.
#
#   detach.sh RUN_DIR -- COMMAND [ARGS...]
#
# RUN_DIR must exist and must not contain a pid file yet. The command runs
# with stdin closed, stdout in RUN_DIR/stdout.log and stderr in
# RUN_DIR/stderr.log. RUN_DIR/pid holds the wrapper's pid, which is also the
# process group of everything the command starts. RUN_DIR/exit-status is
# written when the command exits, and only then.
#
# On a remote host, copy this script into the project once and call it there.
set -eu

if [ "$#" -lt 3 ] || [ "$2" != "--" ]; then
  echo "usage: detach.sh RUN_DIR -- COMMAND [ARGS...]" >&2
  exit 2
fi
run=$1
shift 2
if [ ! -d "$run" ]; then
  echo "run directory $run does not exist" >&2
  exit 2
fi
if [ -e "$run/pid" ]; then
  echo "$run/pid exists; every launch gets a new run directory" >&2
  exit 2
fi
run=$(cd "$run" && pwd)

wrapper='echo $$ >"$0/pid"; "$@" </dev/null >"$0/stdout.log" 2>"$0/stderr.log"; echo $? >"$0/exit-status"'

if command -v setsid >/dev/null 2>&1; then
  setsid sh -c "$wrapper" "$run" "$@" </dev/null >/dev/null 2>&1 &
else
  perl -MPOSIX -e 'fork and exit; POSIX::setsid() or die "setsid: $!"; exec @ARGV or die "exec: $!"' \
    sh -c "$wrapper" "$run" "$@" </dev/null >/dev/null 2>&1 &
fi

i=0
while [ ! -s "$run/pid" ] && [ "$i" -lt 50 ]; do
  sleep 0.1
  i=$((i + 1))
done
if [ ! -s "$run/pid" ]; then
  echo "the wrapper did not write $run/pid" >&2
  exit 1
fi
cat "$run/pid"
