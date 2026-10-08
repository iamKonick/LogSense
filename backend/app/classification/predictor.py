"""Trusted local model bundles only; no uploaded executable model files."""

import re

import joblib
import numpy as np
from app.domain.models import PRIORITIES, Event, Prediction


def distribution(model, message):
    values = model.predict_proba([message])[0]
    return {p: float(values[list(model.classes_).index(p)]) for p in PRIORITIES}


def decide(probabilities):
    # A tied probability selects the higher severity; no hidden severity override.
    return max(PRIORITIES, key=lambda p: (probabilities[p], p))


class Predictor:
    def __init__(self, path="", review_threshold=0.6):
        self.bundle = None
        self.threshold = review_threshold
        self.metadata = {
            "mode": "rule_fallback",
            "version": "rules-v1",
            "reason": "No trained model configured",
            "confidence_calibrated": False,
        }
        if path:
            self.bundle = joblib.load(path)
            if self.bundle.get("format") not in ("logsense-v1", "logsense-v2"):
                raise ValueError("Incompatible LogSense model bundle")
            for model in [*self.bundle["models"].values(), self.bundle["stacking"]]:
                if set(model.classes_) != set(PRIORITIES):
                    raise ValueError("Every serving model must expose P1–P5 classes")
            if self.bundle["format"] == "logsense-v2" and self.bundle["metadata"].get(
                "selected_model"
            ) not in {*self.bundle["models"], "soft_voting", "stacking"}:
                raise ValueError("Bundle has no valid selected candidate")
            self.metadata = self.bundle["metadata"] | {
                "mode": "trained_selected"
                if self.bundle["format"] == "logsense-v2"
                else "trained_ensemble",
                "confidence_calibrated": False,
            }

    def predict(self, event: Event) -> Prediction:
        if not self.bundle:
            levels = {
                "TRACE": "P1",
                "DEBUG": "P1",
                "INFO": "P2",
                "INFORMATION": "P2",
                "NOTICE": "P2",
                "WARN": "P3",
                "WARNING": "P3",
                "ERROR": "P4",
                "ERR": "P4",
                "CRITICAL": "P5",
                "FATAL": "P5",
                "EMERG": "P5",
                "ALERT": "P5",
            }
            priority = levels.get(event.source_level)
            if priority is None:
                priority = "P2"
                for p, pattern in [
                    ("P5", r"\b(panic|out of memory|data corruption|kernel crash)\b"),
                    ("P4", r"\b(failed|failure|exception|refused|unavailable)\b"),
                    ("P3", r"\b(timeout|retry|slow|degraded)\b"),
                ]:
                    if re.search(pattern, event.message, re.IGNORECASE):
                        priority = p
                        break
            return Prediction(priority=priority, mode="rule_fallback", needs_review=True)
        individual = {
            name: distribution(model, event.message)
            for name, model in self.bundle["models"].items()
        }
        voting = {p: float(np.mean([x[p] for x in individual.values()])) for p in PRIORITIES}
        stacking = distribution(self.bundle["stacking"], event.message)
        if self.bundle["format"] == "logsense-v2":
            candidates = individual | {"soft_voting": voting, "stacking": stacking}
            final = candidates[self.metadata["selected_model"]]
        else:
            weight = self.metadata["voting_weight"]
            final = {p: weight * voting[p] + (1 - weight) * stacking[p] for p in PRIORITIES}
        priority = decide(final)
        return Prediction(
            priority=priority,
            mode=self.metadata["mode"],
            confidence=final[priority],
            individual={
                name: {"priority": decide(probs), "probabilities": probs}
                for name, probs in individual.items()
            },
            voting=voting,
            stacking=stacking,
            probabilities=final,
            needs_review=final[priority] < self.threshold,
            model_version=self.metadata["version"],
        )
