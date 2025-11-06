import { computed } from '@angular/core';
import { patchState, signalStore, withComputed, withMethods, withState } from '@ngrx/signals';
import { rxMethod } from '@ngrx/signals/rxjs-interop';
import { pipe, switchMap, tap, from, concatMap } from 'rxjs';
import { tapResponse } from '@ngrx/operators';
import { inject } from '@angular/core';
import { DNADataListResponse, initialState, TableRowData } from './models';
import { NotificationService } from '../../shared/services/notification.service';
import {DnaTableHttpService} from './dna-table.service';

export const DnaTableStore = signalStore(
  { providedIn: 'root' },

  withState(initialState),

  withComputed((store) => ({
    // Filtered data based on role
    filteredTableData: computed(() => {
      const filter = store.roleFilter();
      const allData = store.tableData();

      if (filter === 'parent') {
        return allData.filter(row => row.role === 'father' || row.role === 'mother');
      } else {
        return allData.filter(row => row.role === 'child');
      }
    }),

    // Get filtered person name
    filteredPersonName: computed(() => {
      const personId = store.currentPersonFilter();
      if (!personId) return null;

      const allData = store.tableData();
      const person = allData.find(row => row.personId === personId);
      return person?.name || null;
    }),
  })),

  withMethods((store) => {
    const httpService = inject(DnaTableHttpService);
    const notificationService = inject(NotificationService);

    // Helper: Build table rows from API response
    const buildTableRows = (response: DNADataListResponse): TableRowData[] => {
      const rows: TableRowData[] = [];

      response.data.forEach(item => {
        if (item.parent) {
          rows.push({
            id: item.id,
            personId: item.parent.id,
            overall_confidence: item.overall_confidence,
            uploaded_at: item.uploaded_at,
            name: item.parent.name,
            role: item.parent.role,
            file: item.file,
            loci_count: item.parent.loci_count,
            loci: item.parent.loci,
            relatedPersonId: item.child?.id || null,
            relatedPersonName: item.child?.name || null,
            relatedPersonRole: item.child?.role || null,
          });
        }

        if (item.child) {
          rows.push({
            id: item.id,
            personId: item.child.id,
            overall_confidence: item.overall_confidence,
            uploaded_at: item.uploaded_at,
            name: item.child.name,
            role: item.child.role,
            file: item.file,
            loci_count: item.child.loci_count,
            loci: item.child.loci,
            relatedPersonId: item.parent?.id || null,
            relatedPersonName: item.parent?.name || null,
            relatedPersonRole: item.parent?.role || null,
          });
        }
      });

      return rows;
    };

    return {
      // Set role filter
      setRoleFilter(filter: 'parent' | 'child') {
        patchState(store, {
          roleFilter: filter,
          expandedRowId: null
        });
      },

      // Toggle expanded row
      toggleExpandedRow(rowId: number) {
        const currentExpandedId = store.expandedRowId();
        patchState(store, {
          expandedRowId: currentExpandedId === rowId ? null : rowId
        });
      },

      // Check if row is expanded
      isRowExpanded(rowId: number): boolean {
        return store.expandedRowId() === rowId;
      },

      // Load table data using rxMethod + HTTP service
      loadTableData: rxMethod<{ personId?: number; page?: number }>(
        pipe(
          tap(() => patchState(store, { loading: true, expandedRowId: null })),
          switchMap(({ personId, page = 1 }) => {
            return httpService.loadTableData(personId, page, store.pageSize()).pipe(
              tapResponse({
                next: (response) => {
                  const rows = buildTableRows(response);

                  patchState(store, {
                    tableData: rows,
                    currentPage: page,
                    totalRecords: response.total || 0,
                    currentPersonFilter: personId || null,
                    loading: false,
                  });
                },
                error: (error) => {
                  console.error('Failed to load table data:', error);
                  patchState(store, {
                    tableData: [],
                    loading: false
                  });
                  notificationService.error('Failed to load table data');
                }
              })
            );
          })
        )
      ),

      // Filter by person
      filterByPerson: rxMethod<{ personId: number; personRole: string }>(
        pipe(
          tap(({ personRole }) => {
            const targetFilter = personRole === 'child' ? 'child' : 'parent';
            patchState(store, { roleFilter: targetFilter, loading: true });
          }),
          switchMap(({ personId }) => {
            return httpService.loadTableData(personId, 1, store.pageSize()).pipe(
              tapResponse({
                next: (response) => {
                  const rows = buildTableRows(response);

                  patchState(store, {
                    tableData: rows,
                    currentPage: 1,
                    totalRecords: response.total || 0,
                    currentPersonFilter: personId,
                    loading: false,
                    expandedRowId: null,
                  });

                  const personName = store.filteredPersonName();
                  if (personName) {
                    notificationService.info(`Filtered by: ${personName}`);
                  }
                },
                error: () => {
                  patchState(store, { loading: false });
                  notificationService.error('Failed to filter data');
                }
              })
            );
          })
        )
      ),

      // Clear person filter
      clearPersonFilter: rxMethod<void>(
        pipe(
          tap(() => patchState(store, { loading: true, expandedRowId: null })),
          switchMap(() => {
            return httpService.loadTableData(undefined, 1, store.pageSize()).pipe(
              tapResponse({
                next: (response) => {
                  const rows = buildTableRows(response);

                  patchState(store, {
                    tableData: rows,
                    currentPage: 1,
                    totalRecords: response.total || 0,
                    currentPersonFilter: null,
                    loading: false,
                  });

                  notificationService.info('Filter cleared');
                },
                error: () => {
                  patchState(store, { loading: false });
                  notificationService.error('Failed to clear filter');
                }
              })
            );
          })
        )
      ),

      // Update row (name + loci)
      updateRow: rxMethod<{
        row: TableRowData;
        nameUpdate?: string;
        lociUpdates: Array<{ id: number; allele_1: string; allele_2: string }>;
      }>(
        pipe(
          tap(({ row }) => {
            patchState(store, { updatingRowId: row.personId });
          }),
          switchMap(({ row, nameUpdate, lociUpdates }) => {
            const updates: Array<{ type: 'name' | 'locus'; data: any }> = [];

            if (nameUpdate) {
              updates.push({
                type: 'name',
                data: { id: row.personId, value: nameUpdate }
              });
            }

            lociUpdates.forEach(({ id, allele_1, allele_2 }) => {
              updates.push({
                type: 'locus',
                data: { id, allele_1, allele_2 }
              });
            });

            return from(updates).pipe(
              concatMap((update) => {
                if (update.type === 'name') {
                  return httpService.updatePerson(update.data.id, { name: update.data.value }).pipe(
                    tap(() => {
                      patchState(store, (state) => {
                        const rows = [...state.tableData];
                        const rowIndex = rows.findIndex(r => r.personId === row.personId);
                        if (rowIndex !== -1) {
                          rows[rowIndex] = { ...rows[rowIndex], name: update.data.value };
                        }
                        return { tableData: rows };
                      });
                    })
                  );
                } else {
                  return httpService.updateLocus(update.data.id, {
                    allele_1: update.data.allele_1,
                    allele_2: update.data.allele_2
                  }).pipe(
                    tap(() => {
                      patchState(store, (state) => {
                        const rows = [...state.tableData];
                        const rowIndex = rows.findIndex(r => r.personId === row.personId);
                        if (rowIndex !== -1) {
                          const loci = [...rows[rowIndex].loci];
                          const locusIndex = loci.findIndex(l => l.id === update.data.id);
                          if (locusIndex !== -1) {
                            loci[locusIndex] = {
                              ...loci[locusIndex],
                              allele_1: update.data.allele_1,
                              allele_2: update.data.allele_2
                            };
                            rows[rowIndex] = { ...rows[rowIndex], loci };
                          }
                        }
                        return { tableData: rows };
                      });
                    })
                  );
                }
              }),
              tapResponse({
                next: () => {
                  patchState(store, { updatingRowId: null });

                  const updatedFields = [];
                  if (nameUpdate) updatedFields.push('name');
                  if (lociUpdates.length > 0) updatedFields.push(`${lociUpdates.length} loci`);

                  if (updatedFields.length > 0) {
                    notificationService.success(`Updated: ${updatedFields.join(', ')}`);
                  }
                },
                error: (error: any) => {
                  patchState(store, { updatingRowId: null });
                  const errorMsg = error?.error?.message || error?.message || 'Failed to save changes';
                  notificationService.error(`Update failed: ${errorMsg}`);
                }
              })
            );
          })
        )
      ),

      // Refresh data
      refreshData() {
        this.loadTableData({
          personId: store.currentPersonFilter() || undefined,
          page: store.currentPage()
        });
      },

      // Change page
      changePage: rxMethod<{ page: number; pageSize?: number }>(
        pipe(
          tap(({ pageSize }) => {
            patchState(store, { expandedRowId: null, loading: true });

            if (pageSize && pageSize !== store.pageSize()) {
              patchState(store, { pageSize });
            }
          }),
          switchMap(({ page, pageSize: newPageSize }) => {
            const personId = store.currentPersonFilter();
            return httpService.loadTableData(personId || undefined, page, newPageSize || store.pageSize()).pipe(
              tapResponse({
                next: (response) => {
                  const rows = buildTableRows(response);

                  patchState(store, {
                    tableData: rows,
                    currentPage: page,
                    totalRecords: response.total || 0,
                    loading: false,
                  });
                },
                error: () => {
                  patchState(store, { loading: false });
                  notificationService.error('Failed to load page');
                }
              })
            );
          })
        )
      ),

      // Check if row is updating
      isRowUpdating(personId: number): boolean {
        return store.updatingRowId() === personId;
      },

      // Get file URL
      getFileUrl(filename: string): string {
        return httpService.getFileUrl(filename);
      },

      // Get related person label
      getRelatedPersonLabel(): string {
        return store.roleFilter() === 'parent' ? 'Child' : 'Parent';
      },

      // Add this method to withMethods()
      deleteRecord: rxMethod<number>(
        pipe(
          switchMap((uploadId) => {
            patchState(store, { loading: true });

            return httpService.deleteUpload(uploadId).pipe(
              tapResponse({
                next: () => {
                  patchState(store, (state) => {
                    const updatedData = state.tableData.filter(
                      row => row.id !== uploadId
                    );

                    return {
                      tableData: updatedData,
                      totalRecords: state.totalRecords - 1,
                      loading: false,
                      expandedRowId: null
                    };
                  });

                  notificationService.success('Record deleted successfully');
                },
                error: (error: any) => {
                  patchState(store, { loading: false });
                  const errorMsg = error?.error?.message || 'Failed to delete record';
                  notificationService.error(`Delete failed: ${errorMsg}`);
                }
              })
            );
          })
        )
      ),
    };
  })
);
