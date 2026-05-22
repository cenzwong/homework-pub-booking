# Ex7 — Handoff bridge

## Your answer

The `HandoffBridge` orchestrates bidirectional round-trips between the LLM-backed loop half and the deterministic structured half. Each round:
1. The bridge executes the `loop_half` using the current input task, which generates subgoals and invokes tools to identify candidate booking details.
2. If the loop agent determines it is ready to book, it returns `next_action="handoff_to_structured"`. The bridge catches this, constructs a forward handoff payload containing the booking parameters (venue, date, time, party size, deposit) using `build_forward_handoff`, and writes it to the structured half's IPC mailbox.
3. The bridge updates the session state via `append_trace_event` with a `session.state_changed` event (from `loop` to `structured`) and invokes `structured_half.run()`.
4. If the structured half approves, the booking is confirmed and marked complete.
5. If the structured half rejects or escalates (returning `next_action="escalate"`), the bridge constructs a new "reverse task" using `build_reverse_task` that contains the prior proposal and the rejection reason. It logs the transition back (from `structured` to `loop` along with the `rejection_reason`), cleans up and archives the stale forward handoff file to `logs/handoffs/`, and loops back for another round.

In our actual offline integration session `sess_ab4cb70be2c5`, the structured half had to deal with the Rasa webhook being offline, resulting in the rejection reason `"rasa unreachable: <urlopen error [Errno 61] Connection refused>"`. The bridge successfully processed this escalation in Round 1, rewrote the task to notify the loop agent of the network failure, and routed it back to the loop. In Round 2, the loop agent adjusted its search and re-proposed a group booking at "The Royal Oak", illustrating the seamless back-and-forth orchestration.

## Citations

- starter/handoff_bridge/bridge.py — `HandoffBridge.run` and state-changed orchestration logic
- sessions/examples/ex7-handoff-bridge/sess_ab4cb70be2c5/logs/trace.jsonl — traces demonstrating round transitions, state changes, and rejections
- sessions/examples/ex7-handoff-bridge/sess_ab4cb70be2c5/logs/tickets/tk_21e10234/raw_output.json — first loop planner subgoal ticket
- sessions/examples/ex7-handoff-bridge/sess_ab4cb70be2c5/logs/tickets/tk_f1ff2634/raw_output.json — loop executor executing forward handoff
