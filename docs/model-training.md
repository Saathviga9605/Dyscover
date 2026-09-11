# Model training

Three scikit-learn baselines are available as offline interfaces: logistic regression, random forest, and gradient boosting. They use imputation where feature values are unavailable; training rejects single-class labels. No model is trained or registered in this repository because no validated labeled dataset is present.

Training must record feature schema, dataset version, model version, seed, parameters, and evaluation configuration before a model can move from unavailable to research status.
