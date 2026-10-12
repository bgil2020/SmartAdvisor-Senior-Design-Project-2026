/**
 * SmartAdvisor Frontend API Client
 * Connects browser components to FastAPI backend endpoints.
 */

const API_BASE_URL = (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');

export interface RawCourseRecord {
  COURSE: string;
  TITLE: string;
  DEPT?: string;
  METHOD?: string;
  CAMPUS?: string;
  [key: string]: unknown;
}

export interface RawSectionRecord {
  CRN: number | string;
  COURSE: string;
  SECT: string;
  TITLE: string;
  DAYS?: string | null;
  'BEG TIME'?: string | null;
  'END TIME'?: string | null;
  METHOD?: string | null;
  CAMPUS?: string | null;
  'ENRL REMN'?: number | string | null;
  INSTRUCTOR?: string | null;
  TERM?: number | string | null;
  [key: string]: unknown;
}

export interface CoursesResponse {
  count: number;
  filters: {
    term: string | null;
    department: string | null;
    modality: string | null;
  };
  courses: RawCourseRecord[];
}

export interface SectionsResponse {
  count: number;
  filters: {
    course?: string | null;
    crn?: string | null;
    term?: string | null;
    modality?: string | null;
  };
  sections: RawSectionRecord[];
}

export interface AlternativesResponse {
  requested_crn: string;
  count: number;
  alternatives: RawSectionRecord[];
}

export interface CompatibilityRequest {
  student_id: string;
  proposed_courses: string[];
  recent_difficulty: number;
  satisfied_with_performance: 'yes' | 'mostly' | 'no';
  work_hours: number;
  preferred_max_credits?: number | null;
  recent_courses?: string[] | null;
}

export interface CompatibilityResponse {
  success: boolean;
  student_id: string;
  student_name: string;
  major: string;
  proposed_courses: string[];
  proposed_credits: number;
  overall_risk: 'Low' | 'Medium' | 'High' | string;
  recommendations: string[];
  matched_combinations?: Array<{
    courses: string[];
    risk_category: string;
    severity: string;
    explanation: string;
    recommended_action?: string;
  }>;
  repeat_courses?: string[];
  data_limitations?: string[];
  disclaimer?: string;
  detail?: string | unknown;
}

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(message: string, status: number, data?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errData: unknown;
    try {
      errData = await res.json();
    } catch {
      errData = await res.text();
    }
    const message =
      typeof errData === 'object' && errData !== null && 'detail' in errData
        ? String((errData as { detail: unknown }).detail)
        : `Request failed with status ${res.status}`;
    throw new ApiError(message, res.status, errData);
  }
  return res.json() as Promise<T>;
}

/**
 * Fetch all available course records from the backend.
 */
export async function getCourses(filters?: {
  term?: string;
  department?: string;
  modality?: string;
}): Promise<CoursesResponse> {
  const params = new URLSearchParams();
  if (filters?.term) params.append('term', filters.term);
  if (filters?.department) params.append('department', filters.department);
  if (filters?.modality) params.append('modality', filters.modality);

  const query = params.toString();
  const url = `${API_BASE_URL}/courses${query ? `?${query}` : ''}`;
  const res = await fetch(url);
  return handleResponse<CoursesResponse>(res);
}

/**
 * Fetch sections for a course using the supported query parameter `course`.
 */
export async function getSections(
  course: string,
  filters?: { crn?: string; term?: string; modality?: string }
): Promise<SectionsResponse> {
  const params = new URLSearchParams();
  params.append('course', course);
  if (filters?.crn) params.append('crn', filters.crn);
  if (filters?.term) params.append('term', filters.term);
  if (filters?.modality) params.append('modality', filters.modality);

  const url = `${API_BASE_URL}/sections?${params.toString()}`;
  const res = await fetch(url);
  return handleResponse<SectionsResponse>(res);
}

/**
 * Fetch alternative non-conflicting sections for a conflicted CRN.
 */
export async function getAlternatives(
  crn: string | number,
  selectedCrns: (string | number)[]
): Promise<AlternativesResponse> {
  const params = new URLSearchParams();
  params.append('crn', String(crn));
  if (selectedCrns.length > 0) {
    params.append('selected_crns', selectedCrns.map(String).join(','));
  }

  const url = `${API_BASE_URL}/alternatives?${params.toString()}`;
  const res = await fetch(url);
  return handleResponse<AlternativesResponse>(res);
}

/**
 * Evaluate workload and course combination compatibility via the backend engine.
 */
export async function checkCompatibility(
  payload: CompatibilityRequest
): Promise<CompatibilityResponse> {
  const url = `${API_BASE_URL}/compatibility`;
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
  return handleResponse<CompatibilityResponse>(res);
}

export interface ConversationRequest {
  message: string;
  student_id?: string | null;
  recent_difficulty?: number | null;
  satisfied_with_performance?: 'yes' | 'mostly' | 'no' | null;
  work_hours?: number | null;
  preferred_max_credits?: number | null;
  recent_courses?: string[] | null;
}

export interface ConversationResponse {
  status:
    | 'engine_executed'
    | 'clarification'
    | 'escalation'
    | 'rag_inactive'
    | 'unsupported'
    | 'engine_unavailable'
    | 'engine_error';
  raw_message: string;
  disposition: string;
  target_handler: string;
  response_code: string;
  response_text: string;
  actionable_guidance?: string | null;
  safe_to_route: boolean;
  missing_context: string[];
  extracted_courses: string[];
  engine_executed: boolean;
  engine_result?: Record<string, unknown> | null;
  disclaimer: string;
}

/**
 * Send natural-language student message to deterministic conversational assistant.
 * If intent is course compatibility and student context is provided, executes compatibility engine.
 */
export async function sendConversationMessage(
  payload: ConversationRequest
): Promise<ConversationResponse> {
  const url = `${API_BASE_URL}/conversation`;
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
  return handleResponse<ConversationResponse>(res);
}

