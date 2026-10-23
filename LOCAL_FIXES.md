# Local deployment and retained fixes

This is a short inventory of behavior we retain downstream, not a PR tracker.
At each upstream refresh, compare these behaviors with the candidate source.
The listed regression files document the contracts; do not repeat upstream's
test suite during routine updates. Remove a local implementation only when the
candidate provides the same behavior. A closed or merged PR alone
does not establish that the selected upstream revision contains the fix. Do not
revert an adopted commit blindly: that can undo the upstream implementation too.

## Retained behavior

| Area | Why it remains local / removal condition | Main regression coverage |
| --- | --- | --- |
| Telegram message provenance | Keep forward, reply, quote and channel context when batching, queueing or steering. Remove only when upstream carries the same context through all these paths. | `tests/gateway/test_telegram_forward_context.py`, `test_telegram_reply_quote.py`, `test_forward_context_rendering.py`, `test_queue_command.py`, `test_steer_command.py`, `test_active_session_text_merge.py`, `test_telegram_text_batching.py`, `test_native_forward_context.py` |
| Telegram DM topic directory | Read the configured topic directory with `hermes_yaml`; configured names take precedence over historical names. Keep until upstream covers local DM-topic discovery and naming. | `tests/gateway/test_channel_directory.py` |
| SQLite transient read failures | Retry the SQLite NULL/no-more-rows and transient WAL-marker cases with transaction-aware handling. Keep until equivalent upstream handling passes the regressions. | `tests/hermes_state/test_no_more_rows_retry.py`, `tests/hermes_cli/test_state_db_guard.py` |
| Slow integrity checks | Report actual SQLite integrity progress to the startup watchdog using bounded renewable leases; a large healthy database must not trigger a restart loop. | `tests/hermes_cli/test_integrity_check_watchdog.py` |
| Remote file sync | External Compresr's Hermes cache calls `sync(force=True, raise_on_error=True)` to surface transport failures. Keep while upstream lacks this contract; an in-tree caller search alone misses this installed consumer. | `tests/tools/test_file_sync.py`, installed `compresr/integrations/hermes/cache.py` |
| Local Docker runtime | Preserve image revision stamps, runtime UID/GID, root-safe operator shims, sealed PM/tool stores, small build contexts and graceful shutdown of every gateway slot. These are deployment adaptations; revisit each when upstream offers the same guarantees. | `tests/docker/`, `tests/pm/test_store_extensions.py`, `test_venv_store_identity.py`, `tests/scripts/test_docker_shutdown_wiring.py` |
| External Compresr | Install the external package reproducibly and retain the absolute compression threshold plus Hermes YAML config loading in both the image and PM environments. Review/remove the guarded package patch when a newer Compresr supplies both behaviors. | `docker/patch_compresr_threshold.py --verify`, isolated image smoke |
| Delegation delivery | Accept wakes when only the topic label changed, and re-offer stale unclaimed completions even while their owner lives. Sources: [#142257](https://github.com/NousResearch/hermes-agent/pull/142257) (`f636e21890e514a7941ab4726dc57019e51aad92`), [#140721](https://github.com/NousResearch/hermes-agent/pull/140721) (`b953202e55f9c35a2f43ebd08e78349788425729`), cherry-picked with source attribution. Remove local differences when upstream supplies each fix and its regression passes. | `tests/gateway/test_automation_notification_category.py`, `tests/tools/test_async_delegation_orphan_sweep.py` |
| Detached Telegram status | One editable structural status message per parent turn, surviving detached children. Source: [#90677](https://github.com/NousResearch/hermes-agent/pull/90677), cherry-picked with attribution and adapted for Telegram deferred edits/flood waits. Remove when upstream has equivalent lifecycle, routing and retry behavior. | `tests/gateway/test_subagent_activity_board.py` |

## Update and deployment

`main` follows `upstream/main`; `overlay/local-fixes` holds the local integration;
`deploy` tracks `origin/deploy`. Fetch remotes separately:

```bash
git fetch upstream main
git fetch origin deploy
```

Merge upstream into the clean integration checkout, preserve the behavior above,
and inspect any pending-fix source commits before cherry-picking them with `-x`.
For upstream changes, rely on upstream CI instead of rerunning its tests locally.
Keep the result committed and the source checkout clean before a build. Do not
create rollback branches, image archives or database copies for routine updates.
Remove task-owned temporary resources when done. Update the deployment branch
after deployment; do not rewrite published history merely to remove an
upstream-adopted commit.

Production Compose is `/opt/docker/hermes-agent`, not the repository Compose file.
Its `build.sh` accepts `HERMES_SOURCE_DIR` and builds the source plus the external
Compresr layer without restarting. `redeploy.sh` also switches the gateway. Verify
the intended source revision before using either script. Accepted local fixes and
upstream updates include rebuilding, deploying and verifying the live gateway;
the operator has authorized this workflow. An operator's hold on restarting stays
in force until explicitly released: building an image does not authorize a
restart. Do not restart for unrelated read-only investigations. Default deployment
is gateway-only; enable the dashboard only on explicit request.

State is mounted from `/home/j2h4u/.hermes` at `/opt/data`. Provider secrets,
including `GROQ_API_KEY`, come from that home's `.env`; behavior belongs in
`config.yaml`. Never print secrets or replace configuration during an update.
Writing commands inside the root-started container must run as `hermes` (or use
the protected operator shims); absolute Python paths bypass those shims.

Verify source/image provenance, health, Telegram connectivity, enabled MCP server
registration and the Compresr engine/threshold after deployment. A running
container alone is insufficient. Use an isolated `HERMES_HOME` for image smokes;
imports themselves may create state. Never run tests against the live home.
