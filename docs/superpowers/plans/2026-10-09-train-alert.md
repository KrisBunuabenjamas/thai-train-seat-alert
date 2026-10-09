# Train Seat Alert Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Notify Discord when sleeper seats return for 29/30 December 2026, Bangkok Aphiwat to Udon Thani.
**Architecture:** One Python run polls verified D-Ticket endpoints, validates results, reconciles durable state, and delivers pending alerts. GitHub Actions schedules runs; a dedicated branch stores state via optimistic GitHub Contents API updates.
**Tech Stack:** Python 3.11+ standard library, unittest, GitHub Actions, Discord webhook.
**Spec:** ../specs/2026-10-09-train-alert-design.md

## Global Constraints
- Dates 2026-12-29 and 2026-12-30; stations 1679 → 141; Asia/Bangkok.
- Every 5 minutes best effort; one workflow concurrency group.
- FULL → AVAILABLE alerts, no repeat while available; errors preserve observations.
- Anonymous fresh sessions; no credentials/cookies in logs or repository.
- Pending alerts saved before delivery; sent flag saved only after acknowledgement.
- Fail closed on corrupt/missing established state; explicit initialization only.
- No Firebase, no automated reservation; stop expired departures.

## Review Focus
- Partial results or null counts must not generate false availability transitions (task 1/2).
- Interrupted notification and outdated pending events must not cause stale alerts (task 2).
- Discord errors must not expose webhook URL (task 3).
- Remote state conflicts must abort before sending (task 3).
- Missing secrets, expiry, and unavailable GitHub runner must be visibly distinguished from active monitoring (task 4).

## Task 1: Validated D-Ticket reader
Files: train_alert/dticket.py, train_alert/http.py, tests/test_dticket.py.
Interfaces: Observation dataclass; DTicketClient.check(config, now) -> (observations, errors).
- [ ] Write tests for verified response schema, sleeper filtering, date/station request fields, invalid counts, duplicate IDs, and departure expiry.
- [ ] Run unittest; verify missing implementation failure.
- [ ] Implement HTTP cookie session, bounded timeout/retry, anonymous form POST, view-state refresh, trip/coach parsing.
- [ ] Run tests; then live dry-run both dates and compare output to known UI behavior.
- [ ] Commit task.

## Task 2: Persistent transitions and pending alerts
Files: train_alert/state.py, tests/test_state.py.
Interfaces: fresh_state(config), reconcile(state, observations, errors, now), pending_alerts(state, observations), acknowledge(state, event).
- [ ] Test FULL/AVAILABLE transitions, unchanged silence, error preservation, stale pending cancellation, missing state rejection and expired event handling.
- [ ] Run failing tests.
- [ ] Implement validated JSON state, per-coach keys, pending event IDs, health failure/recovery transitions.
- [ ] Run full suite and commit task.

## Task 3: Delivery, storage, and CLI
Files: train_alert/discord.py, train_alert/storage.py, train_alert/__main__.py, tests/test_delivery.py, tests/test_storage.py, tests/test_run.py, config.json.
Interfaces: Discord.send(event), LocalStore/GitHubStore.load/save/initialize, run_once(client, store, sender, config, now).
- [ ] Test acknowledged vs failed delivery, pending save failure preventing send, GitHub conflict abort, webhook redaction, health alert deduplication.
- [ ] Run failing tests.
- [ ] Implement explicit initialization, atomic local state, GitHub state branch/Contents API with SHA preconditions, dry-run/check/test-discord CLI modes. Reject mismatched config fingerprint.
- [ ] Run full suite; live dry-run; commit task.

## Task 4: Workflow and setup guide
Files: .github/workflows/check-seats.yml, .github/workflows/tests.yml, README.md, .gitignore.
- [ ] Add cron 2-57/5, workflow_dispatch modes, one concurrency group, minimal permissions, workflow enable variable, timeout, Python setup, tests workflow.
- [ ] Document GitHub Secret, explicit state initialization, test notification, enable/disable, expected first result and limitations, local alternative.
- [ ] Run complete tests and CLI checks; review changes with independent reviewer; fix material findings with regression tests.
- [ ] Commit; publish only to user-selected repository; verify hosted dry-run and Discord if configured.

## Execution decision
User requested “ถ้าทำได้ก็ทำเลย ถ้ามีปัญหาอะไรก้แจ้งมาก่อน”: execute inline without another planning approval round. Report blockers immediately; do independent local work while awaiting repository selection. Use a new nested repository because the ancestor repository spans unrelated user files.
