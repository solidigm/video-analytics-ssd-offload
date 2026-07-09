// Created by Metrum AI for Solidigm

import sse from 'k6/x/sse';
import { Trend, Counter, Rate } from 'k6/metrics';
import { SharedArray } from 'k6/data';
import exec from 'k6/execution';

const ttftSeconds = new Trend('ttft_seconds', true);
const tpotMs = new Trend('tpot_ms', true);
const tokensGenerated = new Counter('tokens_generated');
const tokPerSec = new Trend('tokens_per_sec', true);
const dispatchOffsetMs = new Trend('dispatch_offset_ms', true);
const errorRate = new Rate('error_rate');

// Use SharedArray to avoid per-VU memory duplication (critical for 500+ users).
// Each entry is a pre-stringified JSON body string so VUs just read it directly.
const baselinePayloads = new SharedArray('baseline', function () {
  var all = JSON.parse(open('./payloads.json'));
  return all.baseline.map(function (p) { return JSON.stringify(p); });
});
const lmcachePayloads = new SharedArray('lmcache', function () {
  var all = JSON.parse(open('./payloads.json'));
  return all.lmcache.map(function (p) { return JSON.stringify(p); });
});
const NUM_USERS = lmcachePayloads.length;

export const options = {
  scenarios: {
    baseline: {
      executor: 'per-vu-iterations',
      vus: NUM_USERS,
      iterations: 1,
      maxDuration: '__MAX_DURATION__',
      exec: 'runBaseline',
    },
    lmcache: {
      executor: 'per-vu-iterations',
      vus: NUM_USERS,
      iterations: 1,
      maxDuration: '__MAX_DURATION__',
      exec: 'runLmcache',
    },
  },
};

function runBenchmark(target, url) {
  const idx = __VU - 1;
  const payloadList = target === 'baseline' ? baselinePayloads : lmcachePayloads;
  const body = payloadList[idx % payloadList.length]; // already JSON string
  const scenarioStart = new Date(exec.scenario.startTime).getTime();
  const startTime = Date.now();
  dispatchOffsetMs.add(startTime - scenarioStart, { target: target });
  let firstTokenTime = null;
  let tokenCount = 0;

  sse.open(url, {
    method: 'POST',
    body: body,
    headers: { 'Content-Type': 'application/json' },
    tags: { target: target },
    timeout: '__MAX_DURATION__',
  }, function (client) {
    client.on('event', function (event) {
      if (!event.data || event.data.trim() === '[DONE]') {
        client.close();
        return;
      }
      try {
        var data = JSON.parse(event.data);
        var choice = data.choices && data.choices[0];
        var content = choice && choice.delta && choice.delta.content;
        if (content) {
          if (firstTokenTime === null) {
            firstTokenTime = Date.now();
            ttftSeconds.add((firstTokenTime - startTime) / 1000, { target: target });
          }
          tokenCount++;
        }
        // Some providers end with finish_reason and close without [DONE].
        if (choice && choice.finish_reason) {
          client.close();
          return;
        }
      } catch (e) { /* skip unparseable */ }
    });

    client.on('error', function (e) {
      errorRate.add(1, { target: target });
    });
  });

  var totalTime = (Date.now() - startTime) / 1000;
  tokensGenerated.add(tokenCount, { target: target });
  errorRate.add(0, { target: target });

  if (tokenCount > 1 && firstTokenTime !== null) {
    var genTime = (Date.now() - firstTokenTime) / 1000;
    tpotMs.add((genTime * 1000) / (tokenCount - 1), { target: target });
    // genTime = first→last token: actual GPU generation throughput (excludes queue wait)
    tokPerSec.add(tokenCount / genTime, { target: target });
  }
}

export function runBaseline() {
  runBenchmark('baseline', '__BASELINE_URL__');
}

export function runLmcache() {
  runBenchmark('lmcache', '__LMCACHE_URL__');
}
