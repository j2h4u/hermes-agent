#!/bin/sh
# shellcheck shell=sh
# /opt/hermes/bin/python{,3} — `docker exec` privilege-drop shim.
#
# Operators and agents often probe Hermes internals with:
#   docker exec hermes-gateway python3 -c '...'
# Docker exec defaults to the container config user (root in the s6 image).
# Running the venv Python as root can rewrite $HERMES_HOME state files as
# root:root 0600, making the supervised hermes process unable to read them.

set -e

name=$(basename "$0")
case "$name" in
    python|python3) REAL="/opt/hermes/.venv/bin/$name" ;;
    *) REAL="/opt/hermes/.venv/bin/python3" ;;
esac

if [ ! -x "$REAL" ]; then
    echo "python-shim: $REAL not found or not executable" >&2
    exit 127
fi

if [ "$(id -u)" != "0" ]; then
    exec "$REAL" "$@"
fi

case "${HERMES_DOCKER_EXEC_AS_ROOT:-}" in
    1|true|TRUE|True|yes|YES|Yes)
        exec "$REAL" "$@"
        ;;
esac

S6_SUID=/command/s6-setuidgid
if [ ! -x "$S6_SUID" ]; then
    echo "python-shim: $S6_SUID not found; refusing to silently run as root." >&2
    echo "python-shim: re-run with --user hermes or set HERMES_DOCKER_EXEC_AS_ROOT=1." >&2
    exit 126
fi

export HOME=/opt/data

exec "$S6_SUID" hermes "$REAL" "$@"
