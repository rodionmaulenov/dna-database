import {LocusData, PersonData} from '../models';

export interface DNADataResponse {
  id: number;
  parent: PersonData | null;
  child: PersonData | null;
  children: PersonData[] | null;
}

export interface DNADataListResponse {
  data: DNADataResponse[];
  total: number;
  page: number;
  page_size: number;
}

export interface TableRowData {
  id: number;
  personId: number;
  name: string;
  role: string;
  loci_count: number;
  file: string;  // First file (backward compatibility)
  files?: Array<{  // ✅ Already has this
    id: number;
    file: string;
    uploaded_at: string;
  }>;
  loci: LocusData[];

  relatedPersonId: number | null; // ID of child (if parent) or parent (if child)
  relatedPersonName: string | null; // Name of child (if parent) or parent (if child)
  relatedPersonRole: string | null;
  relatedPersons: Array<{
    id: number;
    name: string;
    role: string;
  }> | null;
}

interface DnaTableState {
  tableData: TableRowData[];
  loading: boolean;
  currentPage: number;
  pageSize: number;
  totalRecords: number;
  currentPersonFilter: number | null;
  localPersonFilter: number | null;
  multiplePersonFilter: number[] | null;
  roleFilter: 'parent' | 'child';
  expandedRowId: number | null;
  updatingRowId: number | null;
}

export const initialState: DnaTableState = {
  tableData: [],
  loading: false,
  currentPage: 1,
  pageSize: 20,
  totalRecords: 0,
  currentPersonFilter: null,
  localPersonFilter: null,
  multiplePersonFilter: null,
  roleFilter: 'parent',
  expandedRowId: null,
  updatingRowId: null,
};

export interface UpdatePersonData {
  name?: string;
  role?: string;
}

export interface CreateLocusData {
  locus_name: string;
  allele_1: string;
  allele_2: string;
}

export interface LociUpdate {
  id: number | null;
  locus_name?: string;
  allele_1: string;
  allele_2: string;
}

