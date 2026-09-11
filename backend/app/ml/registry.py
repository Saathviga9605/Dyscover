from .schemas import ModelInfo

MODELS = [
    ModelInfo(model_id="behavior-logistic-v1", model_name="Behavior Logistic Baseline", model_type="logistic_regression", version="1.0", feature_schema_version="1.0", status="unavailable", training_status="unavailable", algorithm="logistic_regression", hyperparameters={"max_iter": 1000}),
    ModelInfo(model_id="behavior-forest-v1", model_name="Behavior Random Forest Baseline", model_type="random_forest", version="1.0", feature_schema_version="1.0", status="unavailable", training_status="unavailable", algorithm="random_forest", hyperparameters={"n_estimators": 100, "class_weight": "balanced"}),
    ModelInfo(model_id="behavior-boosting-v1", model_name="Behavior Gradient Boosting Baseline", model_type="gradient_boosting", version="1.0", feature_schema_version="1.0", status="unavailable", training_status="unavailable", algorithm="gradient_boosting", hyperparameters={}),
]

def list_models() -> list[ModelInfo]: return MODELS

def get_model(model_id: str) -> ModelInfo | None: return next((model for model in MODELS if model.model_id == model_id), None)
