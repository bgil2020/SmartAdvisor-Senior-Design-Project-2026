import type { RawSectionRecord } from '../services/api';

export interface ConversationSectionContext {
  crn: string;
  course: string;
  section: string;
  term: string | number | null;
}

export function selectedSectionGroups(records: RawSectionRecord[]): RawSectionRecord[][] {
  const groups = new Map<string, RawSectionRecord[]>();
  for (const record of records) {
    const key = String(record.CRN);
    groups.set(key, [...(groups.get(key) ?? []), record]);
  }
  return Array.from(groups.values());
}

export function addSelectedSectionGroup(current: RawSectionRecord[], records: RawSectionRecord[]): RawSectionRecord[] {
  if (records.length === 0) return current;
  const crn = String(records[0].CRN);
  return current.some((section) => String(section.CRN) === crn) ? current : [...current, ...records];
}

export function removeSelectedSection(current: RawSectionRecord[], crn: string | number): RawSectionRecord[] {
  const target = String(crn);
  return current.filter((section) => String(section.CRN) !== target);
}

export function toConversationSections(records: RawSectionRecord[]): ConversationSectionContext[] {
  return selectedSectionGroups(records).map((group) => {
    const section = group[0];
    return {
      crn: String(section.CRN),
      course: section.COURSE.trim(),
      section: String(section.SECT ?? '').trim(),
      term: section.TERM ?? null,
    };
  });
}

export function commonSelectedTerm(sections: ConversationSectionContext[]): string | number | null {
  const terms = Array.from(new Set(sections.map((section) => section.term).filter((term) => term !== null)));
  return terms.length === 1 ? terms[0] : null;
}

export function describeSelectedSections(sections: ConversationSectionContext[]): string {
  if (sections.length === 0) return 'No selected classes';
  return sections
    .map((section) => `${section.course} sec ${section.section || 'TBA'} (CRN ${section.crn})`)
    .join(', ');
}
