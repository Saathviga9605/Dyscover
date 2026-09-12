# Stage 6 — Remedial Learning Engine

> **Stage 6 provides educational practice activities. It does not diagnose,
> treat, or clinically evaluate dyslexia.**

This document describes the modular remedial-learning subsystem introduced in
Stage 6 and the exact contractual boundary between *practice* and
*assessment*.

---

## 1. Purpose and boundaries

Stage 6 adds the first learning loop to Dyscover:

    OBSERVE -> DOMAIN PROFILE -> PERSONALIZE -> RECOMMEND PRACTICE
    -> CHILD PRACTICES -> COLLECT ACTIVITY TELEMETRY
    -> UPDATE OBSERVATIONS -> ADAPT FUTURE PRACTICE

It is an **educational-support** subsystem. It:

- recommends practice activities from the child's Stage 5 domain profile;
- runs practice sessions with the child;
- records practice telemetry separately from assessment evidence;
- reports observed practice progress to parents.

It does **not**:

- provide a diagnosis, treatment, or clinical evaluation of dyslexia;
- make claims that practice "improves" or "treats" a condition;
- convert practice data into assessment evidence, clinical evidence, or
  labelled training data;
- use machine learning, reinforcement learning, or any learned model;
- replace or redesign the five Stage 3 assessment games.

## 2. Architecture

```
app/remedial/
    __init__.py   engine/content/schema versions + module mode
    config.py     small, versioned product knobs (no clinical thresholds)
    catalog.py    canonical activity definitions (versioned)
    content.py    minimal versioned stimulus/content pools
    recommend.py  deterministic, explainable selection
    session.py    practice-session lifecycle + structured telemetry
    progress.py   observed practice progress (first-vs-latest, safe)
    routes.py     minimal REST surface (/api/remedial/...)
```

New tables (auto-provisioned by `Base.metadata.create_all`):

- `practice_sessions` — one row per practice session, with `mode='practice'`,
  `activity_id`, `target_domain`, `difficulty`, `activity_version`,
  `content_version`, `config_version`, status lifecycle, timestamps.
- `practice_events` — structured practice telemetry using the shared event
  vocabulary (`event_type`, `timestamp`, `sequence_number`, `payload`,
  `schema_version`), all marked `mode='practice'`.

### 2.1 Learning domains

Stage 6 reuses the Stage 5 domain taxonomy exactly — no new domain categories
are invented:

- `visual-symbol-discrimination`
- `orthographic-recognition`
- `working-memory`
- `attention-visual-search`

The model remains compatible with future literacy/phonics expansion, but Stage 6
does **not** fabricate a phonics or letter-sound domain.

### 2.2 Activity catalog

Each activity is a versioned, enabled practice opportunity targeting one
Stage 5 domain and reusing an existing game as its practice shell.

| activity_id      | display_name     | target_domain               | supporting_game |
|------------------|------------------|-----------------------------|-----------------|
| `symbol-match`   | Symbol Match     | visual-symbol-discrimination| `letter-detective` |
| `word-builder`   | Word Builder     | orthographic-recognition    | `word-flash`       |
| `sequence-recall`| Sequence Recall  | working-memory              | `sequence-quest`   |
| `visual-search`  | Visual Search    | attention-visual-search     | `word-maze`        |

Canonical fields per activity: `activity_id`, `display_name`, `description`,
`target_domain`, `supporting_game`, `supported_difficulty_levels` (1–5),
`age_range` (4–10 as a product/content constraint, not a clinical norm),
`estimated_duration_minutes`, `activity_type` (`"practice"`), required
capabilities, `version`, `enabled`.

New activities are added to the catalog **without** changing selection,
session, or telemetry code.

## 3. Assessment vs practice (critical boundary)

- Every practice artefact carries `mode='practice'`, persisted in a *separate*
  table from assessment evidence.
- `build_child_profile`, `build_game_difficulty`, and
  `build_child_recommendations` read **assessment trials only**. Practice
  telemetry can never shift a child's assessment profile (regression-tested in
  `test_f_practice_never_contaminates_assessment_evidence`).
- Practice data *may* be used for: practice progress reporting, adaptive
  practice difficulty (still via the Stage 5 difficulty engine), activity
  selection, and longitudinal educational tracking.
- Practice data must **never** become diagnostic evidence, clinical evidence,
  or labelled training data. This boundary is enforced by the separate-table
  design and by the observation-only progress language.

## 4. Practice-session model

Status lifecycle: `planned` → `active` → `completed | abandoned`.

- create (planned) → start (records `SESSION_STARTED`, sequence 0) → record
  events (strictly increasing `sequence_number`, schema version `2.0`) →
  complete or abandon (terminal; repeats are rejected with `409`).
- `difficulty` is bounded to 1–5 at creation regardless of input.
- Practice events accept only the canonical event types shared with the
  assessment contract: `SESSION_STARTED`, `SESSION_PAUSED`, `SESSION_RESUMED`,
  `STIMULUS_SHOWN`, `RESPONSE_SUBMITTED`, `TRIAL_TIMEOUT`, `HINT_SHOWN`,
  `SESSION_COMPLETED`, `SESSION_ABANDONED`. Anything else is rejected (400).

## 5. Telemetry

Practicing a trial mirrors two canonical events per trial into practice
telemetry: `STIMULUS_SHOWN` (with the stimulus) and `RESPONSE_SUBMITTED`
(with `response`, `correct`, `reactionTimeMs`). Session boundaries are
recorded by the `start`/`complete`/`abandon` endpoints. No fabricated metrics
are produced: accuracy and timing values come only from recorded responses.

## 6. Activity selection

Deterministic, explainable, versioned, reproducible — no ML recommender, no
reinforcement learning, no unseeded randomness. Priority:

1. **Evidence-backed practice opportunity** — domain profile shows
   `practice_opportunity` with sufficient evidence.
2. **Developing area with sufficient evidence** — category `developing`.
3. **Spaced practice** — the same activity is not recommended again within the
   cooldown window (default 24h).
4. **Balanced/neutral** — when there is no focus signal, the engine selects a
   balanced activity deterministically.

Insufficient or missing evidence is **never framed as a weakness**. The engine
returns a neutral balanced activity (or `no_activity`) with reason language
like "A balanced practice activity for …".

Difficulty for the recommended activity reuses the Stage 5 difficulty engine
via `build_game_difficulty` — no second adaptive algorithm is introduced in
Stage 6.

## 7. Child experience

- Entry point: explorer home → "Let's practise" → practice zone.
- Language is simple, encouragement-led, and age-appropriate (4–10):
  "Let's practise!", "Great job!", "Let's try the next one!",
  "You finished today's practice."
- No diagnostic, risk, probability, severity, ranking, or
  internal-category vocabulary appears anywhere in the child flow
  (enforced by tests on both API and frontend copy).
- Feedback is immediate, simple (correct / retry / encouragement) and never
  claims to improve a condition.

## 8. Parent experience

The parent dashboard gains a **Suggested practice** card showing:

- the next recommended practice activity (parent-safe name) and its reason;
- practice progress: completed sessions, distinct practice activities,
  observed per-activity accuracy ("N% accurate in practice") where enough
  valid data exists.

Language is observation/support oriented. It never shows raw internal
categories, clinical probabilities, diagnostics, or treatment claims, and
never implies *improvement* of a condition. Progress wording is limited to
"practice progress", "observed activity performance", and "recent practice
activity".

## 9. Practice progress

`GET /api/remedial/children/{child_id}/practice/progress` returns:

- totals: sessions attempted / completed / activities completed / available;
- per-activity records (attempts, completed, last completed, observed
  accuracy);
- `first_accuracy_observed` vs `latest_accuracy_observed` **only** when an
  activity has at least two completed sessions with valid responses — a
  single practice session never produces a (misleading) trend;
- a fixed `note` stating progress is observed practice activity only.

Safety rules:

- malformed telemetry is skipped, never used to shift a trend;
- abandoned sessions count as attempts, not completions;
- totals degrade gracefully when nothing has been practised yet.

Notifications: progress data is never presented as diagnostic or clinical.

## 10. API surface (minimal)

| Endpoint | Purpose |
|----------|---------|
| `GET /api/remedial/activities` | catalog (age-filterable via `child_id` or `age`) |
| `GET /api/remedial/children/{child_id}/next-activity` | recommended practice |
| `POST /api/remedial/sessions` | create a practice session (planned) |
| `POST /api/remedial/sessions/{id}/start` | begin practice |
| `POST /api/remedial/sessions/{id}/events` | record a structured practice event |
| `POST /api/remedial/sessions/{id}/complete` | finish practice |
| `POST /api/remedial/sessions/{id}/abandon` | abandon practice |
| `GET /api/remedial/children/{child_id}/practice/progress` | practice progress |

Clear error states: unknown child (404), unknown/inactive activity (404),
unknown session (404), invalid state transition (409), unknown event type
(400). No duplicate assessment or event endpoints were introduced.

## 11. Content versioning

`remedial/__init__.py` exposes `REMEDIAL_ENGINE_VERSION`, `REMEDIAL_CONTENT_VERSION`,
`REMEDIAL_MODE`, and `REMEDIAL_EVENT_SCHEMA_VERSION`, stored on every practice
session. The curated content pools in `content.py` are deterministic tuples so
stimulus families can be swapped and versioned without touching the engine.

## 12. Safety & data quality

Practice telemetry reuses the Stage 5 data-quality stance: evidence is
observation-only, sufficiency thresholds are product/engineering decisions,
and insufficient data causes safe, neutral default behaviour rather than a
strong personalization change.

## 13. Frontend integration

- Reuses `GameEngine`, the supporting game definitions, and the existing game
  views; no assessment-game redesign.
- `PracticeRunner` seeds the engine deterministically from the practice
  session id and starts at the recommended difficulty.
- The practice route `/child/practice` is added; the parent dashboard renders
  `PracticeCard`.
- Accessibility: keyboard-operated buttons with clear focus, readable text,
  adequate tap targets, no colour-only instructions, accessible feedback (role
  status / aria labels), reduced-motion support, responsive layout — no
  regressions were introduced.

## 14. Non-goals (explicit)

No ML, no synthetic labels, no clinical thresholds/probabilities, no
therapeutic claims, no reinforcement learning, no speech remediation, no
pronunciation therapy, no multilingual remediation, no curriculum CMS, no
teacher dashboards, no mobile app, no assessment-game redesign, no rebuild of
Stages 3/4/5, no unnecessary dependencies, no fabricated validation data, and
no broad repository rewrite.

## 15. Future content expansion

Adding a new activity is additive: define it in `catalog.py`, optionally add
curated pools in `content.py`, keep the engine unchanged. A future
literacy/phonics domain can be introduced through the Stage 5 domain taxonomy
and catalog without changing the practice machinery.