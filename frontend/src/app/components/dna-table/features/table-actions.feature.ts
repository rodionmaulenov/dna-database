import {inject} from '@angular/core';
import {patchState, signalStoreFeature, withMethods, withState} from '@ngrx/signals';
import {DnaTableHttpService} from '../dna-table.service';
import {LociUpdate, TableRowData} from '../../models';
import {FieldTree} from '@angular/forms/signals';
import {PersonsArrayFormData} from '../schemas/persons-array.schema';
import {rxMethod} from '@ngrx/signals/rxjs-interop';
import {catchError, EMPTY, pipe, switchMap, tap} from 'rxjs';


export function withTableActionsFeature(
  loadPersonLoci: (personId: number, loci: Array<{ id: number; locus_name: string; alleles: string }>) => void,
  setCurrentEditingPerson: (personId: number | null) => void,
  toggleExpandedRow: (personId: number) => void,
  isRowExpanded: (personId: number) => boolean,
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
        };
      }>(
        pipe(
          tap(({personId}) => {
            patchState(store, {personIdInTableRow: personId});
          }),
          switchMap(({personId, updates}) =>
            httpService.updatePerson(personId, updates).pipe(
              tap(() => {
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
            setCurrentEditingPerson(null);
            toggleExpandedRow(row.personId);
          } else {
            toggleExpandedRow(row.personId);

            const personsArrayForm = PersonsArrayForm();
            if (personsArrayForm) {
              const currentValue = personsArrayForm().value();
              const existingPerson = currentValue.persons.find(p => p.id === row.personId);

              if (existingPerson && existingPerson.loci.length > 0) {
                setCurrentEditingPerson(row.personId);
                return;
              }
            }

            const lociData = row.loci.map(locus => ({
              id: locus.id,
              locus_name: locus.locus_name,
              alleles: `${locus.allele_1 || ''}, ${locus.allele_2 || ''}`
            }));

            loadPersonLoci(row.personId, lociData);
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

              if (nameField().dirty() || roleField().dirty()) {
                return true;
              }

              if (lociForms && lociForms.length > 0) {
                for (let i = 0; i < lociForms.length; i++) {
                  const allelesField = (lociForms[i] as any)['alleles'];
                  if (allelesField && allelesField().dirty()) {
                    return true;
                  }
                }
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

          // ✅ Collect ALL loci (send all 23, backend handles create/update)
          const lociUpdates: LociUpdate[] = [];

          if (lociForms && lociForms.length > 0) {
            for (let i = 0; i < lociForms.length; i++) {
              const locusField = lociForms[i];
              const allelesField = (locusField as any)['alleles'];
              const locusNameField = (locusField as any)['locus_name'];

              const allelesValue = allelesField ? allelesField().value() : '';
              const locusNameValue = locusNameField ? locusNameField().value() : '';

              const parts = allelesValue.split(/[,\/]/).map((p: string) => p.trim());

              // ✅ Send all loci with locus_name
              lociUpdates.push({
                locus_name: locusNameValue,
                allele_1: parts[0] || '',
                allele_2: parts[1] || ''
              });
            }
          }

          const hasChanges = nameUpdate !== undefined ||
            roleUpdate !== undefined ||
            lociUpdates.some(l => l.allele_1 || l.allele_2);

          if (!hasChanges) return;

          updatePersonRx({
            personId: row.personId,
            updates: {
              name: nameUpdate,
              role: roleUpdate,
              loci: lociUpdates.length > 0 ? lociUpdates : undefined
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
