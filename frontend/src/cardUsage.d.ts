export function calculateUsagePercent(
  usedValue: number | string | null | undefined,
  limitValue: number | string | null | undefined,
  remainingValue: number | null | undefined,
): number | null;

export function calculateDataUsagePercent(
  uploadValue: number | string | null | undefined,
  downloadValue: number | string | null | undefined,
  limitValue: number | string | null | undefined,
  remainingValue: number | null | undefined,
): number | null;
