/**
 * Запускается параллельно с деплоем новой canary версии.
 * Цель: доказать zero-downtime во время canary promotion.
 *
 * Запуск:
 *   k6 run tests/load/k6-canary-under-load.js &
 *   kubectl argo rollouts set image toxicity toxicity=$NEW_IMAGE -n ml-platform
 */
import http from 'k6/http';
import { check } from 'k6';
import { Rate } from 'k6/metrics';

const errors = new Rate('canary_errors');
const GATEWAY = __ENV.GATEWAY_URL || 'http://localhost:8000';

export const options = {
  // Фиксированная нагрузка на всё время canary promotion
  scenarios: {
    steady: {
      executor: 'constant-arrival-rate',
      rate: 200,
      timeUnit: '1s',
      duration: '25m',        // перекрывает весь цикл AnalysisRun
      preAllocatedVUs: 60,
      maxVUs: 120,
    },
  },
  thresholds: {
    // Во время canary promotion ошибок быть не должно
    'canary_errors':     ['rate<0.005'],
    'http_req_duration': ['p(99)<250'],  // чуть мягче — учитываем routing overhead
  },
};

export default function () {
  const res = http.post(
    `${GATEWAY}/v1/toxicity/predict`,
    JSON.stringify({ text: 'canary promotion load test' }),
    { headers: { 'Content-Type': 'application/json' } }
  );

  errors.add(res.status >= 500);

  check(res, { 'not 5xx': r => r.status < 500 });
}