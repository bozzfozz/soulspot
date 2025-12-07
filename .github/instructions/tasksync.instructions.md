---
applyTo: '**'
description: 'TaskSync V5 - Terminal-based token optimization. Keep session alive via run_in_terminal between tasks until user enters "stop" or token lifetime expires.'
priority: 100
---

# TaskSync V5 – Terminal-Based Session Management

**CORE PURPOSE:** Optimize token usage by keeping conversation active across multiple tasks. One session = many tasks = single token consumption (vs. individual token waste per task).

**SESSION LIFECYCLE:**
1. **Start:** User provides Task #1 (via chat OR terminal)
2. **Execute:** Agent completes Task #1, respecting copilot-instructions.md patterns
3. **Hold Session:** Agent calls `run_in_terminal` with `read -p "Task #N+1: " task` to request next input
4. **Continue:** User enters Task #2 (or "stop")
5. **Repeat:** Steps 2-4 until user enters "stop" OR token lifetime expires
6. **End:** Session terminates gracefully with summary

**ACTIVATION:** TaskSync is ALWAYS active when this file is loaded. No manual trigger needed.

**TASK COUNTER:** Agent tracks task number internally. First task = #1, after completion request #2, etc.

**MANDATORY AGENT BEHAVIOR:**

### Rule 1: Never End Session Prematurely
- Do NOT end conversation after task completion
- Do NOT say "Let me know if you need anything" or similar closing phrases
- Session ends ONLY by:
  - User entering "stop" in terminal
  - Token lifetime expiring (auto-cutoff)

### Rule 2: Request Next Task via Terminal
- After completing Task #N, immediately call `run_in_terminal`
- Use: `read -p "🤖 Task #N+1 > " task_input`
- Wait for user input (DO NOT guess or proceed without input)
- Keep conversation open while waiting

### Rule 3: Terminal Input is Gateway to Session Continuation
- Terminal prompt = Session stays alive
- Terminal input = Next task begins
- Without terminal prompt = Session ends (wasteful)

### Rule 4: Parse Special Commands
```
"stop"   → Terminate gracefully, show session summary
"status" → Report current task count and metrics (then request next task)
"help"   → Show available commands (then request next task)
<task>   → Execute task normally
```

### Rule 5: Respect Core Patterns
- Follow all code patterns from copilot-instructions.md (Sections 1-15)
- Architecture layers: API → App → Domain ← Infrastructure
- Port-Repository sync, testing, documentation, quality gates
- TaskSync is meta-layer (session management), not code guidance

**TOKEN OPTIMIZATION MATH:**
```
Without TaskSync:
- 50 separate tasks = 50 separate sessions = 50× token consumption = $$$

With TaskSync:
- 50 tasks in one session = 1 session = 1× token consumption
- Token stays alive across all tasks until expiry or "stop"
- Result: ~99% cost reduction for multi-task workflows
```

**SESSION SUMMARY (shown at termination):**
```
═══════════════════════════════════
  TaskSync Session Summary
───────────────────────────────────
  Tasks Completed: #N
  Duration: X seconds
  Avg per Task: Y seconds
  Termination: "stop" OR token-expired
  Status: ✅ Complete
═══════════════════════════════════
```

**TOKEN LIFETIME TERMINATION:**
- Session continues until user enters "stop" OR token lifetime expires (whichever comes first)
- No manual action needed for token expiry – conversation ends automatically
- Final summary is shown regardless of termination trigger