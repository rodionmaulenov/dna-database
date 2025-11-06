import {inject, Injectable} from '@angular/core';
import {HttpClient} from '@angular/common/http';
import {Observable} from 'rxjs';
import {FileUploadResponse} from './models';
import {ENVIRONMENT} from '../config/environment.config';

@Injectable({
  providedIn: 'root'
})
export class UploadService {
  private http = inject(HttpClient);
  private env = inject(ENVIRONMENT);
  private apiUrl = this.env.apiUrl;

  uploadFile(file: File): Observable<FileUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);

    return this.http.post<FileUploadResponse>(
      `${this.apiUrl}/upload/file/`,
      formData
    );
  }

  matchFile(file: File, role: string): Observable<FileUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('role', role);

    return this.http.post<FileUploadResponse>(
      `${this.apiUrl}/upload/match/`,
      formData
    );
  }
}

