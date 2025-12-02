import {patchState, signalStoreFeature, withMethods, withState} from '@ngrx/signals';
import {FieldTree, form} from '@angular/forms/signals';
import {signal} from '@angular/core';
import {PersonsArrayFormData, personsArraySchema} from '../schemas/persons-array.schema';

const ALL_LOCI = [
  'D1S1656', 'D2S441', 'D2S1338', 'D3S1358', 'D5S818',
  'D6S1043', 'D7S820', 'D8S1179', 'D10S1248', 'D12S391',
  'D13S317', 'D16S539', 'D18S51', 'D19S433', 'D21S11',
  'D22S1045', 'CSF1PO', 'FGA', 'TH01', 'TPOX', 'vWA',
  'Penta D', 'Penta E',
] as const;


export function withDnaFormState() {

  const personsSignal = signal<PersonsArrayFormData>({persons: []});
  let personsArrayForm: FieldTree<PersonsArrayFormData> | null = null;

  return signalStoreFeature(
    withState({
      editingPersonIdInTableRow: null as number | null,
      isEditingTableRow: false,
    }),

    withMethods((store) => {

      if (!personsArrayForm) {
        personsArrayForm = form(personsSignal, personsArraySchema);
      }

      return {

        personsArrayForm: () => personsArrayForm,
        personsSignal: () => personsSignal,

        setCurrentEditingPerson: (personId: number | null): void => {
          patchState(store, {editingPersonIdInTableRow: personId, isEditingTableRow: personId !== null});
        },

        loadPerson: (person: {
          id: number;
          name: string;
          role: 'father' | 'mother' | 'child';
        }): void => {
          personsSignal.update(data => {
            const exists = data.persons.some(p => p.id === person.id);
            if (exists) return data;

            return {
              persons: [...data.persons, {
                id: person.id,
                name: person.name,
                role: person.role,
                loci: []
              }]
            };
          });
        },

        loadPersonLoci: (personId: number, loci: Array<{ id: number; locus_name: string; alleles: string }>): void => {
          personsSignal.update(data => ({
            persons: data.persons.map(p => {
              if (p.id !== personId) return p;

              // ✅ Create all 23 loci, fill with existing data
              const fullLoci = ALL_LOCI.map(locusName => {
                const existing = loci.find(l => l.locus_name === locusName);
                return {
                  id: existing?.id || 0,
                  locus_name: locusName,
                  alleles: existing?.alleles || ''
                };
              });

              return { ...p, loci: fullLoci };
            })
          }));
        },

        updatePersonById: (personId: number, updates: {
          name?: string;
          role?: 'father' | 'mother' | 'child';
        }): void => {
          personsSignal.update(data => ({
            persons: data.persons.map(p =>
              p.id === personId ? {...p, ...updates} : p
            )
          }));
        },

        getPersonFormFields: (personId: number) => {
          const formInstance = personsArrayForm!;
          const personsField = (formInstance as any)['persons'];

          for (const personForm of personsField) {
            if (personForm().value()['id'] === personId) {
              return personForm;
            }
          }
          return null;
        },

        getPersonLociFields: (personId: number): Array<{ field: any; index: number }> => {
          const formInstance = personsArrayForm!;
          const personsField = (formInstance as any)['persons'];

          for (const personForm of personsField) {
            if (personForm().value()['id'] === personId) {
              const lociForms = (personForm as any)['loci'];
              const result: Array<{ field: any; index: number }> = [];

              let i = 0;
              for (const locusForm of lociForms) {
                result.push({ field: locusForm, index: i });
                i++;
              }
              return result;
            }
          }
          return [];
        },
      };
    })
  );
}
