# PBVI Session Status

Show the current state of the active PBVI build session.

## Instructions

Read `SESSION_LOG.md` in the project root (or `sessions/` directory).
Read `EXECUTION_PLAN.md` (check project root, then `docs/`).

Print:
```
═══════════════════════════════════════════
PBVI SESSION STATUS
═══════════════════════════════════════════
Active session:  S{n} — {session name}
Branch:          session/s{n}_{desc}
Progress:        {completed}/{total} tasks

TASKS:
  {TASK_ID}  {description (short)}  {status}
  {TASK_ID}  {description (short)}  {status}
  ...

Next pending:    {TASK_ID or "ALL COMPLETE"}
═══════════════════════════════════════════
```

For status, use:
- ✅ COMPLETE — task verified and committed
- ⏳ PENDING — not yet started
- 🔄 IN PROGRESS — started but not committed
- ❌ FAILED — last verification failed

If no SESSION_LOG.md exists or no active session:
```
No active session. Create SESSION_LOG.md and VERIFICATION_RECORD.md
before starting Phase 6 build.
```
