import test from "node:test";
import assert from "node:assert/strict";

import {
  getNextPreviewOffset,
  getPreviousPreviewOffset,
  getPreviewPageRange,
} from "../src/userManagerPreviewPagination.js";

test("first preview page exposes the next page but not a previous page", () => {
  assert.equal(getPreviousPreviewOffset(0, 50), 0);
  assert.equal(getNextPreviewOffset(0, 50, 51), 50);
  assert.deepEqual(getPreviewPageRange(51, 0, 50), { start: 1, end: 50 });
});

test("last partial preview page has an exact range and no next page", () => {
  assert.equal(getPreviousPreviewOffset(50, 50), 0);
  assert.equal(getNextPreviewOffset(50, 50, 51), null);
  assert.deepEqual(getPreviewPageRange(51, 50, 1), { start: 51, end: 51 });
});

test("empty preview results display a zero range and no next page", () => {
  assert.equal(getNextPreviewOffset(0, 50, 0), null);
  assert.deepEqual(getPreviewPageRange(0, 0, 0), { start: 0, end: 0 });
});

test("invalid numeric inputs are clamped to safe page boundaries", () => {
  assert.equal(getPreviousPreviewOffset(-10, 0), 0);
  assert.equal(getNextPreviewOffset(-10, 0, 1), null);
  assert.deepEqual(getPreviewPageRange(10, -5, 3), { start: 1, end: 3 });
});
