import {LocusData, PersonData} from '../models';

export interface TableRowData {
  id: number;
  personId: number;
  name: string;
  role: 'father' | 'mother' | 'child';
  loci_count: number;
  file: string;
  files?: Array<{
    id: number;
    file: string;
    uploaded_at: string;
  }>;
  loci: LocusData[];
  relatedPersonId: number | null;
  relatedPersonName: string | null;
  relatedPersonRole: string | null;
  relatedPersons: Array<{
    id: number;
    name: string;
    role: string;
  }> | null;
}

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

export interface UpdatePersonData {
  name?: string;
  role?: string;
  loci?: Array<{
    id: number;
    locus_name: string;
    allele_1: string;
    allele_2: string;
  }>;
  deleted_loci_ids?: number[];
}

export interface UpdatePersonResponse {
  success: boolean;
  errors?: string[];
}

export interface CreateLocusData {
  locus_name: string;
  allele_1: string;
  allele_2: string;
}



