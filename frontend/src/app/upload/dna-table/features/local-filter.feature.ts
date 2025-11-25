import {signalStoreFeature, withState, withMethods, withComputed, patchState} from '@ngrx/signals';
import {computed, Signal} from '@angular/core';
import {TableRowData} from '../../models';

export function withLocalFilterFeature(
  tableData: Signal<TableRowData[]>,
  setRemotePersonIds: (ids: string | null) => void,
  setRemotePersonNames: (names: string | null) => void,
  setLoading: (loading: boolean) => void,
  isLoading: Signal<boolean>,
  reload: () => void,
  resetForm: () => void
) {
  return signalStoreFeature(
    withState({
      localRoleFilter: 'parent' as 'parent' | 'child' | null
    }),

    withMethods((store) => ({

      setRoleFilter: (role: 'parent' | 'child' | null) => {
        patchState(store, {localRoleFilter: role});
      },

      // withLocalFilterFeature
      filterByPerson: (personId: number, personRole: string, personName: string) => {
        // ✅ DON'T set role yet
        setLoading(true);
        setRemotePersonIds(personId.toString());
        setRemotePersonNames(personName);
        resetForm();

        const newRoleFilter = personRole === 'child' ? 'child' : 'parent';

        // ✅ Set role AFTER data loaded (use setTimeout as simple solution)
        reload();

        // Apply role when loading finishes
        const checkLoading = setInterval(() => {
          if (!isLoading()) {
            patchState(store, { localRoleFilter: newRoleFilter });
            clearInterval(checkLoading);
          }
        }, 50);
      },

      filterByMultiplePersons: (personIds: number[], personsRole: string, count: Number[]) => {
        const idsString = personIds.join(',');
        const displayText = `${count} related persons`;

        setRemotePersonIds(idsString);
        setRemotePersonNames(displayText);

        if (personsRole === 'child') {
          patchState(store, {localRoleFilter: 'child'});
        } else {
          patchState(store, {localRoleFilter: 'parent'});
        }
        resetForm();
        reload();
      },

      clearFilter: () => {
        setRemotePersonIds(null);
        setRemotePersonNames(null);
        patchState(store, {localRoleFilter: 'parent'});
        resetForm();
        reload();
      }
    })),

    withComputed((store) => ({
      // ✅ Filter tableData by local role only
      filteredTableData: computed(() => {
        const data = tableData();
        const roleFilter = store.localRoleFilter();

        if (!roleFilter) return data;

        if (roleFilter === 'parent') {
          return data.filter(row => row.role === 'father' || row.role === 'mother');
        } else if (roleFilter === 'child') {
          return data.filter(row => row.role === 'child');
        }

        return data;
      }),
    }))
  );
}
