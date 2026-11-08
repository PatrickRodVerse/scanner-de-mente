import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { summarizeCase } from '../site/app.js';

const study = JSON.parse(readFileSync(new URL('../site/ioi.json', import.meta.url), 'utf8'));
const original = study.cases.find((item) => item.id === 'original');
const { restore, fixed, drop } = summarizeCase(original);
assert.equal(restore.toFixed(2), '5.08');
assert.equal(fixed.toFixed(2), '0.95');
assert.equal((100 * drop).toFixed(1), '81.3');
assert.equal(study.scan.patches.length, 24);
assert.equal(study.cases.length, 4);
for (const { scores } of study.cases) {
  assert.ok(scores.clean > 0 && scores.corrupt < 0);
  assert.ok(scores.restore > 0 && scores.restore_clamp_last < 0 && scores.restore_clamp_adjacent > 0);
}

// The held-state condition uses its own control even when that control changes.
assert.deepEqual(summarizeCase({ scores: { restore: 5, corrupt: -1, restore_clamp_last: 4, clamp_last: 2 } }),
  { restore: 6, fixed: 2, drop: 1 - 2 / 6 });
console.log('Public study measurements and comparisons verified.');
