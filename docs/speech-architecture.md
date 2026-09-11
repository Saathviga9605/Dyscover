# Stage 4 speech and reading infrastructure

Stage 4 adds an optional `backend/app/speech` subsystem. Its provider boundary is `SpeechProvider`; the default provider is explicitly `NOT_CONFIGURED` and never pretends to transcribe audio.

The deterministic pipeline is:

`ReadingTask -> Transcript -> expected-text alignment -> reading features + text features -> existing ML feature registry`.

Alignment reports matched words, substitutions, omissions, insertions, repetitions, and order differences. Fluency features require real duration or word timestamps. Missing audio, transcript, timestamps, or expected text remain unavailable rather than becoming zero.

Speech features are observable research/educational features. They are not diagnostic biomarkers. Raw audio is not accepted by the Stage 4 API and is not stored in feature vectors. Future providers may reference controlled audio storage without changing the transcript/alignment contract.

## Current APIs

- `GET /api/speech/status`
- `POST /api/speech/analyze`
- `POST /api/speech/sessions`
- `GET /api/speech/sessions/{speech_session_id}`

No provider, cloud API key, speech model, pronunciation model, or clinical speech classifier is configured.

Speech sessions store only assessment/trial references, task metadata, language, provider metadata, duration, and an `audio_available` flag. They do not accept raw audio blobs.