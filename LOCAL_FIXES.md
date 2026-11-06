# Local deployment and retained fixes

This is a short inventory of fixes, features and deployment choices we retain downstream,
not a PR tracker. At each upstream refresh, audit the complete source delta as well as
these listed behaviors, so unlisted additions and upstream replacements are not missed.
The listed regression files document the contracts; do not repeat upstream's
test suite during routine updates. Remove a local implementation only when the
candidate provides the same behavior. A closed or merged PR alone
does not establish that the selected upstream revision contains the fix. Do not
revert an adopted commit blindly: that can undo the upstream implementation too.

## Retained behavior

| Area | Why it remains local / removal condition | Main regression coverage |
| --- | --- | --- |
| Telegram message provenance | Keep forward, reply, quote and channel context when batching, queueing, steering or replaying durable input; ignore topic-creation service messages as reply content. Remove only when upstream carries the same context through all these paths. | `tests/gateway/test_telegram_forward_context.py`, `test_telegram_reply_quote.py`, `test_forward_context_rendering.py`, `test_queue_command.py`, `test_steer_command.py`, `test_active_session_text_merge.py`, `test_telegram_text_batching.py`, `test_native_forward_context.py` |
| Telegram DM topic directory | Read configured topics through the core ConfigBackend; configured names take precedence over historical names. Keep until upstream covers local DM-topic discovery and naming. | `tests/gateway/test_channel_directory.py`, `test_telegram_dm_directory_config.py` |
| SQLite transient read failures | Retry the SQLite NULL/no-more-rows and transient WAL-marker cases with transaction-aware handling. Keep until equivalent upstream handling passes the regressions. | `tests/hermes_state/test_no_more_rows_retry.py`, `tests/hermes_cli/test_state_db_guard.py` |
| Slow integrity checks | Report actual SQLite integrity progress to the startup watchdog using bounded renewable leases; a large healthy database must not trigger a restart loop. | `tests/hermes_cli/test_integrity_check_watchdog.py` |
| Remote file sync | External Compresr's Hermes cache calls `sync(force=True, raise_on_error=True)` to surface transport failures. Keep while upstream lacks this contract; an in-tree caller search alone misses this installed consumer. | `tests/tools/test_file_sync.py`, installed `compresr/integrations/hermes/cache.py` |
| Local Docker runtime | Preserve image revision stamps with canonical release versions, runtime UID/GID, root-safe operator shims and graceful shutdown of every gateway slot. `build.sh` passes `HERMES_BASE_VERSION` from the source's canonical Git version; never use pyproject's `0.0.0` placeholder, which falsely rejects compatible plugins. Retain local build choices: Kazakhstan Debian mirror, Firecrawl/Exa/Edge TTS extras, recursive bytecode/runtime exclusions, opt-in dashboard and test-container volume cleanup. Sealed stores and their snapshot exclusions now use upstream code/layout. | `tests/docker/`, `tests/scripts/test_docker_shutdown_wiring.py` |
| External Compresr | Install the external package reproducibly and retain the absolute compression threshold plus Hermes YAML config loading in both the image and PM environments. Review/remove the guarded package patch when a newer Compresr supplies both behaviors. | `docker/patch_compresr_threshold.py --verify`, isolated image smoke |
| External Muse | Installed from the pinned `v0.5.1-local.3` release of `j2h4u/hermes-muse`, with its own retained-change inventory. Nightly review evaluates every unjudged private turn in the existing 72-hour window, in any language, using the model assigned to Muse; keyword admission filters are removed. Review retains all assistant messages, supports full-turn reads, and carries findings across batches into the daily synthesis, including a summary-only run after the queue is empty. Keep until Muse upstream supplies equivalent behavior. Update through plugin management; the plugin does not patch Hermes core. | Separate fork: `tests/review_all_turns_acceptance.py`, nightly kernel contracts, `tests/native_host_contract.py` |
| Chromium / Playwright and browser sandbox | Retain the emergency 2026-11-03 update: managed Chrome for Testing 156.0.8078.80 (revision 1248), Google Meet's Python Playwright 1.64.1 pin/lock, verified browser artifacts on every platform, and Docker browser sandbox wiring (seccomp/user namespaces and no automatic Docker-wide `--no-sandbox`). Upstream checked on 2026-11-05 still pins Chromium 145.0.7632.6 and Playwright 1.64.0. Retire only when the selected upstream supplies the patched versions or newer and equivalent sandbox behavior; a version bump alone does not replace the whole local change. | `tests/pm/test_chromium.py`, `tests/plugins/test_google_meet_sandbox.py`, `tests/tools/test_terminal_browser_sandbox.py`, `tests/tools/test_docker_environment.py`, `tests/tools/test_bot_desktop_browser.py` |
| Detached Telegram status | One editable structural status message per parent turn, surviving detached children. Source: [#90677](https://github.com/NousResearch/hermes-agent/pull/90677), cherry-picked with attribution and adapted for Telegram deferred edits/flood waits. Remove when upstream has equivalent lifecycle, routing and retry behavior. | `tests/gateway/test_subagent_activity_board.py` |

## Latest full overlay audit — 2026-11-05

Refreshed against upstream `c55af2c93b` (541 commits since the previous base).
Compared every retained source delta; none of the listed behaviors has a complete
upstream replacement. Accepted upstream dependency updates alongside the local
Playwright pin. Kept upstream's bot-peer notice suppression on the local activity
board as well as its standard progress lanes.

Replaced the obsolete late container-finish hook with a dependency-ordered s6-rc
drain: upstream moved profile gateways to the unprivileged `/run/hermes-service`
supervision tree. Stop and wait for its gateway slots before that tree shuts down;
keep the existing bounded parallel waits and persisted desired state.

## Previous full overlay audit — 2026-11-03

Refreshed against upstream `c314285f07`. Retired our live-owner completion recovery
implementation and its early-replay assertion: upstream `6a065c1a58` adopted the fix,
and `8a10a3cbef`, `b847741865` and `e48531be29` add lost-copy checks, held-copy and
per-offer leases, and completed-record context release. Use upstream's implementation
and regression coverage unchanged. The detached Telegram activity board and its child
heartbeat forwarding remain local; reliable delivery and progress display are separate.

Retained the other behaviors above after comparing all downstream source differences.
Combined upstream's Telegram reply-expectation handling with retained provenance, and
adapted the local rendering fixtures to the new original-media-name parameter. Included
upstream's FAL/documents Docker extras alongside the local service extras.

## Previous full overlay audit — 2026-10-28

Compared all downstream files, including tests, generated contracts, documentation and
deployment choices, against upstream `ee7e0f5172`. No additional unclassified behavior
remains outside the groups above. Attribution and the link to this inventory stay local.

Retired the topic-label identity implementation: upstream `91171b7f0b` admits by route key
and adapter, covering mutable labels and speaker/profile drift more broadly. Accepted
upstream tests instead of retaining obsolete assertions rejecting display-field drift;
kept an explicit renamed-topic case on the upstream behavior.

Retired the hidden `.runtime/tools` layout and its PM store-resolution/identity patches:
upstream `a3dc841707` excludes published tool-store entries from source snapshots, and
`b74a29f016` resolves the image payload from its manifest. New images use upstream's
`/opt/hermes/tools` layout. Removed nested-layout-only tests; retained image provenance,
sealed-payload and snapshot checks. Existing images are not migrated in place.

Adapted the Telegram directory reader to the new ConfigBackend seam, including remote
settings without a local file and containment of backend outages during refresh. Kept
the integrity progress callback alongside upstream's rewritten SQLite snapshot code.
The activity-board PR was closed without merging; its implementation remains necessary.

## Update and deployment

### Update the complete Hermes installation

Every operator-triggered upstream refresh includes updating the separately installed
third-party components, not just rebuilding Hermes. This is part of the same maintenance
session, not an unattended updater. Discover the current enabled plugins, installed-skill
sources, package pins and MCP endpoints each time; the table below is a starting map,
not a closed list. Use the existing install metadata and lockfiles, not a new registry.

| Component | Update path |
| --- | --- |
| Compresr | Check the package release, update the image and PM wheel pins together, and reassess both retained package patches before rebuilding. A rebuild alone reinstalls the pinned version. |
| Muse | Refresh upstream in the separate `j2h4u/hermes-muse` fork, audit its `LOCAL_FIXES.md`, and install the resulting pinned revision through Hermes plugin management. Its persistent installation is not updated by rebuilding Hermes. |
| Advanced delegation | Refresh the installed official plugin from `NousResearch/hermes-official-plugins` through plugin management; retain role routes, model assignments and reasoning settings. |
| Honcho | Refresh its separately installed Hermes integration and managed SDK dependencies. The hosted Honcho service itself is provider-managed. Preserve the existing workspace and memory configuration. |
| Ponytail and other external plugins | Resolve their actual installation source and update through the supported installer. Missing provenance is a maintenance blocker to resolve, not permission to overwrite with a guessed source. |
| Third-party skills | Inspect the existing Skills Hub lockfile and other recorded sources; update installed external skills while preserving deliberate local changes. Bundled skills follow Hermes upstream; our own skills have no external version to fetch. |
| Browser and managed runtimes | Check Chromium, Playwright, Python, Node and uv plus optional integration dependencies against their supported release tracks. Use Hermes PM and the image build, preserve compatible lockfiles, and audit the retained browser changes. Do not bypass package management with ad-hoc live installs. |
| Connected MCP services | Include enabled ONAY, Basic Memory, Ozon, Strava and Telegram services, plus any later additions, in the maintenance review. Update available releases through each service's own repository and deployment procedure; never assume a Hermes rebuild updates them. Respect each service's active-work and deployment constraints. |

Audit our fixes and features against each selected upstream revision before retaining
them. Upgrade available compatible releases; report an actual incompatibility or deployment
hold explicitly instead of silently skipping the component. Preserve disabled integrations
as disabled. Verify the changed components with targeted checks and real integration
smokes, including Muse job readiness and MCP registration, without rerunning upstream's
full test suites. Finish with a concise account of what changed, what was already current,
and any component that remains blocked. Keep plugin auto-apply disabled; do not add a
timer, version registry, routine backup or rollback archive for this workflow.

### Source integration and deployment

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
