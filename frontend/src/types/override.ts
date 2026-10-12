export type OverrideReasonCategory = 
  | 'SCHEDULE_CONFLICT' 
  | 'DEGREE_REQUIREMENT' 
  | 'PREREQ_WAIVER' 
  | 'OTHER';

export interface OverrideFormState {
  courseCode: string;
  reasonCategory: OverrideReasonCategory | '';
  justification: string;
  attachedFile: File | null;
  isSubmitting: boolean;
  status: 'IDLE' | 'SUCCESS' | 'ERROR';
}