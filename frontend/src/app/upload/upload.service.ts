import {inject, Injectable} from '@angular/core';
import {HttpClient} from '@angular/common/http';
import {filter, interval, map, Observable, of, startWith, switchMap, take, takeWhile} from 'rxjs';
import {FileUploadResponse, TaskStatusResponse} from './models';
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

    // 1. Upload file
    return this.http.post<FileUploadResponse>(`${this.apiUrl}/upload/file/`, formData).pipe(
      switchMap(response => {
        if (response.task_id) {
          // 2. Got task_id, start polling
          return this.pollTaskStatus(response.task_id).pipe(
            map(taskStatus => ({
              success: taskStatus.success || false,
              errors: taskStatus.errors || null,
            }))
          );
        }
        // Old synchronous response (backward compatible)
        return of(response);
      })
    );
  }

  matchFile(file: File, role: string): Observable<FileUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);

    return this.http.post<FileUploadResponse>(`${this.apiUrl}/upload/match/`, formData, {
      params: { role }
    }).pipe(
      switchMap(response => {
        if (response.task_id) {
          return this.pollTaskStatus(response.task_id).pipe(
            map(taskStatus => ({
              success: taskStatus.success || false,
              errors: taskStatus.errors || null,
              top_matches: (taskStatus as any).top_matches || [],
            }))
          );
        }
        return of(response);
      })
    );
  }

  // ✅ NEW: Poll task status
  private pollTaskStatus(taskId: string): Observable<TaskStatusResponse> {
    return interval(2000).pipe(  // Poll every 2 seconds
      startWith(0),  // Start immediately
      switchMap(() =>
        this.http.get<TaskStatusResponse>(`${this.apiUrl}/upload/task/${taskId}/`)
      ),
      // Continue while processing
      takeWhile(response => response.status === 'processing', true),
      // Stop when completed or failed
      filter(response => response.status !== 'processing'),
      take(1)
    );
  }
}

