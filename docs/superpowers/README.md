# Superpowers — Alpha-Omega Development Plans

This directory stores implementation plans created by the Superpowers `writing-plans` skill.

## How plans work

1. Before implementing any feature, invoke the `brainstorming` skill to produce a design
2. Once design is approved, invoke the `writing-plans` skill to produce a plan
3. Save the plan here as: `plans/YYYY-MM-DD-<feature-name>.md`
4. Execute with `subagent-driven-development` or `executing-plans`

## Plan naming convention

```
plans/2026-05-06-supabase-migration.md
plans/2026-05-10-circuit-breakers.md
plans/2026-05-15-xai-thesis-generation.md
```

## Current feature backlog (from PRD)

Priority order:
1. **Supabase migration** — persistent signals storage (replaces ephemeral JSON on Render)
2. **Circuit breakers** — auto-shutdown if drawdown > 15%
3. **XAI thesis** — human-readable explanation for every signal
4. **Sharpe/drawdown reporting** — live KPI dashboard
5. **Paper trading audit** — 6-month pre-live validation framework

When starting any of these, follow the full superpowers workflow documented in COWORK-SKILLS.md.
