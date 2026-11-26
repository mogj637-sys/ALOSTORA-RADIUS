import assert from "node:assert/strict";
import test from "node:test";

import {
  calculateDataUsagePercent,
  calculateUsagePercent,
} from "../src/cardUsage.js";

test("time usage is measured against the session limit, not an earlier expiry cap", () => {
  const percent = calculateUsagePercent(300, 3600, 0);
  assert.ok(percent !== null);
  assert.ok(Math.abs(percent - (300 / 3600) * 100) < 1e-9);
});

test("data usage combines upload and download counters", () => {
  assert.equal(calculateDataUsagePercent(100, 300, 1000, 600), 40);
});

test("unlimited or unavailable server allowances do not produce a meter", () => {
  assert.equal(calculateUsagePercent(100, 1000, null), null);
  assert.equal(calculateUsagePercent(100, 1000, undefined), null);
  assert.equal(calculateDataUsagePercent(20, 30, 1000, null), null);
});

test("missing, invalid, zero, or negative limits do not produce a meter", () => {
  assert.equal(calculateUsagePercent(10, null, 90), null);
  assert.equal(calculateUsagePercent(10, "invalid", 90), null);
  assert.equal(calculateUsagePercent(10, 0, 0), null);
  assert.equal(calculateUsagePercent(10, -1, 0), null);
});

test("usage is clamped to the valid 0-100 percent range", () => {
  assert.equal(calculateUsagePercent(1500, 1000, 0), 100);
  assert.equal(calculateUsagePercent(-50, 1000, 1000), 0);
  assert.equal(calculateDataUsagePercent(-50, 150, 1000, 850), 15);
});

test("numeric values serialized as strings remain supported", () => {
  assert.equal(calculateUsagePercent("250", "1000", 750), 25);
  assert.equal(calculateDataUsagePercent("100", "200", "1000", 700), 30);
});

test("invalid usage counters do not produce a data meter", () => {
  assert.equal(calculateDataUsagePercent("not-a-number", 20, 1000, 980), null);
});
