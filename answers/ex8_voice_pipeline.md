# Ex8 — Voice pipeline

## Your answer

The voice pipeline supports two modes of interaction under a unified event-logging contract: text-only mode and voice-interactive mode. In text mode (`run_text_mode`), the system captures input from standard input and processes the dialogue with the Scottish pub manager persona (Alasdair) backed by the LLM. In voice mode (`run_voice_mode`), the mic captures local PCM audio, sends it to the Speechmatics Realtime WebSockets API for speech-to-text (STT) transcription, processes it with the pub manager's dialogue model, and synthesizes speech playback via Rime.ai's Arcana TTS engine. 

The primary design principle is **graceful degradation**. If `SPEECHMATICS_KEY` or the required `speechmatics-python`/`sounddevice` libraries are missing, `run_voice_mode` logs a warning and gracefully falls through to the stdin text mode transport. Similarly, if `RIME_API_KEY` is not found, it runs speech input normally but prints Alasdair’s responses textually instead of speaking them. This ensures the agent is extremely robust across varied developer setups and automated test suites.

Regardless of transport, both modes emit uniform `voice.utterance_in` (user turn) and `voice.utterance_out` (manager turn) trace events to the session log, capturing the `{text, turn, mode}` payload. In our local test run (session `sess_142ac23af4c5`), the agent executed a successful 6-turn text mode conversation starting with turn 0 (User: `"hi"`, Manager: `"What can I do for ye? Booking inquiry, I suppose?"`), and gracefully concluded at turn 5 when a party of 2 was approved. Since both transport modes output identical trace event schemas, downstream verification remains completely consistent.

## Citations

- starter/voice_pipeline/voice_loop.py — `run_voice_mode`, `run_text_mode`, and degradation fallbacks
- sessions/homework/ex8/sess_142ac23af4c5/logs/trace.jsonl — conversation trace containing `voice.utterance_in` and `voice.utterance_out` logs spanning 6 turns
- sessions/homework/ex8/sess_8e2d34329c98/logs/trace.jsonl — alternative text-mode conversation trace recording a fully committed booking
