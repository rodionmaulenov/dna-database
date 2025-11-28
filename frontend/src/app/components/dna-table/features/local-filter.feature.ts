import {
  patchState, signalStoreFeature, withComputed, withHooks, withMethods, withProps, withState
} from '@ngrx/signals';
import {computed, effect, Signal, untracked} from '@angular/core';
import {TableRowData} from '../../models';
import {MatTableDataSource} from '@angular/material/table';
import {SelectionModel} from '@angular/cdk/collections';

export function withLocalFilterFeature(
  tableData: Signal<TableRowData[]>,
  setRemotePersonIds: (ids: string | null) => void,
  setRemotePersonNames: (names: string | null) => void,
  setLoading: (loading: boolean) => void,
  collapseExpandable: () => void,
  isLoading: Signal<boolean>,
  reload: () => void,
) {
  return signalStoreFeature(

    withState({
      localRoleFilter: 'parent' as 'parent' | 'child' | null
    }),

    withProps(() => ({
      _dataSource: new MatTableDataSource<TableRowData>([]),
      selection: new SelectionModel<TableRowData>(true, []),
    })),

    withComputed((store) => {

      const filteredData = computed(() => {
        const data = tableData();
        const roleFilter = store.localRoleFilter();

        if (!roleFilter) {
          return data;
        } else if (roleFilter === 'parent') {
          return data.filter(row => row.role === 'father' || row.role === 'mother');
        } else if (roleFilter === 'child') {
          return data.filter(row => row.role === 'child');
        }
        return data;
      });

      const dataSource = computed(() => store._dataSource);

      return {
        filteredData,
        dataSource,
      };
    }),

    // ========== METHODS ==========
    withMethods((store) => ({

      setRoleFilter: (role: 'parent' | 'child' | null) => {
        collapseExpandable();
        patchState(store, {localRoleFilter: role});
      },

      filterByPerson: (personId: number, personRole: string, personName: string) => {
        collapseExpandable();
        setLoading(true);
        setRemotePersonIds(personId.toString());
        setRemotePersonNames(personName);

        const newRoleFilter = personRole === 'child' ? 'child' : 'parent';

        reload();

        const checkLoading = setInterval(() => {
          if (!isLoading()) {
            patchState(store, {localRoleFilter: newRoleFilter});
            clearInterval(checkLoading);
          }
        }, 50);
      },

      filterByMultiplePersons: (personIds: number[], personsRole: string, count: number) => {
        collapseExpandable();
        const idsString = personIds.join(',');
        const displayText = `${count} related persons`;

        setRemotePersonIds(idsString);
        setRemotePersonNames(displayText);

        if (personsRole === 'child') {
          patchState(store, {localRoleFilter: 'child'});
        } else {
          patchState(store, {localRoleFilter: 'parent'});
        }
        reload();
      },

      clearFilter: () => {
        collapseExpandable();
        setRemotePersonIds(null);
        setRemotePersonNames(null);
        patchState(store, {localRoleFilter: 'parent'});
        reload();
      },

    })),

    withHooks({
      onInit(store) {
        effect(() => {
          const filtered = store.filteredData();

          untracked(() => {
            store._dataSource.data = filtered;
            store.selection.clear();
          });
        });
      }
    }),
  );
}
