import {signalStoreFeature, withState, withMethods, patchState} from '@ngrx/signals';

const ALL_LOCI = [
  'D1S1656', 'D2S441', 'D2S1338', 'D3S1358', 'D5S818',
  'D6S1043', 'D7S820', 'D8S1179', 'D10S1248', 'D12S391',
  'D13S317', 'D16S539', 'D18S51', 'D19S433', 'D21S11',
  'D22S1045', 'CSF1PO', 'FGA', 'TH01', 'TPOX', 'vWA',
  'Penta D', 'Penta E',
] as const;

interface LociTrackingState {
  pendingDeletedLoci: Map<number, number[]>;  // personId -> locusIds[]
  activeAddingPersonId: number | null;        // Which person is adding
}

export function withLocusFeature() {
  return signalStoreFeature(
    // State
    withState<LociTrackingState>({
      pendingDeletedLoci: new Map(),
      activeAddingPersonId: null
    }),

    // Methods
    withMethods((store) => ({
      // Start adding locus UI
      startAddingLocus: (personId: number) => {
        patchState(store, {
          activeAddingPersonId: personId
        });
      },

      // Cancel adding locus
      cancelAddingLocus: () => {
        patchState(store, {
          activeAddingPersonId: null
        });
      },

      // Track deleted locus (for backend sync)
      trackDeletedLocus: (personId: number, locusId: number) => {
        const deletedMap = new Map(store.pendingDeletedLoci());
        const existing = deletedMap.get(personId) || [];

        if (!existing.includes(locusId)) {
          deletedMap.set(personId, [...existing, locusId]);
          patchState(store, {
            pendingDeletedLoci: deletedMap
          });
        }
      },

      // Get deleted loci for person
      getDeletedLoci: (personId: number): number[] => {
        return store.pendingDeletedLoci().get(personId) || [];
      },

      // Clear deleted loci after successful update
      clearDeletedLoci: (personId: number) => {
        const deletedMap = new Map(store.pendingDeletedLoci());
        deletedMap.delete(personId);
        patchState(store, {
          pendingDeletedLoci: deletedMap
        });
      },

      // Get available loci for person
      getAvailableLoci: (usedLociNames: string[]): string[] => {
        return ALL_LOCI.filter(name => !usedLociNames.includes(name));
      },

      // Check if person is adding locus
      isAddingLocus: (personId: number): boolean => {
        return store.activeAddingPersonId() === personId;
      },

      // Check if person has deleted loci
      hasDeletedLoci: (personId: number): boolean => {
        const deleted = store.pendingDeletedLoci().get(personId);
        return deleted !== undefined && deleted.length > 0;
      },
    })),
  );
}
