function finiteNumber(value) {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

/**
 * Returns the percentage of a configured usage limit, or null when the
 * server did not provide a finite remaining allowance for a bounded limit.
 */
export function calculateUsagePercent(usedValue, limitValue, remainingValue) {
  const used = finiteNumber(usedValue);
  const limit = finiteNumber(limitValue);
  const remaining = finiteNumber(remainingValue);

  if (used === null || limit === null || remaining === null || remaining < 0 || limit <= 0) {
    return null;
  }

  return Math.min(100, Math.max(0, (Math.max(0, used) / limit) * 100));
}

/**
 * Calculates combined upload/download usage against the plan's data limit.
 */
export function calculateDataUsagePercent(uploadValue, downloadValue, limitValue, remainingValue) {
  const upload = finiteNumber(uploadValue);
  const download = finiteNumber(downloadValue);
  if (upload === null || download === null) return null;

  const consumed = Math.max(0, upload) + Math.max(0, download);
  return calculateUsagePercent(consumed, limitValue, remainingValue);
}
