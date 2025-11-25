import {patchState, signalStoreFeature, withMethods, withState} from '@ngrx/signals';

export function withExpansionFeature() {
  return signalStoreFeature(
    withState({
      expandedRowId: null as number | null
    }),

    withMethods((store) => ({
      toggleExpandedRow: (personId: number) => {
        const currentId = store.expandedRowId();

        if (currentId === personId) {
          // Collapse if clicking same row
          patchState(store, { expandedRowId: null });
        } else {
          // Expand new row (auto-collapses previous)
          patchState(store, { expandedRowId: personId });
        }
      },

      isRowExpanded: (personId: number) => {
        return store.expandedRowId() === personId;
      },

      collapseAll: () => {
        patchState(store, { expandedRowId: null });
      },
    })),
  );
}
