import {patchState, signalStore, withFeature} from '@ngrx/signals';
import {withLoadFeature} from './features/load.feature';
import {withUploadFeature} from './features/upload.feature';
import {withDeleteFeature} from './features/delete.feature';
import {withLocusFeature} from './features/locus.feature';
import {withDnaFormState} from './features/dna-form-state.feature';
import {withDnaFormActions} from './features/dna-form-actions.feature';
import {withExpansionFeature} from './features/expansion.feature';
import {withTableActionsFeature} from './features/table-actions.feature';
import {withLocalFilterFeature} from './features/local-filter.feature';


export const DnaTableStore = signalStore(
  {providedIn: 'root'},


  withLoadFeature(),

  withFeature((store) =>
    withUploadFeature(() => store.setDnaRecordsLoading())
  ),

  withFeature((store) =>
    withDeleteFeature(() => store.setDnaRecordsLoading())
  ),

  withExpansionFeature(),

  withLocusFeature(),

  withDnaFormState(),

  withFeature((store) =>
    withDnaFormActions(
      store.addLocusToPersonById,
      store.removeLocusFromPersonById,
      store.setCurrentEditingPerson,
    )
  ),

  withFeature((store) =>
    withTableActionsFeature(
      store.loadPersonLoci,
      store.setCurrentEditingPerson,
      store.toggleExpandedRow,
      store.isRowExpanded,
      store.getDeletedLoci,
      store.clearDeletedLoci,
      store.personsArrayForm,
      store.reload,
      store.collapseAll,
    )
  ),

  withFeature((store) =>
    withLocalFilterFeature(
      store.tableData,
      (ids: string | null) => patchState(store, {remotePersonIds: ids}),
      (names: string | null) => patchState(store, { remotePersonNames: names }),
      (loading: boolean) => patchState(store, { isLoading: loading }),
      store.collapseAll,
      store.isLoading,
      store.reload,
      store.resetForm,
    )
  ),
);
