# Dataset pipeline

Dataset rows are session-level and retain a pseudonymous subject ID only for grouping. `subject_level_split` assigns all sessions for one subject to one partition, preventing trial/session leakage. Dataset targets are optional and must come from validated research labels or non-clinical performance outcomes.

Synthetic children and synthetic clinical labels are not generated. CSV/JSON export can be added around the row builder; Parquet requires an optional Arrow dependency.
