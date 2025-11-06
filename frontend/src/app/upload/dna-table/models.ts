import {LocusData, PersonData} from '../models';

export interface DNADataResponse {
  id: number;
  file: string;
  overall_confidence: number;
  uploaded_at: string;
  parent: PersonData | null;
  child: PersonData | null;
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
  overall_confidence: number;
  uploaded_at: string;
  name: string;
  role: string;
  loci_count: number;
  file: string;
  loci: LocusData[];

  relatedPersonId: number | null; // ID of child (if parent) or parent (if child)
  relatedPersonName: string | null; // Name of child (if parent) or parent (if child)
  relatedPersonRole: string | null;
}

interface DnaTableState {
  tableData: TableRowData[];
  loading: boolean;
  currentPage: number;
  pageSize: number;
  totalRecords: number;
  currentPersonFilter: number | null;
  roleFilter: 'parent' | 'child';
  expandedRowId: number | null;
  updatingRowId: number | null;
}

export const initialState: DnaTableState = {
  tableData: [],
  loading: false,
  currentPage: 1,
  pageSize: 50,
  totalRecords: 0,
  currentPersonFilter: null,
  roleFilter: 'parent',
  expandedRowId: null,
  updatingRowId: null,
};

