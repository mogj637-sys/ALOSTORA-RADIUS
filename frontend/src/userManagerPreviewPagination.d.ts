export const USER_MANAGER_PREVIEW_PAGE_SIZE: number;

export function getPreviousPreviewOffset(offset: number, limit: number): number;
export function getNextPreviewOffset(offset: number, limit: number, total: number): number | null;
export function getPreviewPageRange(
  total: number,
  offset: number,
  itemCount: number,
): { start: number; end: number };
