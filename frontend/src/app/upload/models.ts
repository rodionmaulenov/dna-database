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
  status: 'idle' | 'uploading' | 'success' | 'error';
  response?: FileUploadResponse;
  description?: string;
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


export interface FileUploadResponse {
  success: boolean;
  errors: string[] | null;
  top_matches?: MatchResult[];
}

