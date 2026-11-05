#!/usr/bin/env bash
# The gateway-drain oneshot runs before the nested supervision tree stops.
set -uo pipefail

service_root=${GATEWAY_SERVICE_ROOT:-/run/hermes-service}
s6_setuidgid=${S6_SETUIDGID:-/command/s6-setuidgid}
s6_svc=${S6_SVC:-/command/s6-svc}
s6_svwait=${S6_SVWAIT:-/command/s6-svwait}

set --
for slot in "$service_root"/gateway-*; do
    [ -d "$slot" ] && set -- "$@" "$slot"
done
[ "$#" -gt 0 ] || exit 0

# Keep desired_state untouched: this is container shutdown, not a user-requested
# gateway stop. The next container boot must reconcile and restart the gateways.
# Request every slot first, then wait for every slot concurrently. A stale slot
# can fail either operation without preventing healthy slots from being stopped
# and waited on; the per-slot 250-second waits share one overall bound.
# Covers restart_drain_timeout up to 180s plus the gateway's 60s watchdog grace.
# The inner shell expands its own positional arguments after dropping privileges.
# shellcheck disable=SC2016
exec "$s6_setuidgid" hermes /bin/sh -c '
    s6_svc=$1
    s6_svwait=$2
    shift 2
    for slot do "$s6_svc" -d -- "$slot" || :; done
    for slot do "$s6_svwait" -D -t 250000 -- "$slot" & done
    wait || :
' sh "$s6_svc" "$s6_svwait" "$@"
