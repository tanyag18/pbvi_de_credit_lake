# PBVI Task Runner — Execute Next Pending Task

You are executing the next pending PBVI build task. Follow these steps exactly.

## Step 1 — Read current session state

Read `SESSION_LOG.md` in the project root (or `sessions/` directory).
- Identify which session is currently active (status = IN PROGRESS or OPEN).
- List all tasks in that session with their status.

If `SESSION_LOG.md` does not exist or no session is active:
```
ERROR: No active session found in SESSION_LOG.md. Start a session first.
```
Stop here.

## Step 2 — Determine the next pending task

Find the first task in the active session that is NOT marked COMPLETE (or PASS/COMMITTED).

If all tasks in the active session are complete:
```
═══════════════════════════════════════════
SESSION {n} — ALL TASKS COMPLETE
═══════════════════════════════════════════
Completed: {list of task IDs}

NEXT STEPS:
  1. Run session integration check
  2. Update SESSION_LOG.md status to COMPLETE
  3. Raise PR: session/s{n}_{desc} → main
═══════════════════════════════════════════
```
Stop here.

## Step 3 — Confirm the previous task is committed

If the next pending task is NOT the first task in the session, check that the immediately preceding task is marked COMPLETE.

If the preceding task is not complete:
```
ERROR: Previous task S{n}.T{m} is not yet complete.
Verify and commit it before proceeding to the next task.
```
Stop here.

## Step 4 — Extract the CC prompt from EXECUTION_PLAN.md

Read `EXECUTION_PLAN.md` (check project root, then `docs/`).
Find the section for the next pending task.
Extract ONLY the **CC Prompt** content for that task.

Also extract and display:
- **Task description** (one line)
- **Invariant flags** (which invariants this task touches — if any)
- **Verification command** (what to run after the task completes)

## Step 5 — Display task briefing, then execute

Let TASK_ID = the determined next pending task.

Print:
```
═══════════════════════════════════════════
PBVI TASK: {TASK_ID} (auto-detected next)
═══════════════════════════════════════════
Session:     {session name}
Progress:    {completed}/{total} tasks done
Description: {task description}
Invariants:  {invariant flags or "None"}
═══════════════════════════════════════════
```

Then execute the CC prompt — do the work it describes.

After completing the work, print:
```
═══════════════════════════════════════════
TASK {TASK_ID} — WORK COMPLETE
═══════════════════════════════════════════
Verification command:
  {verification command from execution plan}

NEXT STEPS (your responsibility):
  1. Read the generated code before running anything
  2. Write your prediction in VERIFICATION_RECORD.md
  3. Run the verification command above
  4. Compare result against your prediction
  5. If PASS → commit with: [{TASK_ID}] add: {brief description}
  6. If FAIL → fix and re-verify before committing
  7. Update SESSION_LOG.md with task status
  8. Then run /project:run_next for the next task
═══════════════════════════════════════════
```

## Rules

- Do NOT skip the previous-task-committed check (Step 3).
- Do NOT auto-run verification commands — the engineer must run them after writing predictions.
- Do NOT modify SESSION_LOG.md or VERIFICATION_RECORD.md — those are engineer responsibilities.
- If the task prompt conflicts with Claude.md, stop and flag: `INVARIANT CONFLICT: [INV-XX] — {description}`.
- Read Claude.md before executing any task prompt. Claude.md is the execution contract.
