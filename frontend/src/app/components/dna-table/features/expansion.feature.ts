import {patchState, signalStoreFeature, withMethods, withState} from '@ngrx/signals';
import {Signal} from '@angular/core';

export function withExpansionFeature(disableEditMode: () => void) {
  return signalStoreFeature(
    withState({
      expandedRowId: null as number | null
    }),

    withMethods((store) => ({
      toggleExpandedRow: (personId: number) => {
        const currentId = store.expandedRowId();

        if (currentId === personId) {
          patchState(store, { expandedRowId: null });
          disableEditMode();
        } else {
          patchState(store, { expandedRowId: personId });
        }
      },

      isRowExpanded: (personId: number) => {
        return store.expandedRowId() === personId;
      },

      collapseAll: () => {
        patchState(store, { expandedRowId: null });
        disableEditMode();
      },
    })),
  );
}
