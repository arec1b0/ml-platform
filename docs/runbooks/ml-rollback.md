# Runbook: ML Model Rollback

## Триггер
Этот runbook открывается автоматически при срабатывании Slack-алерта о rollback.

## Диагностика (первые 2 минуты)

### 1. Статус Rollout
```bash
kubectl argo rollouts get rollout toxicity -n ml-platform --watch
kubectl argo rollouts get rollout ranker   -n ml-platform --watch
```

### 2. AnalysisRun — почему failed?
```bash
kubectl get analysisrun -n ml-platform
kubectl describe analysisrun <NAME> -n ml-platform
```

### 3. Метрики в момент rollback
Grafana: https://grafana/d/ml-platform
- Panel: "Error Rate by Model" → смотри аномалию
- Panel: "p99 Latency" → смотри spike

### 4. Логи canary пода
```bash
kubectl logs -l app=toxicity,rollouts-pod-template-hash=<CANARY_HASH> \
  -n ml-platform --since=10m
```

## Действия

### Rollback уже произошёл автоматически
Ничего делать не нужно. Проверь:
1. Grafana: error rate вернулся к норме (< 1%)
2. `kubectl argo rollouts get rollout toxicity` → phase: Healthy

### Rollback не произошёл (phase: Paused)
```bash
# Принудительный abort
kubectl argo rollouts abort toxicity -n ml-platform
```

### Нужно зафиксировать баг в модели
```bash
# Проверить какая версия сейчас в canary
kubectl argo rollouts get rollout toxicity -n ml-platform \
  -o jsonpath='{.status.canary.currentStepIndex}'

# Откатиться к конкретной версии в MLflow
python scripts/rollback_model.py --model toxicity-classifier --version 3
```

## Эскалация
Если проблема не решена за 30 минут → @ml-platform-oncall