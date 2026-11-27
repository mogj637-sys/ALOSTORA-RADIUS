export type OriginalPrintCard = {
  id: string;
  status: string;
  assigned_pos_id: number | null;
};

export function isOriginalPrintEligible(card: OriginalPrintCard): boolean;
export function getOriginalPrintEligibleCards<T extends OriginalPrintCard>(cards: T[]): T[];
export function resolveOriginalPrintSelection(
  cards: OriginalPrintCard[],
  selectedIds: string[],
): { eligibleIds: string[]; rejectedCount: number };
