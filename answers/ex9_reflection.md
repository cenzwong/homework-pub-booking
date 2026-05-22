# Ex9 — Reflection

## Q1 — Planner handoff decision

### Your answer

In my actual Ex7 run (session `sess_ab4cb70be2c5`), the planner generated subgoal `sg_1` ("find venue near haymarket for 12") under ticket `tk_21e10234` with `assigned_half: "loop"`. While the planner delegated the initial research task to the LLM-backed loop half, the transition to the structured half was triggered dynamically by the loop agent in turn 2 (ticket `tk_f1ff2634`) calling the `handoff_to_structured` tool. The prose signal driving the structured assignment arose from the goal of validating the booking parameters under deterministic constraints (like party size and deposit limits) which are standard policy rules.

This routing decision is advisory rather than physical. The orchestrator delegates execution to the structured half only because both halves are registered in the bridge. If the structured half were missing, any subgoal or handoff routed to it would fail silently or raise an error, dropping the request into the void. This highlights a critical architectural lesson: LLM planners rely on natural language descriptions to assign subgoals, which can lead to mis-assignment or dead-ends if routing is fuzzy. To avoid these routing failures, core policy rules must be hardcoded in Python within the structured half, rather than relying on the LLM's interpretation of prose.

### Citation

- sessions/examples/ex7-handoff-bridge/sess_ab4cb70be2c5/logs/tickets/tk_21e10234/raw_output.json — first planner subgoal assignment
- sessions/examples/ex7-handoff-bridge/sess_ab4cb70be2c5/logs/tickets/tk_f1ff2634/raw_output.json — executor executing `handoff_to_structured`
- sessions/examples/ex7-handoff-bridge/sess_ab4cb70be2c5/logs/trace.jsonl — round 1 transition from `loop` to `structured`

---

## Q2 — Dataflow integrity catch

### Your answer

During my Ex5 run (session `sess_e53d0f559056`), the dataflow integrity check `verify_dataflow` verified the generated `workspace/flyer.md` which claimed a total of "£973" and a deposit of "£195". These figures matched the outputs returned by the `calculate_cost` tool in turn 3 exactly, yielding `ok=True`. During development and testing of the integrity check, we planted a fabricated value of "£9999" (or a rule-threshold value of "£300" that didn't originate from a tool output) to test calibration. 

The integrity check successfully returned `ok=False` with `unverified_facts=['£9999']`. Because the LLM-generated flyer prose could easily include plausible-sounding but completely fabricated numbers (such as an incorrect deposit fee), a human reviewer skimming the flyer would likely overlook the error. The automated `verify_dataflow` check successfully prevented this by comparing all monetary, temperature, and condition facts in the final flyer text against the ground-truth logs in `_TOOL_CALL_LOG`. The core lesson is that dialogue validation must be grounded in actual tool invocation records rather than grammatical correctness or plausibility.

### Citation

- sessions/examples/ex5-edinburgh-research/sess_e53d0f559056/workspace/flyer.md — containing the validated total of £973 and deposit of £195
- sessions/examples/ex5-edinburgh-research/sess_e53d0f559056/logs/trace.jsonl — showing `calculate_cost` returning total £973 and deposit £195 in turn 3
- starter/edinburgh_research/integrity.py — the `verify_dataflow` function comparing facts against `_TOOL_CALL_LOG`

---

## Q3 — Removing one framework primitive

### Your answer

If forced to strip the framework down to its absolute foundation, I would retain **Session Directories** (Decision 1) and sacrifice all other primitives. Without dedicated session directories, the system loses its physical boundary of isolation. The primary failure mode of removing session directories is **cross-tenant data leakage and state corruption**. If multiple concurrent agents write to a shared workspace or common directory, their files, handoffs, and temporary artifacts would overwrite each other, causing the LLM to read stale context from another session and execute catastrophic actions (such as booking the wrong venue for the wrong user).

Session directories are the bedrock of the entire sovereign-agent architecture. They serve as the source of truth for execution traces, tickets, and workspace isolation, acting much like git commits. While we could easily rebuild atomic IPC (Decision 5), ticket structures (Decision 3), and forward-only states (Decision 2) as flat files inside a directory, we cannot rebuild session isolation without directories. Losing session directories turns session debugging into untraceable archaeology.

### Citation

- sessions/examples/ex5-edinburgh-research/sess_e53d0f559056/ — isolating the entire Ex5 research workspace and execution logs
- sessions/examples/ex7-handoff-bridge/sess_ab4cb70be2c5/ — isolating the multi-round Ex7 handoff IPC and audit history
