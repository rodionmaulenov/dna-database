import {
  patchState, signalStoreFeature, withComputed, withHooks, withMethods, withProps, withState
} from '@ngrx/signals';
import {computed, effect, Signal, untracked} from '@angular/core';
import {RelatedPerson, TableRowData} from '../../models';
import {MatTableDataSource} from '@angular/material/table';
import {SelectionModel} from '@angular/cdk/collections';


export function withLocalFilterFeature(
  loadNextBackendPage: () => void,
  hasMoreBackendData: Signal<boolean>,
  backendTotal: Signal<number>,
  tableData: Signal<TableRowData[]>,
  collapseExpandable: () => void,
) {
  return signalStoreFeature(
    withState({
      localRoleFilter: 'parent' as 'parent' | 'child' | null,
      filteredPersons: [] as Array<{ id: number; name: string; role: string }>,
      localPageIndex: 0,
      localPageSize: 20,
    }),

    withProps(() => ({
      _dataSource: new MatTableDataSource<TableRowData>([]),
      selection: new SelectionModel<TableRowData>(true, []),
    })),

    withComputed((store) => {

      const filteredData = computed(() => {
        const data = tableData();
        const roleFilter = store.localRoleFilter();
        const personFilter = store.filteredPersons();

        let result = data;

        // Filter by specific persons
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
            // ✅ No role filter - show all rows related to filtered persons
            result = result.filter(row => {
              // Row is the filtered person
              if (filterIds.includes(row.personId)) return true;
              // Row is related to filtered person
              if (row.relatedPersonId && filterIds.includes(row.relatedPersonId)) return true;
              // Row has related persons that match filter
              return !!row.relatedPersons?.some(rp => filterIds.includes(rp.id));
            });
          }
        } else {
          // No person filter - just role filter
          if (roleFilter === 'parent') {
            result = result.filter(row => row.role === 'father' || row.role === 'mother');
          } else if (roleFilter === 'child') {
            result = result.filter(row => row.role === 'child');
          }
          // ✅ roleFilter null + no person filter = show all
        }

        return result;
      });

      const paginatedData = computed(() => {
        const data = filteredData();
        const start = store.localPageIndex() * store.localPageSize();
        const end = start + store.localPageSize();
        return data.slice(start, end);
      });

      const filteredTotal = computed(() => {
        const localFiltered = filteredData().length;
        const total = backendTotal();

        return hasMoreBackendData()
          ? total
          : localFiltered;
      })

      const dataSource = computed(() => store._dataSource);

      return {
        filteredData,
        paginatedData,
        filteredTotal,
        dataSource,
      };

    }),

    // ========== METHODS ==========
    withMethods((store) => ({

      setRoleFilter: (role: 'parent' | 'child' | null) => {
        collapseExpandable();
        patchState(store, {localRoleFilter: role, localPageIndex: 0});
      },

      setLocalPage: (pageIndex: number) => {
        const totalFiltered = store.filteredTotal();
        const nextStart = pageIndex * store.localPageSize();

        if (nextStart < totalFiltered) {
          collapseExpandable();
          patchState(store, { localPageIndex: pageIndex });
        }
        else if (hasMoreBackendData()) {
          loadNextBackendPage();  // Replace old data
          patchState(store, { localPageIndex: 0 });  // Start fresh
        }
      },

      filterByPerson: (person: { personId: number; personName: string; role: string }) => {
        collapseExpandable();
        patchState(store, {
          filteredPersons: [{id: person.personId, name: person.personName, role: person.role}],
          localRoleFilter: person.role === 'child' ? 'child' : 'parent',
          localPageIndex: 0
        });
      },

      filterByMultiplePersons: (persons: RelatedPerson[]) => {
        collapseExpandable();
        const firstRole = persons[0]?.role;
        patchState(store, {
          filteredPersons: persons,
          localRoleFilter: firstRole === 'child' ? 'child' : 'parent',
          localPageIndex: 0
        });
      },

      removeFilter: (personId: number) => {
        patchState(store, {
          filteredPersons: store.filteredPersons().filter(p => p.id !== personId),
        });
        if (store.filteredPersons().length === 0) {
          patchState(store, {localRoleFilter: 'parent'})
        }
      },

      clearFilter: () => {
        collapseExpandable();
        patchState(store, {
          filteredPersons: [],
          localRoleFilter: 'parent',
          localPageIndex: 0
        });
      },
    })),

    withHooks({
      onInit(store) {
        effect(() => {
          const paginated = store.paginatedData();

          untracked(() => {
            store._dataSource.data = paginated;
            store.selection.clear();
          });
        });
      }
    }),
  );
}
