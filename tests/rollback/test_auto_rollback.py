"""
Тесты доказывают, что:
1. Bad canary деплоится и получает трафик
2. AnalysisRun фиксирует нарушение SLO
3. Rollback происходит автоматически за < 5 минут
4. После rollback stable версия отвечает корректно

Требования: кластер с Argo Rollouts, Prometheus, работающий gateway.
"""
import time
import pytest
import httpx
import requests


# ── Helpers ─────────────────────────────────────────────────────────────────

def get_rollout_phase(k8s: object, namespace: str, name: str) -> str:
    rollout = k8s.get_namespaced_custom_object(
        group="argoproj.io",
        version="v1alpha1",
        namespace=namespace,
        plural="rollouts",
        name=name,
    )
    return rollout.get("status", {}).get("phase", "Unknown")


def get_prom_metric(prom_url: str, query: str) -> float:
    resp = requests.get(
        f"{prom_url}/api/v1/query",
        params={"query": query},
        timeout=5,
    )
    resp.raise_for_status()
    result = resp.json()["data"]["result"]
    if not result:
        return 0.0
    return float(result[0]["value"][1])


def wait_for_rollout_phase(
    k8s,
    namespace: str,
    name: str,
    expected_phase: str,
    timeout_s: int = 360,   # 6 минут — с запасом на 5-минутный SLO
    poll_interval_s: int = 10,
) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        phase = get_rollout_phase(k8s, namespace, name)
        if phase == expected_phase:
            return True
        if phase in ("Degraded", "Aborted") and expected_phase == "Healthy":
            # Провал раньше таймаута
            return False
        time.sleep(poll_interval_s)
    return False


# ── Scenario 1: High Error Rate ──────────────────────────────────────────────

class TestHighErrorRateRollback:
    """
    Деплоим bad-toxicity (15% error rate).
    Ожидаем: AnalysisRun fails → Rollout aborted → stable восстановлен.
    """

    def test_deploy_bad_canary(self, k8s_apps, namespace):
        """Обновляем image tag на bad-toxicity через kubectl argo rollouts."""
        import subprocess
        result = subprocess.run(
            [
                "kubectl", "argo", "rollouts", "set", "image",
                "toxicity", f"toxicity={os.environ['BAD_TOXICITY_IMAGE']}",
                "-n", namespace,
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Failed to set image: {result.stderr}"

    def test_canary_receives_traffic(self, gateway_url):
        """
        Отправляем 200 запросов.
        При canary weight=5% → ~10 запросов должны попасть на bad canary.
        """
        errors = 0
        with httpx.Client(base_url=gateway_url, timeout=10.0) as client:
            for _ in range(200):
                resp = client.post(
                    "/v1/toxicity/predict",
                    json={"text": "test input for canary validation"},
                )
                if resp.status_code >= 500:
                    errors += 1

        # При 15% error rate на 5% трафика → ~0.75% общего error rate
        # Это меньше порога 1%, но AnalysisRun смотрит на upstream напрямую
        # Достаточно что ошибки есть
        assert errors > 0, "No errors detected — bad canary may not have received traffic"

    def test_error_rate_visible_in_prometheus(self, prometheus_url):
        """Prometheus должен видеть повышенный error rate."""
        time.sleep(30)  # ждём scrape interval × 2

        query = """
            sum(rate(gateway_errors_total{model="toxicity"}[2m]))
            /
            sum(rate(gateway_requests_total{model="toxicity"}[2m]))
        """
        error_rate = get_prom_metric(prometheus_url, query)
        # Хотя бы какой-то error rate присутствует
        assert error_rate > 0, f"Error rate is 0 in Prometheus: {error_rate}"

    def test_rollback_occurs_automatically(self, k8s_apps, namespace):
        """
        Ключевой тест.
        Rollout должен уйти в Degraded/Aborted за < 5 минут (300 секунд).
        """
        start = time.time()

        # Ждём degraded state
        rolled_back = wait_for_rollout_phase(
            k8s_apps, namespace, "toxicity",
            expected_phase="Degraded",
            timeout_s=300,
        )

        elapsed = time.time() - start

        assert rolled_back, (
            f"Rollback did not occur within 5 minutes. "
            f"Current phase: {get_rollout_phase(k8s_apps, namespace, 'toxicity')}"
        )
        assert elapsed < 300, f"Rollback took {elapsed:.0f}s — exceeds 5-minute SLO"

    def test_stable_version_healthy_after_rollback(self, gateway_url):
        """
        После rollback stable версия должна отвечать без ошибок.
        """
        time.sleep(30)  # ждём полного переключения трафика

        errors = 0
        with httpx.Client(base_url=gateway_url, timeout=10.0) as client:
            for _ in range(50):
                resp = client.post(
                    "/v1/toxicity/predict",
                    json={"text": "post-rollback stability check"},
                )
                if resp.status_code >= 500:
                    errors += 1

        assert errors == 0, f"Stable version has {errors} errors after rollback"


# ── Scenario 2: High Latency ──────────────────────────────────────────────────

class TestHighLatencyRollback:
    """
    Деплоим slow-toxicity (p99 ~350ms).
    Ожидаем: p99 latency > 200ms → AnalysisRun fails → Rollback.
    """

    def test_deploy_slow_canary(self, namespace):
        import subprocess, os
        result = subprocess.run(
            [
                "kubectl", "argo", "rollouts", "set", "image",
                "toxicity", f"toxicity={os.environ['SLOW_TOXICITY_IMAGE']}",
                "-n", namespace,
            ],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr

    def test_latency_exceeds_slo(self, gateway_url, prometheus_url):
        """
        Генерируем нагрузку, затем проверяем p99 в Prometheus.
        """
        with httpx.Client(base_url=gateway_url, timeout=15.0) as client:
            for _ in range(300):
                client.post(
                    "/v1/toxicity/predict",
                    json={"text": "latency injection test"},
                )

        time.sleep(30)

        query = """
            histogram_quantile(0.99,
              sum(rate(
                gateway_upstream_duration_seconds_bucket{model="toxicity"}[2m]
              )) by (le)
            )
        """
        p99 = get_prom_metric(prometheus_url, query)
        assert p99 > 0.2, f"p99 latency {p99*1000:.0f}ms — may not trigger SLO violation"

    def test_rollback_on_latency_violation(self, k8s_apps, namespace):
        start = time.time()
        rolled_back = wait_for_rollout_phase(
            k8s_apps, namespace, "toxicity",
            expected_phase="Degraded",
            timeout_s=300,
        )
        elapsed = time.time() - start

        assert rolled_back, "Latency-based rollback did not occur"
        assert elapsed < 300, f"Rollback took {elapsed:.0f}s"