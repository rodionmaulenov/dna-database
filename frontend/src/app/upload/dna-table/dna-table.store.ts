import {computed} from '@angular/core';
import {patchState, signalStore, withComputed, withMethods, withState} from '@ngrx/signals';
import {rxMethod} from '@ngrx/signals/rxjs-interop';
import {pipe, switchMap, tap, from, concatMap} from 'rxjs';
import {tapResponse} from '@ngrx/operators';
import {inject} from '@angular/core';
import {DNADataListResponse, initialState, TableRowData} from './models';
import {NotificationService} from '../../shared/services/notification.service';
import {DnaTableHttpService} from './dna-table.service';

export const DnaTableStore = signalStore(
  {providedIn: 'root'},

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
          tap(() => patchState(store, {loading: true, expandedRowId: null})),
          switchMap(({personId, page = 1}) => {
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
          tap(({personRole}) => {
            const targetFilter = personRole === 'child' ? 'child' : 'parent';
            patchState(store, {roleFilter: targetFilter, loading: true});
          }),
          switchMap(({personId}) => {
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
                  patchState(store, {loading: false});
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
          tap(() => patchState(store, {loading: true, expandedRowId: null})),
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
                  patchState(store, {loading: false});
                  notificationService.error('Failed to clear filter');
                }
              })
            );
          })
        )
      ),

      // ✅ Method 1: Delete loci
      deleteLoci: rxMethod<{ row: TableRowData; locusIds: number[] }>(
        pipe(
          switchMap(({ row, locusIds }) => {
            return from(locusIds).pipe(
              concatMap(id => httpService.deleteLocus(id)),
              tapResponse({
                next: () => {
                  notificationService.success(`Deleted ${locusIds.length} loci`);
                },
                error: (error: any) => {
                  notificationService.error('Failed to delete loci');
                }
              })
            );
          })
        )
      ),

      // ✅ Method 2: Create new loci
      createLoci: rxMethod<{
        row: TableRowData;
        newLoci: Array<{ locus_name: string; allele_1: string; allele_2: string }>;
      }>(
        pipe(
          switchMap(({ row, newLoci }) => {
            return from(newLoci).pipe(
              concatMap(locus =>
                httpService.createLocus(row.personId, locus).pipe(
                  tap((response: any) => {
                    // Update state with new locus ID
                    patchState(store, (state) => {
                      const rows = [...state.tableData];
                      const rowIndex = rows.findIndex(r => r.personId === row.personId);
                      if (rowIndex !== -1) {
                        const loci = rows[rowIndex].loci.map(l => {
                          if (l.locus_name === locus.locus_name && l.id === null) {
                            return { ...l, id: response.data.id };
                          }
                          return l;
                        });
                        rows[rowIndex] = { ...rows[rowIndex], loci };
                      }
                      return { tableData: rows };
                    });
                  })
                )
              ),
              tapResponse({
                next: () => {
                  notificationService.success(`Created ${newLoci.length} new loci`);
                },
                error: () => {
                  notificationService.error('Failed to create loci');
                }
              })
            );
          })
        )
      ),

      // ✅ Method 3: Update existing loci
      updateLoci: rxMethod<{
        row: TableRowData;
        updates: Array<{ id: number; allele_1: string; allele_2: string }>;
      }>(
        pipe(
          switchMap(({ row, updates }) => {
            return from(updates).pipe(
              concatMap(update =>
                httpService.updateLocus(update.id, {
                  allele_1: update.allele_1,
                  allele_2: update.allele_2
                })
              ),
              tapResponse({
                next: () => {
                  notificationService.success(`Updated ${updates.length} loci`);
                },
                error: () => {
                  notificationService.error('Failed to update loci');
                }
              })
            );
          })
        )
      ),

      // ✅ Method 4: Update person info
      updatePersonInfo: rxMethod<{
        row: TableRowData;
        name?: string;
        role?: string;
      }>(
        pipe(
          switchMap(({ row, name, role }) => {
            const updates: any = {};
            if (name) updates.name = name;
            if (role) updates.role = role;

            return httpService.updatePerson(row.personId, updates).pipe(
              tap(() => {
                patchState(store, (state) => {
                  const rows = [...state.tableData];
                  const rowIndex = rows.findIndex(r => r.personId === row.personId);
                  if (rowIndex !== -1) {
                    rows[rowIndex] = { ...rows[rowIndex], ...updates };
                  }
                  return { tableData: rows };
                });
              }),
              tapResponse({
                next: () => {
                  const fields = Object.keys(updates).join(', ');
                  notificationService.success(`Updated: ${fields}`);
                },
                error: () => {
                  notificationService.error('Failed to update person info');
                }
              })
            );
          })
        )
      ),

      // ✅ Main method: Orchestrate all updates
      updateRow: rxMethod<{
        row: TableRowData;
        nameUpdate?: string;
        roleUpdate?: string;
        lociUpdates: Array<{
          id: number | null;
          locus_name?: string;
          allele_1: string;
          allele_2: string;
        }>;
        deletedLociIds?: number[];
      }>(
        pipe(
          tap(({ row }) => {
            patchState(store, { updatingRowId: row.personId });
          }),
          switchMap(({ row, nameUpdate, roleUpdate, lociUpdates, deletedLociIds = [] }) => {
            const operations = [];

            // 1. Delete loci
            if (deletedLociIds.length > 0) {
              operations.push(
                from(deletedLociIds).pipe(
                  concatMap(id => httpService.deleteLocus(id))
                )
              );
            }

            // 2. Update person info
            if (nameUpdate || roleUpdate) {
              const updates: any = {};
              if (nameUpdate) updates.name = nameUpdate;
              if (roleUpdate) updates.role = roleUpdate;
              operations.push(httpService.updatePerson(row.personId, updates));
            }

            // 3. Create new loci
            const newLoci = lociUpdates.filter(l => l.id === null);
            if (newLoci.length > 0) {
              operations.push(
                from(newLoci).pipe(
                  concatMap(locus =>
                    httpService.createLocus(row.personId, {
                      locus_name: locus.locus_name!,
                      allele_1: locus.allele_1,
                      allele_2: locus.allele_2
                    })
                  )
                )
              );
            }

            // 4. Update existing loci
            const existingLoci = lociUpdates.filter(l => l.id !== null);
            if (existingLoci.length > 0) {
              operations.push(
                from(existingLoci).pipe(
                  concatMap(locus =>
                    httpService.updateLocus(locus.id!, {
                      allele_1: locus.allele_1,
                      allele_2: locus.allele_2
                    })
                  )
                )
              );
            }

            return from(operations).pipe(
              concatMap(op => op),
              tapResponse({
                next: () => {
                  patchState(store, { updatingRowId: null });
                  notificationService.success('Updated successfully');
                },
                error: (error: any) => {
                  patchState(store, { updatingRowId: null });
                  notificationService.error('Update failed');
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
          tap(({pageSize}) => {
            patchState(store, {expandedRowId: null, loading: true});

            if (pageSize && pageSize !== store.pageSize()) {
              patchState(store, {pageSize});
            }
          }),
          switchMap(({page, pageSize: newPageSize}) => {
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
                  patchState(store, {loading: false});
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

      // Get related person label
      getRelatedPersonLabel(): string {
        return store.roleFilter() === 'parent' ? 'Child' : 'Parent';
      },

      // Add this method to withMethods()
      deleteRecord: rxMethod<number>(
        pipe(
          switchMap((uploadId) => {
            patchState(store, {loading: true});

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
                  patchState(store, {loading: false});
                  const errorMsg = error?.error?.message || 'Failed to delete record';
                  notificationService.error(`Delete failed: ${errorMsg}`);
                }
              })
            );
          })
        )
      ),

      addLocusToRow(personId: number, locusName: string) {
        patchState(store, (state) => {
          const rows = [...state.tableData];
          const rowIndex = rows.findIndex(r => r.personId === personId);

          if (rowIndex !== -1) {
            const newLocus = {
              id: null as any,
              locus_name: locusName,
              allele_1: '',
              allele_2: ''
            };

            rows[rowIndex] = {
              ...rows[rowIndex],
              loci: [...rows[rowIndex].loci, newLocus]
            };
          }

          return {tableData: rows};
        });
      },

      removeLocusFromRow(personId: number, index: number) {
        patchState(store, (state) => {
          const rows = [...state.tableData];
          const rowIndex = rows.findIndex(r => r.personId === personId);

          if (rowIndex !== -1) {
            const loci = [...rows[rowIndex].loci];
            loci.splice(index, 1);

            rows[rowIndex] = {
              ...rows[rowIndex],
              loci
            };
          }

          return {tableData: rows};
        });
      },
    };
  })
);
