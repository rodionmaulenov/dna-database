import {
  patchState, signalStoreFeature, withComputed, withHooks, withMethods, withProps, withState
} from '@ngrx/signals';
import {computed, effect, Signal, untracked} from '@angular/core';
import {TableRowData} from '../../models';
import {MatTableDataSource} from '@angular/material/table';
import {SelectionModel} from '@angular/cdk/collections';

export function withLocalFilterFeature(
  tableData: Signal<TableRowData[]>,
  collapseExpandable: () => void,
) {
  return signalStoreFeature(

    withState({
      localRoleFilter: 'parent' as 'parent' | 'child' | null,
      filteredPersons: [] as Array<{ id: number; name: string; role: string }>,
    }),

    withProps(() => ({
      _dataSource: new MatTableDataSource<TableRowData>([]),
      selection: new SelectionModel<TableRowData>(true, []),
    })),

    withComputed((store) => {
      // ✅ Filter only - no pagination
      const filteredData = computed(() => {
        const data = tableData();
        const roleFilter = store.localRoleFilter();
        const personFilter = store.filteredPersons();

        let result = data;

        if (personFilter.length > 0) {
          const filterIds = personFilter.map(p => p.id);

          if (roleFilter === 'parent') {
            result = result.filter(row => {
              if (row.role !== 'father' && row.role !== 'mother') return false;
              if (filterIds.includes(row.personId)) return true;
              if (row.relatedPersonId && filterIds.includes(row.relatedPersonId)) return true;
              return !!row.relatedPersons?.some(rp => filterIds.includes(rp.id));
            });
          } else if (roleFilter === 'child') {
            result = result.filter(row => {
              if (row.role !== 'child') return false;
              if (filterIds.includes(row.personId)) return true;
              return !!(row.relatedPersonId && filterIds.includes(row.relatedPersonId));
            });
          } else {
            result = result.filter(row => {
              if (filterIds.includes(row.personId)) return true;
              if (row.relatedPersonId && filterIds.includes(row.relatedPersonId)) return true;
              return !!row.relatedPersons?.some(rp => filterIds.includes(rp.id));
            });
          }
        } else {
          if (roleFilter === 'parent') {
            result = result.filter(row => row.role === 'father' || row.role === 'mother');
          } else if (roleFilter === 'child') {
            result = result.filter(row => row.role === 'child');
          }
        }

        return result;
      });

      const filteredTotal = computed(() => filteredData().length);
      const dataSource = computed(() => store._dataSource);

      return {
        filteredData,
        filteredTotal,
        dataSource,
      };
    }),

    withMethods((store) => ({

      setRoleFilter: (role: 'parent' | 'child' | null) => {
        collapseExpandable();
        patchState(store, { localRoleFilter: role });
      },

      filterByPerson: (person: { personId: number; personName: string; role: string }) => {
        collapseExpandable();
        patchState(store, {
          filteredPersons: [{ id: person.personId, name: person.personName, role: person.role }],
          localRoleFilter: person.role === 'child' ? 'child' : 'parent',
        });
      },

      filterByMultiplePersons: (persons: Array<{ id: number; name: string; role: string }>) => {
        collapseExpandable();
        const firstRole = persons[0]?.role;
        patchState(store, {
          filteredPersons: persons,
          localRoleFilter: firstRole === 'child' ? 'child' : 'parent',
        });
      },

      removeFilter: (personId: number) => {
        const remaining = store.filteredPersons().filter(p => p.id !== personId);
        patchState(store, { filteredPersons: remaining });
      },

      clearFilter: () => {
        collapseExpandable();
        patchState(store, {
          filteredPersons: [],
          localRoleFilter: 'parent',
        });
      },

    })),

    withHooks({
      onInit(store) {
        effect(() => {
          const data = store.filteredData();

          untracked(() => {
            store._dataSource.data = data;
            store.selection.clear();
          });
        });
      }
    }),
  );
}
