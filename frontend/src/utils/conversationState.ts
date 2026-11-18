export function appendTranscriptEntry<T>(entries: readonly T[], entry: T): T[] {
  return [...entries, entry];
}

export function isCurrentConversationEpoch(requestEpoch: number, currentEpoch: number): boolean {
  return requestEpoch === currentEpoch;
}
