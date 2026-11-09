export const MAX_SESSION_EVIDENCE_RECORDS = 6;
export const MAX_SESSION_EVIDENCE_BYTES = 300_000;

export interface SessionEvidenceRecord {
  record_id: string;
  record_category: 'syllabus' | 'course_description';
  course_code: string;
  term_scope?: { term_id?: string; term_name?: string };
  section_scope?: { section?: string };
  session_provenance: { scheme: string; signature: string };
  [key: string]: unknown;
}

export interface SessionSourceContext {
  course_code: string;
  term_id?: string | null;
  section?: string | null;
}

const encodedBytes = (value: unknown) => new TextEncoder().encode(JSON.stringify(value)).length;

/** Merge as a bounded LRU-like list without collapsing different source categories/scopes. */
export function mergeSessionEvidence(
  current: SessionEvidenceRecord[],
  acquired: SessionEvidenceRecord[],
): SessionEvidenceRecord[] {
  const ordered = [...acquired, ...current.filter((old) => !acquired.some((item) => item.record_id === old.record_id))];
  const result: SessionEvidenceRecord[] = [];
  let bytes = 0;
  for (const record of ordered) {
    const size = encodedBytes(record);
    if (size > 120_000 || bytes + size > MAX_SESSION_EVIDENCE_BYTES) continue;
    result.push(record);
    bytes += size;
    if (result.length === MAX_SESSION_EVIDENCE_RECORDS) break;
  }
  return result;
}
