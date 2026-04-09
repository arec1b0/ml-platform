# Runbook: ML Model Rollback

## Trigger
This runbook is opened automatically when a Slack rollback alert is triggered.

## Diagnostics (first 2 minutes)

### 1. Rollout Status
```bash
kubectl argo rollouts get rollout toxicity -n ml-platform --watch
kubectl argo rollouts get rollout ranker   -n ml-platform --watch
```

### 2. AnalysisRun — why did it fail?
```bash
kubectl get analysisrun -n ml-platform
kubectl describe analysisrun <NAME> -n ml-platform
```

### 3. Metrics at the time of rollback
Grafana: https://grafana/d/ml-platform
- Panel: "Error Rate by Model" → look for anomalies
- Panel: "p99 Latency" → look for spikes

### 4. Canary pod logs
```bash
kubectl logs -l app=toxicity,rollouts-pod-template-hash=<CANARY_HASH> \
  -n ml-platform --since=10m
```

## Actions

### Rollback has already occurred automatically
No action is required. Check:
1. Grafana: error rate returned to normal (< 1%)
2. `kubectl argo rollouts get rollout toxicity` → phase: Healthy

### Rollback did not occur (phase: Paused)
```bash
# Force abort
kubectl argo rollouts abort toxicity -n ml-platform
```

### Need to record a bug in the model
```bash
# Check which version is currently in canary
kubectl argo rollouts get rollout toxicity -n ml-platform \
  -o jsonpath='{.status.canary.currentStepIndex}'

# Roll back to a specific version in MLflow
python scripts/rollback_model.py --model toxicity-classifier --version 3
```

## Escalation
If the problem is not resolved within 30 minutes → @ml-platform-oncall