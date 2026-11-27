import assert from "node:assert/strict";
import test from "node:test";

import {
  getOriginalPrintEligibleCards,
  isOriginalPrintEligible,
  resolveOriginalPrintSelection,
} from "../src/cardSelection.js";

const cards = [
  { id: "ready", status: "generated", assigned_pos_id: null },
  { id: "allocated", status: "allocated", assigned_pos_id: 4 },
  { id: "assigned", status: "generated", assigned_pos_id: 4 },
  { id: "expired", status: "expired", assigned_pos_id: null },
  { id: "active", status: "active", assigned_pos_id: null },
];

test("only generated, unassigned cards are eligible for original printing", () => {
  assert.equal(isOriginalPrintEligible(cards[0]), true);
  assert.equal(isOriginalPrintEligible(cards[1]), false);
  assert.equal(isOriginalPrintEligible(cards[2]), false);
  assert.equal(isOriginalPrintEligible(cards[3]), false);
  assert.deepEqual(getOriginalPrintEligibleCards(cards).map((card) => card.id), ["ready"]);
});

test("bulk selection is restricted to eligible cards on the current page", () => {
  const selected = getOriginalPrintEligibleCards(cards).map((card) => card.id);
  assert.deepEqual(selected, ["ready"]);
});

test("stale or newly ineligible selections are rejected before navigation to printing", () => {
  const result = resolveOriginalPrintSelection(cards, ["ready", "expired", "missing"]);
  assert.deepEqual(result.eligibleIds, ["ready"]);
  assert.equal(result.rejectedCount, 2);
});

test("duplicate selected IDs are normalized without creating duplicate print entries", () => {
  const result = resolveOriginalPrintSelection(cards, ["ready", "ready"]);
  assert.deepEqual(result.eligibleIds, ["ready"]);
  assert.equal(result.rejectedCount, 0);
});

test("an empty selection cannot resolve to printable cards", () => {
  assert.deepEqual(resolveOriginalPrintSelection(cards, []), {
    eligibleIds: [],
    rejectedCount: 0,
  });
});
