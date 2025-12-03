import {signalStoreFeature, withState, withComputed, withMethods, patchState, withHooks} from '@ngrx/signals';
import {withEntities, setAllEntities} from '@ngrx/signals/entities';
import {inject, computed} from '@angular/core';
import {rxMethod} from '@ngrx/signals/rxjs-interop';
import {pipe, switchMap, tap, catchError, EMPTY} from 'rxjs';
import {dnaEntityConfig} from '../dna-table.entity';
import {DnaTableHttpService} from '../dna-table.service';
import {TableRowData} from '../models';
import {DnaRecord} from '../../models';

export function withLoadFeature() {
  return signalStoreFeature(
    withEntities(dnaEntityConfig),

    withState({
      backendPageIndex: 0,
      backendTotal: 0,
      total: 0,
      isLoading: true,
      error: null,
    }),

    withMethods((store) => {
      const service = inject(DnaTableHttpService);

      const loadData = rxMethod<{ page: number; append: boolean }>(
        pipe(
          tap(() => {
            patchState(store, { isLoading: true, error: null });
          }),
          switchMap(({ page, append }) => {
            return service.loadTableData(page + 1, 20).pipe(
              tap(response => {
                if (append) {
                  // ✅ Append to existing entities
                  const existing = store.dnaRecordsEntities();
                  const newIds = response.data.map((r: DnaRecord) => r.id);
                  const filtered = existing.filter(e => !newIds.includes(e.id));
                  patchState(
                    store,
                    setAllEntities([...filtered, ...response.data], {collection: 'dnaRecords'}),
                    { backendPageIndex: page, backendTotal: response.total, isLoading: false }
                  );
                } else {
                  // ✅ Replace entities
                  patchState(
                    store,
                    setAllEntities(response.data, {collection: 'dnaRecords'}),
                    { backendPageIndex: page, backendTotal: response.total, isLoading: false }
                  );
                }
              }),
              catchError(error => {
                patchState(store, { isLoading: false, error: error.message });
                return EMPTY;
              })
            );
          })
        )
      );

      return {
        loadInitial: () => loadData({ page: 0, append: false }),
        loadNextBackendPage: () => loadData({ page: store.backendPageIndex() + 1, append: true }),
        reload: () => loadData({ page: 0, append: false }),
      };
    }),

    withHooks({
      onInit(store) {
        store.loadInitial();
      }
    }),

    withComputed((store) => {
      const transformToTableData = (records: DnaRecord[]): TableRowData[] => {
        const tableData: TableRowData[] = [];

        records.forEach(record => {
          // Parent row
          if (record.parent) {
            const relatedPersons = record.children?.length
              ? record.children.map(c => ({id: c.id, name: c.name, role: c.role}))
              : record.child
                ? [{id: record.child.id, name: record.child.name, role: record.child.role}]
                : null;

            tableData.push({
              id: record.id,
              personId: record.parent.id,
              name: record.parent.name,
              role: record.parent.role as any,
              loci_count: record.parent.loci_count,
              file: record.parent.files?.[0]?.file || '',
              files: record.parent.files || [],
              loci: record.parent.loci || [],
              relatedPersonId: relatedPersons?.[0]?.id || null,
              relatedPersonName: relatedPersons?.[0]?.name || null,
              relatedPersonRole: relatedPersons?.[0]?.role || null,
              relatedPersons: (relatedPersons && relatedPersons.length > 1) ? relatedPersons : null
            });
          }

          // Single child
          if (record.child) {
            tableData.push({
              id: record.id,
              personId: record.child.id,
              name: record.child.name,
              role: record.child.role as any,
              loci_count: record.child.loci_count,
              file: record.child.files?.[0]?.file || '',
              files: record.child.files || [],
              loci: record.child.loci || [],
              relatedPersonId: record.parent?.id || null,
              relatedPersonName: record.parent?.name || null,
              relatedPersonRole: record.parent?.role || null,
              relatedPersons: null
            });
          }

          // ✅ ADD: Multiple children (with or without parent)
          if (record.children?.length) {
            record.children.forEach(child => {
              tableData.push({
                id: record.id,
                personId: child.id,
                name: child.name,
                role: child.role as any,
                loci_count: child.loci_count,
                file: child.files?.[0]?.file || '',
                files: child.files || [],
                loci: child.loci || [],
                relatedPersonId: record.parent?.id || null,
                relatedPersonName: record.parent?.name || null,
                relatedPersonRole: record.parent?.role || null,
                relatedPersons: null
              });
            });
          }
        });

        return tableData;
      };

      return {
        tableData: computed(() => {
          const entities = store.dnaRecordsEntities();
          return transformToTableData(entities);
        }),

        hasMoreBackendData: computed(() => {
          const loaded = store.dnaRecordsEntities().length;
          return loaded < store.backendTotal();
        }),

      };
    })
  );
}
