# Stage 2 assessment engine

Stage 2 uses one `GameEngine` for the full assessment plan:

1. Letter Detective
2. Mirror Match
3. Word Flash
4. Sequence Quest
5. Word Maze

Definitions generate stimuli and evaluate responses. The engine owns session state, trial lifecycle, monotonic timing, event sequence numbers, scoring summaries, pause/resume, completion, and difficulty progression.

## Event contract

Events use `eventId`, `sessionId`, optional `trialId`, `gameId`, wall-clock `timestamp`, monotonic `performanceTime`, `eventType`, `sequenceNumber`, `payload`, and `schemaVersion`. Meaningful events include session/game/trial lifecycle, option selection, response submission, timeouts, hints, errors, and completion. Raw pointer movement is not collected.

## Timing

Wall-clock timestamps support persistence and audit. `performance.now()` values support reaction and presentation durations. UI code never derives behavioral timing from render timestamps.

## Difficulty

The deterministic `DifficultyManager` looks at the last three completed trials. Accuracy of at least 80% with measured responses below five seconds increases difficulty; accuracy of 34% or lower, or three errors in a recent trial, decreases it; otherwise difficulty is held. It is a configurable rule system, not an ML model.

## Persistence and resilience

Trials and events are serialized at the API boundary and sent through the existing FastAPI service. Failed writes are kept in a small local queue and replayed against their original route. The core games work without camera permission; gaze remains an optional future signal provider.

## Interpretation boundary

Results preserve raw stimulus, response, timing, attempts, errors, difficulty, and meaningful events. Game summaries expose task performance only: accuracy, completion, reaction time, error rate, difficulty progression, and hints. No score is converted into a dyslexia probability or diagnosis.
