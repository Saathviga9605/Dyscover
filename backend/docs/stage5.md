# Stage 5 — Deterministic Personalization Engine

Status: implemented · Engine version `1.0.0` · Schema version `1.0`

## 1. Purpose and boundaries

Stage 5 turns persisted, real assessment observations into transparent,
rule-based personalization. It is **deterministic personalization**, not
machine-learned personalization:

- Every function is a fixed arithmetic rule. The same persisted trials and
  the same configuration always produce the same output.
- No trained models, no probabilities, no risk scores, no percentiles, and
  no clinical vocabulary ("disorder", "impairment", "deficit", "diagnosis",
  "risk", …) appear in any output.
- Categories describe **observed activity only** and are explicitly labeled
  as engineering thresholds, never clinical thresholds.
- Speech and gaze are optional. Personalization works on behavior alone and
  never waits on (or depends on) any speech/gaze ML signal.

## 2. Architecture

```
backend/app/personalization/
├── __init__.py         engine/schema version + mode constant
├── config.py           centralized, frozen, documented thresholds
├── domains.py          canonical domain labels + game→domain mapping
├── evidence.py         evidence sufficiency (no / insufficient / sufficient)
├── skills.py           per-domain skill profile + relative categories
├── difficulty.py       bounded adaptive difficulty (hysteresis)
├── recommendations.py  parent-safe activity suggestions
├── progress.py         per-assessment trends, earliest↔latest comparison
├── service.py          DB orchestration (ObservedTrial joins GameSession)
├── schemas.py          Pydantic response models
└── routes.py           /api/personalization router
```

Data path: persisted `Trial` + `GameSession` rows → `service` → domain
profiles → categories → recommendations / difficulty / progress. Feature
extraction (`app/ml`) remains the source for research features; Stage 5 reads
the same persisted observations directly and additively.

### 2.1 Game → domain mapping (existing domains only)

| Game | Domain |
| --- | --- |
| letter-detective | visual-symbol-discrimination |
| mirror-match | visual-symbol-discrimination |
| word-flash | orthographic-recognition |
| sequence-quest | working-memory |
| word-maze | attention-visual-search |

Domains with games map to the `AssessmentDomain` enum; no new domains were
introduced.

## 3. Skill profile

A profile is a list of per-domain skills:

| Field | Meaning |
| --- | --- |
| `domain`, `label` | canonical domain and display label |
| `evidence_state` | `no_data` \| `insufficient_data` \| `sufficient_data` |
| `category` | `relative_strength` \| `practice_opportunity` \| `developing` \| `insufficient_data` |
| `confidence` | `low` / `medium` based purely on valid-trial sample size |
| `accuracy` | proportion correct among valid (completed) trials |
| `mean_reaction_time_ms` | mean measured reaction time (negative values excluded) |
| `trial_count`, `valid_trial_count`, `completed_trial_count`, `incomplete_trial_count` | evidence transparency |
| `games` | games belonging to this domain |
| `observations` | parent-safe plain-language lines |

## 4. Evidence rules

A trial is *valid* if it was completed and has a correctness value. A timing
sample is additionally excluded if its reaction time is negative.

Sufficiency (all values centralized in `config.py` and returned in every
profile's `config_summary`):

- `minimum_valid_trials = 3`
- `minimum_completed_trials = 2`
- `maximum_error_ratio = 0.50` (design intent; doc)
- `minimum_accuracy_samples = 3`

These are product/engineering decisions, not clinical ones.

## 5. Relative categories

Computed from valid-trial accuracy using non-clinical observed thresholds:

- `accuracy >= 0.80` → `relative_strength`
- `accuracy <= 0.50` → `practice_opportunity`
- between → `developing`
- insufficient evidence → `insufficient_data`

Confidence is `medium` at ≥ 5 valid trials, otherwise `low`. No category is
ever emitted without sufficient evidence.

## 6. Adaptive difficulty

`difficulty.py` produces a level in `1..5` for each game:

- Uses the most recent `min_window_samples = 2` (of `recent_window = 3`)
  completed valid trials.
- `accuracy >= 0.85` → +1; `accuracy <= 0.40` → -1; otherwise held.
- Step is always `±1` and clamps at the domain's `1..5` bounds.
- No evidence → configured safe default (`default_level = 1`).
- The window between thresholds acts as hysteresis, preventing oscillation.
- Every decision carries `previous_level`, `window_size`, `changed`, and a
  parent-safe `reason`.

## 7. Recommendations

Deterministic ordering by category priority
(`practice_opportunity` > `developing` > `relative_strength`) then canonical
game order. Each `game_activity` recommendation includes:

- `game_id`, `target_domain[/label]`, `priority`
- `reason` (parent-safe, observation language, e.g. "Recent activity suggests
  more practice with orthographic recognition activities may be helpful.")
- `suggested_difficulty` from the difficulty engine

With no sufficient evidence the engine emits a single `neutral`
recommendation (e.g. "Completing a few more varied assessment activities will
help."). Recommendations never imply a label, diagnosis, or risk.

## 8. Stimulus uniqueness / spaced practice

Implemented in the frontend engine (`frontend/src/games/engine/stimulusSpacing.ts`):

- `beginTrial` retries `createTrial` (bounded, `maxRetries = 6`) while the
  generated stimulus matches another whose signature appeared within the
  recent window (`recent_window = 4`).
- Signatures are `gameId` + `JSON.stringify(stimulus)`, so identical stimuli
  compare equal while ordering differences do not.
- Retries advance the same seeded RNG, so output remains fully deterministic
  across seeds (`stimulusSpacing.test.ts` verifies determinism and the
  retry loop).

Deliberately uses the existing per-game `createTrial`; when a pool is smaller
than the window the retry bound still guarantees termination without a new
database system.

Retries are purely in-memory inside `beginTrial`: a retried candidate is never
pushed to `engine.trials` and emits no events, and persistence runs later in
the `GameRunner` pipeline. The committed trial count, trial ids, and telemetry
therefore match one per `beginTrial` exactly (regression-tested in
`stimulusSpacing.test.ts`); no duplicate persisted trials or duplicated events
are possible from the spacing loop.

## 9. Progress / trends

`progress.py` returns a time-ordered per-assessment summary of observed
domain accuracy over **completed assessments only**, plus a `comparison` of
the earliest vs latest completed assessment whose domains overlap. Trend
deltas are arithmetic differences only — never a projection or forecast.
Abandoned (`planned`/in-progress) sessions are excluded from progress points
so they cannot shift the earliest/latest comparison (verified on the live
database, where a child with two completed screenings plus several abandoned
sessions showed exactly two points and a comparison). Legacy rows that mix
offset-naive and offset-aware timestamps are normalized to UTC before
sorting (`service._utc_sort_key`).

## 10. Versioning / reproducibility

- `PERSONALIZATION_ENGINE_VERSION = "1.0.0"`,
  `PERSONALIZATION_SCHEMA_VERSION = "1.0"`, mode
  `DETERMINISTIC_OBSERVATION`.
- The active configuration is a frozen dataclass; `config_summary()` is
  returned in profile responses for full auditability.
- Determinism is verified by test (`test_personalization_is_deterministic`).

## 11. API contracts

All under `/api/personalization` (router tags `personalization`),

| Endpoint | Purpose |
| --- | --- |
| `GET /children/{child_id}/profile` | skill/domain profile + evidence + config summary |
| `GET /children/{child_id}/difficulty/{game_id}?current=N` | game-specific difficulty decision |
| `GET /children/{child_id}/recommendations` | ordered parent-safe activity suggestions |
| `GET /children/{child_id}/progress` | per-assessment trends + earliest↔latest comparison |

Requests against an unknown child return `404`. Response models live in
`schemas.py` and are visible in OpenAPI.

Frontend integration (minimal): the parent dashboard renders a
"Practice suggestions" card and a cumulative "Progress" card from these
endpoints, preserving the existing design system. With fewer than two
completed assessments the Progress card shows non-clinical copy ("Complete
another screening to see activity progress over time.") and never draws a
trend; the earliest↔latest arithmetic comparison appears only once two or
more completed assessments exist (see §9). Recommendations render the
parent-safe `target_domain_label` (or a neutral fallback); internal category
identifiers are part of the API contract but are never rendered.

Child-flow difficulty adoption (hardening pass): at each game boundary (the
intro of a new game, never per-trial) the runner fetches
`difficulty/{game_id}` once and seeds that game's starting difficulty. All
five games consume a uniform `1..5` level (`difficultyLevels` and
`DIFFICULTY_BY_GAME` agree), so no game mechanics are redesigned. Fallback is
safe and non-blocking: an API failure, an unknown child, a level the game
cannot express, or insufficient evidence (which returns the configured default
`level 1` by §6) all leave the engine on its existing default. The override
is applied only to a not-yet-started engine with no trials, so an in-progress
session is never disturbed.

## 12. Tests

`backend/tests/test_personalization.py` (22 tests, all pass) covers:
no-data handling, insufficient trials, sufficient observations, category
correctness (strength / practice / developing / mixed), difficulty ±1 moves,
difficulty bounds, hysteresis/no-oscillation, recommendation reasons,
neutral recommendations, invalid-data safety (negative timing, missing
correctness), mixed naive/aware timestamp normalization, completed-only
progress points (abandoned sessions excluded), behavior-only operation
without speech/gaze, determinism, parent-safe language scanning, progress
comparison, versioning/config summary, and safe difficulty defaults.

Frontend focused tests (24 tests): `stimulusSpacing.test.ts` (6) covers
spaced reappearance, signature equivalence, disablement, the retry loop,
determinism, and one-trial-per-`beginTrial` persistence integrity;
`difficulty.test.ts` (4) covers seeded starting difficulty and its adaptation;
`childPersonalization.test.ts` (14) covers difficulty clamping, API-failure
and insufficient-evidence fallback (the child still plays with the default),
the not-yet-started engine guard, first-screening progress copy, and the
recommendation label (never leaking internal category ids).

## 13. Non-goals / limitations

- No ML, no synthetic labels, no forecasting, no clinical claims.
- Categories are not norms and do not compare against age populations.
- Progress requires more than one completed assessment to produce a
  comparison.
- Recommendation language is intentionally conservative and generic.
- Speech/gaze are not yet used by personalization (by design).