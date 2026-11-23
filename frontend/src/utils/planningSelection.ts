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

const TERM_SEASONS: Record<string, string> = {
  '01': 'Spring',
  '05': 'Summer',
  '08': 'Fall',
};

export function formatTerm(term: string | number | null | undefined): string {
  if (term === null || term === undefined || String(term).trim() === '') return 'Term not listed';
  const value = String(term).trim();
  const match = value.match(/^(\d{4})(01|05|08)$/);
  return match ? `${TERM_SEASONS[match[2]]} ${match[1]}` : value;
}

export function normalizeTermInput(term: string | number | null | undefined): string | number | null {
  if (term === null || term === undefined || String(term).trim() === '') return null;
  if (typeof term === 'number') return term;
  const value = term.trim();
  const named = value.match(/^(spring|summer|fall)\s+(\d{4})$/i);
  if (!named) return value;
  const suffix = Object.entries(TERM_SEASONS).find(([, season]) => season.toLowerCase() === named[1].toLowerCase())?.[0];
  return suffix ? `${named[2]}${suffix}` : value;
}

export function singleSelectedSourceContext(sections: ConversationSectionContext[]): {
  course_code: string;
  term_id: string;
  section: string;
} | null {
  if (sections.length !== 1) return null;
  const selected = sections[0];
  const term = normalizeTermInput(selected.term);
  if (!selected.course || !selected.section || term === null) return null;
  return {
    course_code: selected.course.replace(/\s+/g, '').toUpperCase(),
    term_id: String(term),
    section: selected.section,
  };
}

export function describeSelectedSections(sections: ConversationSectionContext[]): string {
  if (sections.length === 0) return 'No selected classes';
  return sections
    .map((section) => `${section.course} sec ${section.section || 'TBA'} (CRN ${section.crn}) · ${formatTerm(section.term)}`)
    .join(', ');
}
