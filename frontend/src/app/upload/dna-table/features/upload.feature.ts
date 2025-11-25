import {signalStoreFeature, withState, withMethods, patchState} from '@ngrx/signals';
import {form, submit} from '@angular/forms/signals';
import {inject, signal} from '@angular/core';
import {catchError, of, concatMap, from, tap} from 'rxjs';
import {rxMethod} from '@ngrx/signals/rxjs-interop';
import {pipe} from 'rxjs';
import {uploadSchema, UploadFormData} from '../schemas/upload.schema';
import {UploadService} from '../../upload.service';

interface FileUploadStatus {
  file: File;
  status: 'pending' | 'uploading' | 'success' | 'error';
  error?: string;
}

export function withUploadFeature(reloadData: () => void) {
  return signalStoreFeature(
    withState({
      uploadQueue: [] as FileUploadStatus[],
      isUploading: false
    }),

    withMethods((store) => {
      const service = inject(UploadService);

      const uploadData = signal<UploadFormData>({files: []});
      const uploadForm = form(uploadData, uploadSchema);

      const uploadFilesSequentially = rxMethod<File[]>(
        pipe(
          tap((files) => {
            const queue = files.map(file => ({
              file,
              status: 'pending' as const
            }));
            patchState(store, {uploadQueue: queue, isUploading: true});
          }),
          concatMap((files) =>
            from(files).pipe(
              concatMap((file, index) => {
                // Mark as uploading
                const queue = [...store.uploadQueue()];
                queue[index] = {...queue[index], status: 'uploading'};
                patchState(store, {uploadQueue: queue});

                return service.uploadFile(file).pipe(
                  tap((response) => {
                    const queue = [...store.uploadQueue()];
                    if (response.success) {
                      queue[index] = {...queue[index], status: 'success'};
                    } else {
                      queue[index] = {
                        ...queue[index],
                        status: 'error',
                        error: response.errors?.[0] || 'Upload failed'
                      };
                    }
                    patchState(store, {uploadQueue: queue});
                  }),
                  catchError(() => {
                    const queue = [...store.uploadQueue()];
                    queue[index] = {...queue[index], status: 'error', error: 'Network error'};
                    patchState(store, {uploadQueue: queue});
                    return of(null);
                  })
                );
              })
            )
          ),
          tap(() => {
            patchState(store, {isUploading: false});
            if (store.uploadQueue().some(f => f.status === 'success')) {
              reloadData();
            }
          })
        )
      );

      return {
        uploadForm,

        submitUpload: () => {
          submit(uploadForm, async (formSignal) => {
            const files = formSignal().value().files;
            if (!files || files.length === 0) return null;
            uploadFilesSequentially(files);
            return null;
          });
        },

        resetUpload: () => {
          patchState(store, {uploadQueue: [], isUploading: false});
          uploadData.set({files: []});
        }
      };
    }),
  );
}
