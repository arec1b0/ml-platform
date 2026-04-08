import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Кастомные метрики
const toxicityErrorRate = new Rate('toxicity_errors');
const rankerErrorRate   = new Rate('ranker_errors');
const toxicityLatency   = new Trend('toxicity_latency_ms', true);
const rankerLatency     = new Trend('ranker_latency_ms',   true);

const GATEWAY_URL = __ENV.GATEWAY_URL || 'http://localhost:8000';

// Профиль нагрузки: ramp up → steady → ramp down
export const options = {
  stages: [
    { duration: '2m',  target: 50  },   // прогрев
    { duration: '5m',  target: 200 },   // baseline нагрузка
    { duration: '3m',  target: 500 },   // peak — проверяем SLO
    { duration: '2m',  target: 0   },   // ramp down
  ],
  thresholds: {
    // SLO: p99 < 200ms, error rate < 1%
    'http_req_duration{model:toxicity}': ['p(99)<200'],
    'http_req_duration{model:ranker}':   ['p(99)<50'],
    'toxicity_errors': ['rate<0.01'],
    'ranker_errors':   ['rate<0.01'],
  },
};

const toxicityPayloads = [
  { text: 'great product, highly recommend' },
  { text: 'this is absolutely terrible' },
  { text: 'neutral statement about weather' },
  { text: 'you are the worst person ever' },
  { text: 'interesting article, thanks for sharing' },
];

const rankerPayloads = [
  { texts: ['spam content', 'useful information', 'click here now'] },
  { texts: ['technical deep-dive', 'off-topic comment', 'insightful reply'] },
];

export default function () {
  // 70% toxicity, 30% ranker — имитируем реальный traffic mix
  if (Math.random() < 0.7) {
    const payload = toxicityPayloads[Math.floor(Math.random() * toxicityPayloads.length)];

    const res = http.post(
      `${GATEWAY_URL}/v1/toxicity/predict`,
      JSON.stringify(payload),
      {
        headers: { 'Content-Type': 'application/json' },
        tags: { model: 'toxicity' },
      }
    );

    const ok = check(res, {
      'toxicity status 200': r => r.status === 200,
      'toxicity has score':  r => JSON.parse(r.body).score !== undefined,
    });

    toxicityErrorRate.add(!ok);
    if (res.status === 200) {
      toxicityLatency.add(res.timings.duration);
    }

  } else {
    const payload = rankerPayloads[Math.floor(Math.random() * rankerPayloads.length)];

    const res = http.post(
      `${GATEWAY_URL}/v1/ranker/rank`,
      JSON.stringify(payload),
      {
        headers: { 'Content-Type': 'application/json' },
        tags: { model: 'ranker' },
      }
    );

    const ok = check(res, {
      'ranker status 200':       r => r.status === 200,
      'ranker has ranked_indices': r => JSON.parse(r.body).ranked_indices !== undefined,
    });

    rankerErrorRate.add(!ok);
    if (res.status === 200) {
      rankerLatency.add(res.timings.duration);
    }
  }

  sleep(0.1);  // ~10 RPS per VU
}

export function handleSummary(data) {
  return {
    'baseline-results.json': JSON.stringify(data, null, 2),
    stdout: textSummary(data, { indent: '  ', enableColors: true }),
  };
}

import { textSummary } from 'https://jslib.k6.io/k6-summary/0.0.2/index.js';