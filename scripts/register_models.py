"""
Запускается один раз перед первым деплоем.
Регистрирует initial версии обеих моделей в MLflow.
"""
import os
import mlflow
import lightgbm as lgb
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from transformers import pipeline

MLFLOW_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000")
mlflow.set_tracking_uri(MLFLOW_URI)


def register_toxicity():
    model_name = "toxicity-classifier"
    with mlflow.start_run(run_name="toxicity-v1-registration"):
        pipe = pipeline("text-classification", model="unitary/toxic-bert", device=-1)

        # Тест на sample data
        result = pipe("this is a test")[0]
        mlflow.log_metric("sample_score", result["score"])
        mlflow.log_param("model_id", "unitary/toxic-bert")

        mlflow.transformers.log_model(
            transformers_model=pipe,
            artifact_path="model",
            registered_model_name=model_name,
        )

    client = mlflow.MlflowClient()
    latest = client.get_latest_versions(model_name, stages=["None"])[0]
    client.transition_model_version_stage(
        name=model_name,
        version=latest.version,
        stage="Production",
    )
    print(f"✓ {model_name} v{latest.version} → Production")


def register_ranker():
    model_name = "comment-ranker"

    # Минимальный обучающий набор для демо
    # В production — заменить на реальный датасет
    texts = [
        "great product", "terrible service", "okay experience",
        "highly recommend", "would not buy again", "average quality",
    ]
    labels = [1, 0, 0, 1, 0, 0]

    vectorizer = TfidfVectorizer(max_features=1000)
    X = vectorizer.fit_transform(texts)

    model = lgb.LGBMClassifier(n_estimators=50, random_state=42)
    model.fit(X, labels)

    # Метрики на train (для demo — OK, в production нужен val split)
    train_acc = model.score(X, labels)

    with mlflow.start_run(run_name="ranker-v1-registration"):
        mlflow.log_metric("train_accuracy", train_acc)
        mlflow.log_param("n_estimators", 50)
        mlflow.log_param("vectorizer", "tfidf_1000")

        mlflow.lightgbm.log_model(
            lgb_model=model,
            artifact_path="model",
            registered_model_name=model_name,
            # Сохраняем vectorizer как артефакт рядом
            extra_pip_requirements=["scikit-learn"],
        )

    client = mlflow.MlflowClient()
    latest = client.get_latest_versions(model_name, stages=["None"])[0]
    client.transition_model_version_stage(
        name=model_name,
        version=latest.version,
        stage="Production",
    )
    print(f"✓ {model_name} v{latest.version} → Production")


if __name__ == "__main__":
    print("Registering models in MLflow...")
    register_toxicity()
    register_ranker()
    print("Done.")