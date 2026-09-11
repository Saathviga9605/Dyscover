# Data model

The normalized model stores `User`, `ChildProfile`, `AssessmentSession`, `GameSession`, `Trial`, and `InteractionEvent`. Research extensions are `GazeSample`, `Fixation`, and one `FeatureVector` per trial. UUID primary keys and timestamps are used throughout. Trial number is unique within a game session.

Feature vectors are JSON objects keyed by feature names because the research schema will evolve. They are descriptive data, not clinical measurements.
