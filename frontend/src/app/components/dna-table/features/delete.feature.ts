import {signalStoreFeature, withState, withMethods, patchState} from '@ngrx/signals';
import {inject} from '@angular/core';
import {rxMethod} from '@ngrx/signals/rxjs-interop';
import {pipe, switchMap, tap, catchError, EMPTY} from 'rxjs';
import {DnaTableHttpService} from '../dna-table.service';

export function withDeleteFeature(reload: () => void, clearSelection: () => void) {
  return signalStoreFeature(

    withState({
      deletingPersonIds: null as number[] | null,
      deletingFileId: null as number | null,
      isDeleting: false,
    }),

    // Methods
    withMethods((store) => {
      const service = inject(DnaTableHttpService);

      const deletePersons = rxMethod<number[]>(
        pipe(
          tap((personIds) =>
            patchState(store, {deletingPersonIds: personIds, isDeleting: true}),
          ),
          switchMap((personId) =>
            service.deletePersons(personId).pipe(
              tap(() => {
                patchState(store, {deletingPersonIds: null, isDeleting: false});
                clearSelection();
                reload();
              }),
              catchError(() => {
                patchState(store, {deletingPersonIds: null, isDeleting: false});
                return EMPTY;
              })
            )
          )
        )
      );

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
        deletePersons,
        deleteFile,

      };
    }),
  );
}
