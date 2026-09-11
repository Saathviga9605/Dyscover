# System overview

Dyscover is split into a React client and a FastAPI service. The client owns presentation, accessibility, route composition, and game adapters. The service owns validated API boundaries and persistence. PostgreSQL is the target database; SQLite is available as a development fallback.

The assessment path is `ChildProfile -> AssessmentSession -> GameSession -> Trial -> InteractionEvent`, with optional `GazeSample` and `Fixation` records and derived `FeatureVector` records. There is no prediction model in Stage 1.

## Boundaries

- Games emit typed callbacks and do not mutate global application state.
- Gaze providers emit samples through a provider-neutral interface.
- Research features are stored as named values and require future validation before interpretation.
- Public and child routes do not load camera or ML resources.
