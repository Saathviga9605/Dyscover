from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

class BaselineModel(ABC):
    model_type: str
    def __init__(self, feature_names: list[str]) -> None:
        self.feature_names = feature_names
        self.pipeline: Any = None
    @abstractmethod
    def build(self) -> Any: ...
    def fit(self, rows: list[dict[str, Any]], labels: list[int]) -> None:
        matrix = [[row["features"].get(name) for name in self.feature_names] for row in rows]
        if len(set(labels)) < 2:
            raise ValueError("At least two validated target classes are required for training")
        self.pipeline = self.build()
        self.pipeline.fit(matrix, labels)
    def predict(self, rows: list[dict[str, Any]]) -> list[int]:
        if self.pipeline is None: raise RuntimeError("Model is not trained")
        matrix = [[row["features"].get(name) for name in self.feature_names] for row in rows]
        return self.pipeline.predict(matrix).tolist()
    def predict_proba(self, rows: list[dict[str, Any]]) -> list[list[float]]:
        if self.pipeline is None: raise RuntimeError("Model is not trained")
        matrix = [[row["features"].get(name) for name in self.feature_names] for row in rows]
        return self.pipeline.predict_proba(matrix).tolist()

class LogisticBaseline(BaselineModel):
    model_type = "logistic_regression"
    def build(self) -> Any:
        try:
            from sklearn.impute import SimpleImputer
            from sklearn.linear_model import LogisticRegression
            from sklearn.pipeline import Pipeline
            from sklearn.preprocessing import StandardScaler
        except Exception as error:
            raise RuntimeError(f"scikit-learn runtime unavailable: {error}") from error
        return Pipeline([("imputer", SimpleImputer(strategy="median")), ("scale", StandardScaler()), ("model", LogisticRegression(max_iter=1000, random_state=42))])

class RandomForestBaseline(BaselineModel):
    model_type = "random_forest"
    def build(self) -> Any:
        try:
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.impute import SimpleImputer
            from sklearn.pipeline import Pipeline
        except Exception as error:
            raise RuntimeError(f"scikit-learn runtime unavailable: {error}") from error
        return Pipeline([("imputer", SimpleImputer(strategy="median")), ("model", RandomForestClassifier(n_estimators=100, random_state=42, class_weight="balanced"))])

class GradientBoostingBaseline(BaselineModel):
    model_type = "gradient_boosting"
    def build(self) -> Any:
        try:
            from sklearn.ensemble import GradientBoostingClassifier
            from sklearn.impute import SimpleImputer
            from sklearn.pipeline import Pipeline
        except Exception as error:
            raise RuntimeError(f"scikit-learn runtime unavailable: {error}") from error
        return Pipeline([("imputer", SimpleImputer(strategy="median")), ("model", GradientBoostingClassifier(random_state=42))])
