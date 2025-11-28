import {inject} from '@angular/core';
import {patchState, signalStoreFeature, withMethods, withState} from '@ngrx/signals';
import {DnaTableHttpService} from '../dna-table.service';
import {CreateLocusData, LociUpdate, TableRowData} from '../../models';
import {FieldTree} from '@angular/forms/signals';
import {PersonsArrayFormData} from '../schemas/persons-array.schema';
import {rxMethod} from '@ngrx/signals/rxjs-interop';
import {catchError, EMPTY, pipe, switchMap, tap} from 'rxjs';


export function withTableActionsFeature(
  loadPersonLoci: (personId: number, loci: Array<{ id: number; locus_name: string; alleles: string }>) => void,
  setCurrentEditingPerson: (personId: number | null) => void,
  toggleExpandedRow: (personId: number) => void,
  isRowExpanded: (personId: number) => boolean,
  getDeletedLoci: (personId: number) => number[],
  clearDeletedLoci: (personId: number) => void,
  PersonsArrayForm: () => FieldTree<PersonsArrayFormData> | null,
  reload: () => void,
  collapseExpandableRow: () => void,
) {
  return signalStoreFeature(
    withState({
      personIdInTableRow: null as number | null
    }),

    withMethods((store) => {
      const httpService = inject(DnaTableHttpService);

      const updatePersonRx = rxMethod<{
        personId: number;
        updates: {
          name?: string;
          role?: string;
          loci?: LociUpdate[];
          new_loci?: CreateLocusData[];
          deleted_loci_ids?: number[];
        };
      }>(
        pipe(
          tap(({personId}) => {
            patchState(store, {personIdInTableRow: personId});
          }),
          switchMap(({personId, updates}) =>
            httpService.updatePerson(personId, updates).pipe(
              tap(() => {
                clearDeletedLoci(personId);
                setCurrentEditingPerson(null);
                patchState(store, {personIdInTableRow: null});
                collapseExpandableRow();
                reload();
              }),
              catchError(() => {
                patchState(store, {personIdInTableRow: null});
                return EMPTY;
              })
            )
          )
        )
      );


      return {
        toggle: (row: TableRowData) => {
          const wasExpanded = isRowExpanded(row.personId);

          if (wasExpanded) {
            // Closing
            setCurrentEditingPerson(null);
            toggleExpandedRow(row.personId);
          } else {
            // Opening
            toggleExpandedRow(row.personId);

            // ✅ Check if form already has data for this person
            const personsArrayForm = PersonsArrayForm();
            if (personsArrayForm) {
              const currentValue = personsArrayForm().value();
              const existingPerson = currentValue.persons.find(p => p.id === row.personId);

              // ✅ If form has loci data, use it (already updated from backend)
              if (existingPerson && existingPerson.loci.length > 0) {
                // Form already has data, don't reload
                setCurrentEditingPerson(row.personId);
                return;
              }
            }

            // ✅ Otherwise load from entity (first time opening)
            const lociData = row.loci.map(locus => ({
              id: locus.id,  // ✅ Include ID
              locus_name: locus.locus_name,
              alleles: `${locus.allele_1 || ''}, ${locus.allele_2 || ''}`
            }));

            loadPersonLoci(row.personId, lociData)
            setCurrentEditingPerson(row.personId);
          }
        },

        hasChanges: (row: TableRowData): boolean => {
          const personsArrayForm = PersonsArrayForm();
          if (!personsArrayForm) return false;

          const multiplePersonsForms = (personsArrayForm as any)['persons'];

          for (const personForm of multiplePersonsForms) {
            if (personForm().value()['id'] === row.personId) {
              const nameField = (personForm as any)['name'];
              const roleField = (personForm as any)['role'];
              const lociForms = (personForm as any)['loci'];

              // Check name/role dirty
              if (nameField().dirty() || roleField().dirty()) {
                return true;
              }

              // Check loci dirty
              if (lociForms && lociForms.length > 0) {
                for (let i = 0; i < lociForms.length; i++) {
                  const allelesField = (lociForms[i] as any)['alleles'];
                  if (allelesField && allelesField().dirty()) {
                    return true;
                  }
                }
              }

              // ✅ Check if has deleted loci
              if (getDeletedLoci(row.personId).length > 0) {
                return true;
              }

              // ✅ Check if has new loci (form has more loci than original)
              const formLociCount = lociForms ? lociForms.length : 0;
              const originalLociCount = row.loci.length;
              if (formLociCount > originalLociCount) {
                return true;
              }

              break;
            }
          }

          return false;
        },

        updateRow: (row: TableRowData) => {
          const personsArrayForm = PersonsArrayForm();
          if (!personsArrayForm) return;

          const multiplePersonsForms = (personsArrayForm as any)['persons'];
          let thePersonForm: any = null;

          for (const personForm of multiplePersonsForms) {
            if (personForm().value()['id'] === row.personId) {
              thePersonForm = personForm;
              break;
            }
          }

          if (!thePersonForm) return;

          const nameField = (thePersonForm as any)['name'];
          const roleField = (thePersonForm as any)['role'];
          const lociForms = (thePersonForm as any)['loci'];

          const nameUpdate = nameField().dirty() ? nameField().value() : undefined;
          const roleUpdate = roleField().dirty() ? roleField().value() : undefined;

          // ✅ Existing loci updates
          const lociUpdates: LociUpdate[] = [];

          // ✅ New loci to create
          const newLoci: CreateLocusData[] = [];

          if (lociForms && lociForms.length > 0) {
            for (let i = 0; i < lociForms.length; i++) {
              const locusField = lociForms[i];
              const allelesField = (locusField as any)['alleles'];
              const locusIdField = (locusField as any)['id'];  // ✅ Get ID from form
              const locusNameField = (locusField as any)['locus_name'];

              const allelesValue = allelesField ? allelesField().value() : '';
              const locusIdValue = locusIdField ? locusIdField().value() : 0;
              const locusNameValue = locusNameField ? locusNameField().value() : '';

              const parts = allelesValue.split(/[,\/]/).map((p: string) => p.trim());

              // ✅ Match by ID, not index
              if (locusIdValue > 0) {
                // EXISTING locus - update if dirty
                if (allelesField && allelesField().dirty()) {
                  const existingLocus = row.loci.find(l => l.id === locusIdValue);  // ✅ Find by ID
                  if (existingLocus) {
                    lociUpdates.push({
                      id: existingLocus.id,
                      locus_name: existingLocus.locus_name,
                      allele_1: parts[0] || '',
                      allele_2: parts[1] || ''
                    });
                  }
                }
              } else {
                // NEW locus - create if has data
                if (locusNameValue && allelesValue.trim()) {
                  newLoci.push({
                    locus_name: locusNameValue,
                    allele_1: parts[0] || '',
                    allele_2: parts[1] || ''
                  });
                }
              }
            }
          }

          const deletedLociIds = getDeletedLoci(row.personId);

          // ✅ Check if anything to update
          const hasChanges = nameUpdate !== undefined ||
            roleUpdate !== undefined ||
            lociUpdates.length > 0 ||
            newLoci.length > 0 ||
            deletedLociIds.length > 0;

          if (!hasChanges) return;

          // ✅ Call update
          updatePersonRx({
            personId: row.personId,
            updates: {
              name: nameUpdate,
              role: roleUpdate,
              loci: lociUpdates.length > 0 ? lociUpdates : undefined,
              new_loci: newLoci.length > 0 ? newLoci : undefined,
              deleted_loci_ids: deletedLociIds.length > 0 ? deletedLociIds : undefined
            }
          });
        },

        isUpdating: (row: TableRowData): boolean => {
          return store.personIdInTableRow() === row.personId;
        },

      };
    })
  );
}
