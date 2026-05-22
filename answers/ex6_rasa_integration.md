# Ex6 — Rasa structured half

## Your answer

The `RasaStructuredHalf` integrates sovereign-agent with a Rasa CALM-backed booking workflow. The integration handles a robust data flow from the loop agent to Rasa: the loop half provides raw handoff parameters (e.g. venue name, date, time, party size, deposit), which are validated and canonicalised using `normalise_booking_payload` (housed in `starter/rasa_half/validator.py`). This converts human-entered strings into robust, standard types—such as ISO-8601 dates ("2026-04-25"), 24-hour time strings ("19:30"), and clean lower-snake-case venue identifiers ("the_royal_oak"). The structured half then executes a `urllib` POST request to the Rasa REST webhook, parses the returned JSON payload, and scans the messages for custom slot structures (i.e. `{"action": "committed"}` or `{"action": "rejected"}`).

To allow deterministic testing without a live license, we developed an offline mock server using Python’s standard `ThreadingHTTPServer` library. This mock server parses booking payloads and implements the exact same rules as the real ActionValidateBooking service (e.g., rejecting bookings where party size is greater than 8, or where the deposit exceeds £300, and confirming valid ones with a BK-prefix SHA-1 reference).

Three crucial design decisions shape this implementation:
1. **Defensive Error Handling**: Any `ValidationFailed` exception raised during normalisation is caught in `run()` and returned as an escalation rather than crashing the process, matching the `HalfResult` contract.
2. **Stable Dialogue Trackers**: The webhook `sender` parameter is set to a stable hash of the venue, date, and time. This ensures that the Rasa tracker state remains consistent across retry attempts within a single session.
3. **Resilience to Network Glitches**: HTTP and URL connection errors are caught gracefully, mapping to `SA_EXT_SERVICE_UNAVAILABLE` with `success=False` so the calling orchestrator can make an informed retry or recovery choice.

## Citations

- sessions/examples/ex6-rasa-half/sess_59d96dd2e0c3/logs/rasa/rasa_server.log — Rasa core server logs detailing session execution, CALM flow status, and confirmation messages
- sessions/examples/ex6-rasa-half/sess_59d96dd2e0c3/logs/rasa/rasa_actions.log — Rasa action server logs detailing validation and action execution results
- starter/rasa_half/validator.py — `normalise_booking_payload` and canonical validators
- starter/rasa_half/structured_half.py — `RasaStructuredHalf.run`, network error handlers, and the mock Rasa webhook server
