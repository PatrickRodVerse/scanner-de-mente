import assert from 'node:assert/strict';
import { colorFor, demoResult, patchIndex } from '../ui/app.js';

const example = demoResult();
assert.equal(example.metadata.synthetic, true);
assert.equal(example.patches.length, 12 * example.tokens.length);
const index = patchIndex(example);
assert.equal(index.get(`11:${example.tokens.length - 1}`).recovery, 1);
assert.equal(index.get('11:0').effect, 0);
for (const patch of example.patches) {
  assert.ok(Number.isFinite(patch.effect));
  assert.ok(Math.abs((patch.patched_score - example.corrupt_score) - patch.effect) < 1e-10);
}
assert.equal(colorFor(null, 1), '#f0f3f3');
assert.equal(colorFor(NaN, 1), '#f0f3f3');
assert.equal(colorFor(1, 1), 'rgb(27, 108, 128)');
assert.notEqual(colorFor(-1, 1), colorFor(1, 1));
console.log('UI data self-check: passed');
