export interface LocusData {
  id: number;
  locus_name: string;
  allele_1: string;
  allele_2: string;
}

export interface PersonData {
  id: number;
  role: string;
  name: string;
  loci_count: number;
  loci: LocusData[];
}

export interface FileWithStatus {
  file: File;
  status: 'idle' | 'uploading' | 'success' | 'error' | 'processing';  // ✅ Add 'processing'
  response?: FileUploadResponse;
  description?: string;
  taskId?: string;  // ✅ Add this for polling
}

interface UploadState {
  files: FileWithStatus[];
  selectedRole: 'father' | 'mother' | 'child' | 'save';
  isUploading: boolean;
}

export const initialState: UploadState = {
  files: [],
  selectedRole: 'save',
  isUploading: false,
};

export interface MatchResult {
  person_id: number;
  name: string;
  role: string;
  match_percentage: number;
  matching_loci: number;
  total_loci: number;
}

// ✅ UPDATE: Add optional task_id field
export interface FileUploadResponse {
  success: boolean;
  errors: string[] | null;
  top_matches?: MatchResult[];
  task_id?: string;  // ✅ Add this (returned when async)
  message?: string;  // ✅ Add this (e.g., "Processing started")
}

// ✅ NEW: Add this interface for polling
export interface TaskStatusResponse {
  status: 'processing' | 'completed' | 'failed' | 'error';
  success: boolean | null;
  errors?: string[];
  uploaded_file_id?: number;
  message?: string;
}
