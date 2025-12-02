import {patchState, signalStore, withFeature} from '@ngrx/signals';
import {withLoadFeature} from './features/load.feature';
import {withUploadFeature} from './features/upload.feature';
import {withDeleteFeature} from './features/delete.feature';
import {withDnaFormState} from './features/dna-form-state.feature';
import {withExpansionFeature} from './features/expansion.feature';
import {withTableActionsFeature} from './features/table-actions.feature';
import {withLocalFilterFeature} from './features/local-filter.feature';
import {WithTableSelection} from './features/table-selection.feature';


export const DnaTableStore = signalStore(
  {providedIn: 'root'},

  withLoadFeature(),

  withFeature((store) =>
    withUploadFeature(() => store.setDnaRecordsLoading())
  ),

  withExpansionFeature(),

  withDnaFormState(),

  withFeature((store) =>
    withTableActionsFeature(
      store.loadPersonLoci,
      store.setCurrentEditingPerson,
      store.toggleExpandedRow,
      store.isRowExpanded,
      store.personsArrayForm,
      store.reload,
      store.collapseAll,
    )
  ),

  withFeature((store) =>
    withLocalFilterFeature(
      store.tableData,
      (ids: string | null) => patchState(store, {remotePersonIds: ids}),
      (names: string | null) => patchState(store, {remotePersonNames: names}),
      (loading: boolean) => patchState(store, {isLoading: loading}),
      store.collapseAll,
      store.isLoading,
      store.reload,
    )
  ),

  withFeature((store) =>
    WithTableSelection(
      store.dataSource,
      store.selection
    )
  ),

  withFeature((store) =>
    withDeleteFeature(() =>
      store.setDnaRecordsLoading(),
      store.clearSelection,
    )
  ),
);
