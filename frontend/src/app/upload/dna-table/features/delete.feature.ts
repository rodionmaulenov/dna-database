import {signalStoreFeature, withState, withMethods, patchState} from '@ngrx/signals';
import {inject} from '@angular/core';
import {rxMethod} from '@ngrx/signals/rxjs-interop';
import {pipe, switchMap, tap, catchError, EMPTY} from 'rxjs';
import {DnaTableHttpService} from '../dna-table.service';

export function withDeleteFeature(reload: () => void) {
  return signalStoreFeature(
    // State
    withState({
      deletingPersonId: null as number | null,
      deletingFileId: null as number | null,
    }),

    // Methods
    withMethods((store) => {
      const service = inject(DnaTableHttpService);

      // ✅ Delete person
      const deletePerson = rxMethod<number>(
        pipe(
          tap((personId) =>
            patchState(store, {deletingPersonId: personId})
          ),
          switchMap((personId) =>
            service.deletePerson(personId).pipe(
              tap(() => {
                patchState(store, {deletingPersonId: null});
                reload();
              }),
              catchError(() => {
                patchState(store, {deletingPersonId: null});
                return EMPTY;
              })
            )
          )
        )
      );

      // ✅ Delete file (reactive)
      const deleteFile = rxMethod<{ personId: number; fileId: number }>(
        pipe(
          tap(({fileId}) =>
            patchState(store, {deletingFileId: fileId})
          ),
          switchMap(({fileId}) =>
            service.deleteFile(fileId).pipe(
              tap(() => {
                patchState(store, {deletingFileId: null});
                reload();
              }),
              catchError(() => {
                patchState(store, {deletingFileId: null})
                return EMPTY;
              })
            )
          )
        )
      );

      return {
        deletePerson,

        deleteFile,

      };
    }),
  );
}
