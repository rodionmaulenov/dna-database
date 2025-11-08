import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import {CreateLocusData, DNADataListResponse, UpdatePersonData} from './models';
import {ENVIRONMENT} from '../../config/environment.config';

@Injectable({
  providedIn: 'root'
})
export class DnaTableHttpService {
  private http = inject(HttpClient);
  private env = inject(ENVIRONMENT);
  private apiUrl = this.env.apiUrl;

  loadTableData(personId?: number, page: number = 1, pageSize: number = 20): Observable<DNADataListResponse> {
    let params = new HttpParams()
      .set('page', page.toString())
      .set('page_size', pageSize.toString());

    if (personId) {
      params = params.set('person_id', personId.toString());
    }

    return this.http.get<DNADataListResponse>(`${this.apiUrl}/upload/list/`, { params });
  }

  createLocus(personId: number, data: CreateLocusData): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/upload/persons/${personId}/loci/`, data);
  }

  updatePerson(id: number, data: UpdatePersonData): Observable<void> {
    return this.http.patch<void>(`${this.apiUrl}/upload/persons/${id}/`, data);
  }

  updateLocus(id: number, data: { allele_1: string; allele_2: string }): Observable<void> {
    return this.http.patch<void>(`${this.apiUrl}/upload/loci/${id}/`, data);
  }

  deleteUpload(uploadId: number): Observable<{ success: boolean; message: string }> {
    return this.http.delete<{ success: boolean; message: string }>(
      `${this.apiUrl}/upload/file/${uploadId}/`
    );
  }
  deleteLocus(id: number): Observable<any> {
    return this.http.delete<any>(`${this.apiUrl}/upload/loci/${id}/`);
  }
}
