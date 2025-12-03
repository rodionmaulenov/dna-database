// src/app/components/shared-models.ts

// ============================================================================
// CORE DNA DATA MODELS
// ============================================================================

export interface Locus {
  id: number;
  locus_name: string;
  allele_1: string | null;
  allele_2: string | null;
}

export interface UploadedFile {
  id: number;
  file: string;
  uploaded_at: string;
}

export interface PersonData {
  id: number;
  name: string;
  role: string;
  loci_count: number;
  loci: Locus[];
  files?: UploadedFile[];
}

export interface DnaRecord {
  id: number;
  parent: PersonData | null;
  child: PersonData | null;
  children: PersonData[] | null;
}

// ============================================================================
// BACKWARD COMPATIBILITY ALIASES
// ============================================================================

export type LocusData = Locus;
export type DNADataResponse = DnaRecord;

// ============================================================================
// UPLOAD MODELS
// ============================================================================

export interface FileWithStatus {
  file: File;
  status: 'idle' | 'uploading' | 'success' | 'error';
  response?: FileUploadResponse;
  description?: string;
  error?: string;
}

export interface UploadState {
  files: FileWithStatus[];
  selectedRole: 'parent' | 'child' | 'save';
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

export interface LinkInfo {
  person_id: number;
  name: string;
  role: string
}


export interface FileUploadResponse {
  success: boolean;
  errors: string[] | null;
  links?: LinkInfo[];
  top_matches?: MatchResult[];
}

export interface FilterPersonResult {
  action: 'view_person' | 'view_match';
  personId: number;
  personName: string;
  role: string;
}

// ============================================================================
// DNA TABLE MODELS
// ============================================================================

export interface RelatedPerson {
  id: number;
  name: string;
  role: string;
}

export interface TableRowData {
  id: number;
  personId: number;
  name: string;
  role: 'father' | 'mother' | 'child';
  loci_count: number;
  file: string;
  files?: UploadedFile[];
  loci: Locus[];
  relatedPersonId: number | null;
  relatedPersonName: string | null;
  relatedPersonRole: string | null;
  relatedPersons: RelatedPerson[] | null;
}

export interface DNADataListResponse {
  data: DnaRecord[];
  total: number;
  page: number;
  page_size: number;
}

export interface LociUpdate {
  id?: number;
  locus_name: string;
  allele_1: string;
  allele_2: string;
}

export interface UpdatePersonData {
  name?: string;
  role?: string;
  loci?: LociUpdate[];
}

// persons-array.schema.ts
export interface LocusFormData {
  locus_name: string;  // ✅ Add this
  alleles: string;
}

export interface PersonFormData {
  id: number;
  name: string;
  role: 'father' | 'mother' | 'child';
  loci: LocusFormData[];
}

export interface PersonsArrayFormData {
  persons: PersonFormData[];
}

export interface DeleteFileResponse {
  success: boolean;
  deleted_person_ids: number[];
  unlinked_person_ids: number[];
}
