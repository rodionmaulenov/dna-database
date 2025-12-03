import {signalStore, withFeature} from '@ngrx/signals';
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
    withUploadFeature(() => store.loadInitial())
  ),

  withDnaFormState(),


  withFeature((store) =>
    withExpansionFeature(store.disableEditMode),
  ),

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
      store.loadNextBackendPage,
      store.hasMoreBackendData,
      store.backendTotal,
      store.tableData,
      store.collapseAll,
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
        store.loadInitial(),
      store.clearSelection,
    )
  ),
);
