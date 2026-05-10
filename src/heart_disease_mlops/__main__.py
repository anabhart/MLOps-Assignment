"""Convenience entry point: ``python -m heart_disease_mlops`` runs training."""

from .train import train_and_log_all

if __name__ == "__main__":
    import json

    print(json.dumps(train_and_log_all(), indent=2))
