# Stage 3 ML architecture

Stage 3 adds an isolated research subsystem under `backend/app/ml`. Its flow is:

`AssessmentSession -> Trial/Event validation -> Feature extraction -> Dataset rows -> subject-level split -> offline baseline training -> registry -> optional inference -> screening profile`.

The current installation has no validated labeled dataset, so registered models are `unavailable`. The profile API returns observed task performance and limitations without inventing predictions or clinical labels.

Feature values carry name, unit, source, domain, availability, and extraction/calculation versions. Missing gaze or speech remains unavailable rather than being replaced with zero.
