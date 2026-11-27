const asNonNegativeInteger = (value) => (
  Number.isFinite(value) ? Math.max(0, Math.trunc(value)) : 0
);

export const USER_MANAGER_PREVIEW_PAGE_SIZE = 50;

export function getPreviousPreviewOffset(offset, limit) {
  const safeOffset = asNonNegativeInteger(offset);
  const safeLimit = Math.max(1, asNonNegativeInteger(limit));
  return Math.max(0, safeOffset - safeLimit);
}

export function getNextPreviewOffset(offset, limit, total) {
  const safeOffset = asNonNegativeInteger(offset);
  const safeLimit = Math.max(1, asNonNegativeInteger(limit));
  const safeTotal = asNonNegativeInteger(total);
  const nextOffset = safeOffset + safeLimit;
  return nextOffset < safeTotal ? nextOffset : null;
}

export function getPreviewPageRange(total, offset, itemCount) {
  const safeTotal = asNonNegativeInteger(total);
  const safeOffset = asNonNegativeInteger(offset);
  const safeItemCount = asNonNegativeInteger(itemCount);
  if (safeTotal === 0 || safeItemCount === 0 || safeOffset >= safeTotal) {
    return { start: 0, end: 0 };
  }
  return {
    start: safeOffset + 1,
    end: Math.min(safeTotal, safeOffset + safeItemCount),
  };
}
