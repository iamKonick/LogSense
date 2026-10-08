"""Portable sklearn-compatible XGBoost adapter with public severity labels."""

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier


class SeverityXGBoost(ClassifierMixin, BaseEstimator):
    def __init__(self, random_state=42, n_estimators=100, max_depth=4):
        self.random_state = random_state
        self.n_estimators = n_estimators
        self.max_depth = max_depth

    def fit(self, X, y):
        self.encoder_ = LabelEncoder().fit(y)
        self.classes_ = self.encoder_.classes_
        self.model_ = XGBClassifier(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=0.1,
            objective="multi:softprob",
            eval_metric="mlogloss",
            tree_method="hist",
            n_jobs=2,
            random_state=self.random_state,
        )
        self.model_.fit(X, self.encoder_.transform(y))
        self.n_features_in_ = X.shape[1]
        return self

    def predict_proba(self, X):
        return self.model_.predict_proba(X)

    def predict(self, X):
        return self.encoder_.inverse_transform(np.argmax(self.predict_proba(X), axis=1))
