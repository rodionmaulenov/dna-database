import {inject, Injectable} from '@angular/core';
import {HttpClient, HttpParams} from '@angular/common/http';
import {Observable} from 'rxjs';
import {ENVIRONMENT} from '../../config/environment.config';
import {DeleteFileResponse, DNADataListResponse, UpdatePersonData} from '../models';

@Injectable({
  providedIn: 'root'
})
export class DnaTableHttpService {
  private http = inject(HttpClient);
  private env = inject(ENVIRONMENT);
  private apiUrl = this.env.apiUrl;


  loadTableData(personIds: string | null, page: number, pageSize: number): Observable<DNADataListResponse> {
    if (personIds) {
      // ✅ Use filter endpoint for specific persons
      const params = new HttpParams().set('person_ids', personIds);
      return this.http.get<DNADataListResponse>(`${this.apiUrl}/dna/filter/`, {params});
    } else {
      // ✅ Use list endpoint for paginated all records
      const params = new HttpParams()
        .set('page', page.toString())
        .set('page_size', pageSize.toString());
      return this.http.get<DNADataListResponse>(`${this.apiUrl}/dna/list/`, {params});
    }
  }

  updatePerson(personId: number, data: UpdatePersonData): Observable<any> {
    return this.http.patch<any>(`${this.apiUrl}/dna/person/update/${personId}/`, data);
  }

  deletePersons(personIds: number[]): Observable<any> {
    const params = new HttpParams().set('person_ids', personIds.join(','));
    return this.http.delete<any>(`${this.apiUrl}/dna/person/delete-multiple/`, { params });
  }

  deleteFile(fileId: number): Observable<DeleteFileResponse> {
    return this.http.delete<DeleteFileResponse>(`${this.apiUrl}/dna/file/delete/${fileId}/`);
  }
}
