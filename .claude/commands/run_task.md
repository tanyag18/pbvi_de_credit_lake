# PBVI Task Runner — Execute Specific Task

You are executing a PBVI build task. Follow these steps exactly.

## Step 1 — Identify the task

The engineer has requested task: **$ARGUMENTS**

If `$ARGUMENTS` is empty or does not match the pattern `S{n}.T{n}` (e.g. S1.T3, S2.T1), respond with:
```
ERROR: Provide a task ID. Usage: /project:run_task S1.T3
```
Stop here.

## Step 2 — Read current session state

Read `SESSION_LOG.md` in the project root (or `sessions/` directory).
- Identify which session is currently active (status = IN PROGRESS or OPEN).
- Identify which tasks in that session are already COMPLETE.
- Identify the next pending task in that session.

If `SESSION_LOG.md` does not exist or no session is active:
```
ERROR: No active session found in SESSION_LOG.md. Start a session first.
```
Stop here.

## Step 3 — Validate the task belongs to the current session

Extract the session number from the requested task ID (e.g. S1.T3 → Session 1).

If the requested task's session does not match the active session:
```
ERROR: Task $ARGUMENTS belongs to Session {n}, but the active session is Session {m}.
Cannot run tasks from a different session.
```
Stop here.

## Step 4 — Check task ordering

If the requested task is NOT the next pending task (i.e. earlier tasks in this session are still incomplete):
```
WARNING: Task $ARGUMENTS is not the next pending task.
Next pending task is S{n}.T{m}.
Previous tasks must be verified and committed before proceeding.

Continue anyway? This violates PBVI one-task-at-a-time discipline.
```
Wait for engineer confirmation before proceeding.

## Step 5 — Extract the CC prompt from EXECUTION_PLAN.md

Read `EXECUTION_PLAN.md` (check project root, then `docs/`).
Find the section for task `$ARGUMENTS`.
Extract ONLY the **CC Prompt** content for that task.

Also extract and display:
- **Task description** (one line)
- **Invariant flags** (which invariants this task touches — if any)
- **Verification command** (what to run after the task completes)

## Step 6 — Display task briefing, then execute

Print:
```
═══════════════════════════════════════════
PBVI TASK: $ARGUMENTS
═══════════════════════════════════════════
Description: {task description}
Invariants:  {invariant flags or "None"}
═══════════════════════════════════════════
```

Then execute the CC prompt — do the work it describes.

After completing the work, print:
```
═══════════════════════════════════════════
TASK $ARGUMENTS — WORK COMPLETE
═══════════════════════════════════════════
Verification command:
  {verification command from execution plan}

NEXT STEPS (your responsibility):
  1. Read the generated code before running anything
  2. Write your prediction in VERIFICATION_RECORD.md
  3. Run the verification command above
  4. Compare result against your prediction
  5. If PASS → commit with: [$ARGUMENTS] add: {brief description}
  6. If FAIL → fix and re-verify before committing
  7. Update SESSION_LOG.md with task status
═══════════════════════════════════════════
```

## Rules

- Do NOT skip the session validation (Step 3).
- Do NOT auto-run verification commands — the engineer must run them after writing predictions.
- Do NOT modify SESSION_LOG.md or VERIFICATION_RECORD.md — those are engineer responsibilities.
- If the task prompt conflicts with Claude.md, stop and flag: `INVARIANT CONFLICT: [INV-XX] — {description}`.
- Read Claude.md before executing any task prompt. Claude.md is the execution contract.
