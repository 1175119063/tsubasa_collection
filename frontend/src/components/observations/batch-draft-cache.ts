import type { BatchItem } from "./batch-entry";

export interface StagedBatch {
  items: BatchItem[];
  activeId: string;
  targetDraftId: string;
  returnPath: string;
}

// In-memory only: enough to survive a short trip to /locations, never a refresh.
let staged: StagedBatch | null = null;

export function stageBatch(items: BatchItem[], activeId: string, targetDraftId: string, returnPath = "/observations"): void {
  staged = { items, activeId, targetDraftId, returnPath };
}

export function peekBatch(): StagedBatch | null {
  return staged;
}

export function clearBatch(): void {
  staged = null;
}
