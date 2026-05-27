---
name: alpha-omega-operator
description: Use when managing the Alpha-Omega system end-to-end, including health checks, scans, signal and portfolio operations, deploy verification, runtime triage, and doc-to-code drift control.
---

# Alpha-Omega Operator

**Cursor owns system management** — not Claude. Read `CURSOR-AGENT-BRIEF.md` for the frozen stability stack (do not duplicate health/monitor logic).

## Overview

Operate Alpha-Omega with a safety-first workflow: health before action, guardrails before execution, verification before completion.

This skill is for day-to-day system stewardship, not one-off feature coding.

## AMA (Autonomous Management Agent)

- Code: `core/ama/` — starts on Render via `startup_all()`
- API: `/api/ama/status`, `/api/ama/snapshot`, `/api/ama/run-now`
- Default: `AMA_AUTO_TRADE=false` — observe/alert/fix only, no autonomous trades

## When to Use

Use this skill when the request involves any of:
- Running or supervising scans, autopilot, signal checks, portfolio checks, or dream cycles
- Production troubleshooting (health, memory, monitors, alerts, endpoint slowness)
- Deployment verification and post-deploy validation
- Coordinating backend + frontend + data persistence as one system
- Keeping docs aligned with actual runtime behavior

Do not use this skill for isolated UI tweaks or single-function code edits with no operational impact.

## Non-Negotiable Guardrails

1. Keep execution in paper mode unless user explicitly requests live execution and confirms broker readiness.
2. Treat Signal Tracker and Portfolio as separate systems; do not mix storage/routes/fields implicitly.
3. Respect portfolio constraints in code (slots, risk limits, sector gates, TP/SL invariants).
4. Do not bypass Supabase-first storage abstractions with direct JSON writes unless running fallback behavior already defined in store modules.
5. Never claim a fix without endpoint/runtime verification.

## Operator Workflow

### 1) Preflight

- Read `CLAUDE.md` first.
- Check current backend state quickly:
  - `GET /health`
  - `GET /api/health/full`
  - `GET /api/memory`
  - `GET /api/executor/status`
  - `GET /api/agent/status`
- If core health is degraded, stabilize before feature work.

### 2) Decide Operation Type

- **Scan/selection path**: universe/sector/momentum/scan endpoints
- **Signal path**: `/api/signals/*`
- **Portfolio path**: `/api/portfolio/*`
- **Monitoring path**: `/api/health/*`, `/api/monitor/*`, learning summary, trade history
- **Deploy path**: local checks -> build (if frontend changed) -> push -> verify public endpoints

### 3) Apply Safety Gates

Before acting, confirm:
- Action does not violate risk/slot/sector constraints
- No duplicate concurrent loop is being triggered (check locks/monitor cadence assumptions)
- Any destructive reset/clear path is explicitly requested by user

### 4) Execute + Verify

- Execute smallest safe action first.
- Verify behavior via API response and state deltas (not assumptions).
- For operational changes, verify at least:
  - target endpoint response
  - downstream state store update
  - no regression in health endpoints

### 5) Closeout

- Provide concise operator report:
  - what changed
  - what was verified
  - unresolved risk
  - recommended next check
- If system behavior changed, update canonical docs (`CLAUDE.md`, audit docs) to reduce drift.

## Drift Control Checklist

Run this whenever making infra or runtime changes:
- Docs and code agree on slot/risk thresholds
- Docs and code agree on model names/versions
- Docs and code agree on endpoint list and behavior
- No duplicate routes accidentally introduced
- No secrets hardcoded in tracked files

## Fast Triage Playbook

- **Health endpoint slow/failing**
  - Check parallel check timeouts and whether one dependency is hanging.
- **Portfolio behavior unexpected**
  - Validate gate logic first (sector rank, conviction threshold, TP/SL ordering).
- **Signals not persisting**
  - Confirm Supabase connectivity, then fallback path behavior.
- **Frontend looks stale**
  - Confirm `VITE_API_URL`, rebuild frontend if JSX/CSS changed, then redeploy verify.
- **Autopilot opens poor trades**
  - Inspect momentum pre-screen + conviction thresholds + sector rank gating before changing strategy code.

## Common Mistakes

- Treating Signal Tracker and Portfolio as one shared lifecycle
- Fixing docs only (or code only) and leaving drift unresolved
- Declaring success after local-only checks without public endpoint verification
- Modifying thresholds without checking learning-loop and calibration interactions
- Triggering large scans without chunking/memory guard awareness

## Default Output Format

When finishing an operator task, report with:
- `State`: healthy/degraded
- `Actions`: exact operations run
- `Verification`: endpoints/stores checked
- `Risk`: remaining concern (if any)
- `Next`: single best follow-up action
