import {signalStoreFeature, withState, withMethods, patchState} from '@ngrx/signals';
import {inject} from '@angular/core';
import {catchError, of, concatMap, from, tap} from 'rxjs';
import {rxMethod} from '@ngrx/signals/rxjs-interop';
import {pipe} from 'rxjs';
import {UploadService} from '../../upload.service';

interface FileUploadStatus {
  file: File;
  status: 'uploading' | 'success' | 'error';
  error?: string;
}

export function withUploadFeature(loadInitial: () => void) {
  return signalStoreFeature(
    withState({
      uploadQueue: [] as FileUploadStatus[],
      isUploading: false
    }),

    withMethods((store) => {
      const service = inject(UploadService);

      const uploadFiles = rxMethod<File[]>(
        pipe(
          tap((files) => {
            const queue = files.map(file => ({ file, status: 'uploading' as const }));
            patchState(store, { uploadQueue: queue, isUploading: true });
          }),
          concatMap((files) =>
            from(files).pipe(
              concatMap((file, index) =>
                service.uploadFile(file).pipe(
                  tap((response) => {
                    const queue = [...store.uploadQueue()];
                    queue[index] = {
                      ...queue[index],
                      status: response.success ? 'success' : 'error',
                      error: response.success ? undefined : (response.errors?.[0] || 'Upload failed')
                    };
                    patchState(store, { uploadQueue: queue });
                  }),
                  catchError(() => {
                    const queue = [...store.uploadQueue()];
                    queue[index] = { ...queue[index], status: 'error', error: 'Network error' };
                    patchState(store, { uploadQueue: queue });
                    return of(null);
                  })
                )
              )
            )
          ),
          tap(() => {
            patchState(store, { isUploading: false });
            if (store.uploadQueue().some(f => f.status === 'success')) {
              loadInitial();
            }
          })
        )
      );

      return {
        uploadFiles: (files: File[]) => uploadFiles(files),

        resetUpload: () => {
          patchState(store, { uploadQueue: [], isUploading: false });
        }
      };
    }),
  );
}
