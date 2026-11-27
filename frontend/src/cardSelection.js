export function isOriginalPrintEligible(card) {
  return card?.status === "generated" && card?.assigned_pos_id === null;
}

export function getOriginalPrintEligibleCards(cards) {
  return cards.filter(isOriginalPrintEligible);
}

/**
 * Resolves a selection against the currently loaded page.
 * Missing IDs and cards that are no longer eligible are rejected together.
 */
export function resolveOriginalPrintSelection(cards, selectedIds) {
  const requestedIds = [...new Set(selectedIds)];
  const requested = new Set(requestedIds);
  const selectedCards = cards.filter((card) => requested.has(card.id));
  const eligibleCards = selectedCards.filter(isOriginalPrintEligible);

  return {
    eligibleIds: eligibleCards.map((card) => card.id),
    rejectedCount: requestedIds.length - eligibleCards.length,
  };
}
