import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';
import { textSummary } from 'https://jslib.k6.io/k6-summary/0.0.2/index.js';

const toxicityErrors  = new Rate('toxicity_error_rate');
const rankerErrors    = new Rate('ranker_error_rate');
const toxicityP99     = new Trend('toxicity_p99_ms', true);
const rankerP99       = new Trend('ranker_p99_ms', true);
const totalRequests   = new Counter('total_requests');

const GATEWAY = __ENV.GATEWAY_URL || 'http://localhost:8000';

export const options = {
  scenarios: {
    // Toxicity: 350 RPS (70%)
    toxicity_load: {
      executor: 'constant-arrival-rate',
      rate: 350,
      timeUnit: '1s',
      duration: '15m',
      preAllocatedVUs: 100,
      maxVUs: 200,
      exec: 'toxicityScenario',
    },
    // Ranker: 150 RPS (30%)
    ranker_load: {
      executor: 'constant-arrival-rate',
      rate: 150,
      timeUnit: '1s',
      duration: '15m',
      preAllocatedVUs: 50,
      maxVUs: 100,
      exec: 'rankerScenario',
    },
  },
  thresholds: {
    // Definition of Done: 500 RPS, p99 < 200ms, error rate < 1%
    'http_req_duration{model:toxicity}': ['p(99)<200'],
    'http_req_duration{model:ranker}':   ['p(99)<50'],
    'toxicity_error_rate':               ['rate<0.01'],
    'ranker_error_rate':                 ['rate<0.01'],
    // Суммарный error rate
    'http_req_failed':                   ['rate<0.01'],
  },
};

const TEXTS = [
  'great product highly recommend',
  'absolutely terrible experience',
  'neutral comment about the weather today',
  'this is offensive and hateful content',
  'interesting technical article worth reading',
  'spam spam spam buy now click here',
  'thoughtful analysis of the situation',
  'I hate everything about this',
];

const RANK_BATCHES = [
  { texts: ['spam', 'useful content', 'click bait', 'technical guide'] },
  { texts: ['off topic', 'relevant reply', 'insightful comment'] },
  { texts: ['great answer', 'wrong answer', 'partial answer', 'outdated answer', 'best answer'] },
];

export function toxicityScenario() {
  const payload = JSON.stringify({
    text: TEXTS[Math.floor(Math.random() * TEXTS.length)],
  });

  const res = http.post(
    `${GATEWAY}/v1/toxicity/predict`,
    payload,
    {
      headers: { 'Content-Type': 'application/json' },
      tags: { model: 'toxicity' },
    }
  );

  const ok = check(res, {
    'status 200':    r => r.status === 200,
    'has is_toxic':  r => {
      try { return JSON.parse(r.body).is_toxic !== undefined; }
      catch { return false; }
    },
  });

  toxicityErrors.add(!ok);
  if (res.status === 200) toxicityP99.add(res.timings.duration);
  totalRequests.add(1);
}

export function rankerScenario() {
  const payload = JSON.stringify(
    RANK_BATCHES[Math.floor(Math.random() * RANK_BATCHES.length)]
  );

  const res = http.post(
    `${GATEWAY}/v1/ranker/rank`,
    payload,
    {
      headers: { 'Content-Type': 'application/json' },
      tags: { model: 'ranker' },
    }
  );

  const ok = check(res, {
    'status 200':         r => r.status === 200,
    'has ranked_indices': r => {
      try { return Array.isArray(JSON.parse(r.body).ranked_indices); }
      catch { return false; }
    },
  });

  rankerErrors.add(!ok);
  if (res.status === 200) rankerP99.add(res.timings.duration);
  totalRequests.add(1);
}

export function handleSummary(data) {
  const summary = {
    timestamp: new Date().toISOString(),
    thresholds_passed: Object.entries(data.metrics)
      .filter(([_, m]) => m.thresholds)
      .every(([_, m]) => Object.values(m.thresholds).every(t => !t.ok === false)),
    metrics: {
      toxicity_p99_ms:    data.metrics['toxicity_p99_ms']?.values?.['p(99)'],
      ranker_p99_ms:      data.metrics['ranker_p99_ms']?.values?.['p(99)'],
      toxicity_error_rate: data.metrics['toxicity_error_rate']?.values?.rate,
      ranker_error_rate:   data.metrics['ranker_error_rate']?.values?.rate,
      total_requests:      data.metrics['total_requests']?.values?.count,
    },
  };

  return {
    '500rps-results.json': JSON.stringify(summary, null, 2),
    stdout: textSummary(data, { indent: '  ', enableColors: true }),
  };
}