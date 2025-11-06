import { computed } from '@angular/core';
import { pipe, switchMap, tap, from, of, concatMap, finalize } from 'rxjs';
import { inject } from '@angular/core';
import { UploadService } from './upload.service';
import { patchState, signalStore, withComputed, withMethods, withState } from '@ngrx/signals';
import { NotificationService } from '../shared/services/notification.service';
import { DnaTableStore } from './dna-table/dna-table.store';
import { rxMethod } from '@ngrx/signals/rxjs-interop';
import { tapResponse } from '@ngrx/operators';
import { FileWithStatus, initialState } from './models';

export const UploadStore = signalStore(
  { providedIn: 'root' },

  withState(initialState),

  withComputed((store) => ({
    hasFilesToUpload: computed(() =>
      store.files().some(f => f.status === 'idle')
    ),
  })),

  withMethods((store) => {
    const uploadService = inject(UploadService);
    const notificationService = inject(NotificationService);
    const tableStore = inject(DnaTableStore);  // ⭐ Changed from tableService

    return {
      setRole(role: 'father' | 'mother' | 'child' | 'save') {
        patchState(store, { selectedRole: role });
      },

      addFiles(newFiles: File[]) {
        const role = store.selectedRole();
        const maxSize = 10 * 1024 * 1024;

        if (role !== 'save') {
          if (newFiles.length > 1) {
            notificationService.error('Matching mode: Please select only ONE file');
            return;
          }

          if (store.files().length > 0) {
            notificationService.error('Remove existing file before adding a new one');
            return;
          }
        }

        const validFiles: FileWithStatus[] = [];

        for (const file of newFiles) {
          if (file.size > maxSize) {
            notificationService.error(`${file.name} is too large (max 10MB)`);
            continue;
          }
          validFiles.push({ file, status: 'idle' });
        }

        if (validFiles.length > 0) {
          patchState(store, { files: [...store.files(), ...validFiles] });
          notificationService.info(`${validFiles.length} file(s) selected`);
        }
      },

      removeFile(index: number) {
        const files = [...store.files()];
        files.splice(index, 1);
        patchState(store, { files });
      },

      clearAll() {
        const count = store.files().length;
        patchState(store, { files: [] });
        notificationService.info(`Cleared ${count} file(s)`);
      },

      // ⭐ Upload all files sequentially using rxMethod (fully reactive)
      uploadAll: rxMethod<void>(
        pipe(
          tap(() => {
            const filesToUpload = store.files().filter(f => f.status === 'idle');

            if (filesToUpload.length === 0) {
              notificationService.warning('No files to upload');
              return;
            }

            patchState(store, { isUploading: true });
          }),
          switchMap(() => {
            const filesToUpload = store.files()
              .map((f, index) => ({ file: f, index }))
              .filter(({ file }) => file.status === 'idle');

            if (filesToUpload.length === 0) {
              return of(null);
            }

            const role = store.selectedRole();

            // ⭐ Process files sequentially with concatMap
            return from(filesToUpload).pipe(
              concatMap(({ file, index }) => {
                // Update to uploading
                patchState(store, (state) => {
                  const files = [...state.files];
                  files[index] = { ...files[index], status: 'uploading' };
                  return { files };
                });

                const upload$ = role === 'save'
                  ? uploadService.uploadFile(file.file)
                  : uploadService.matchFile(file.file, role);

                return upload$.pipe(
                  tapResponse({
                    next: (response) => {
                      patchState(store, (state) => {
                        const files = [...state.files];
                        files[index] = {
                          ...files[index],
                          status: 'success',
                          response
                        };
                        return { files };
                      });

                      // Show notifications
                      if (role === 'save') {
                        notificationService.success(`${file.file.name} saved to database`);
                        tableStore.refreshData();
                      } else {
                        if (response.top_matches?.length) {
                          notificationService.success(`${file.file.name}: Found ${response.top_matches.length} matches`);
                        } else {
                          notificationService.warning(`${file.file.name}: No matches found`);
                        }
                      }
                    },
                    error: (error: any) => {
                      const errorResponse = error.error || {
                        success: false,
                        errors: ['Processing failed']
                      };

                      patchState(store, (state) => {
                        const files = [...state.files];
                        files[index] = {
                          ...files[index],
                          status: 'error',
                          response: errorResponse
                        };
                        return { files };
                      });

                      const errorMsg = errorResponse.errors?.[0] || 'Network error';
                      notificationService.error(`${file.file.name}: ${errorMsg}`);
                    }
                  })
                );
              }),
              finalize(() => patchState(store, { isUploading: false }))
            );
          })
        )
      ),

      // ⭐ Navigate to matched person (fully reactive)
      navigateToMatch: rxMethod<{ person_id: number; name: string; role: string }>(
        pipe(
          tap((match) => {
            const tableElement = document.querySelector('app-dna-table');
            if (tableElement) {
              tableElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }

            // ⭐ Call store method (it's an rxMethod, so just call it)
            tableStore.filterByPerson({ personId: match.person_id, personRole: match.role });
          })
        )
      )
    };
  })
);
