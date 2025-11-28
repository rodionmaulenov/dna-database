import {patchState, signalStoreFeature, withMethods, withState} from '@ngrx/signals';
import {FieldTree, form} from '@angular/forms/signals';
import {signal} from '@angular/core';
import {PersonsArrayFormData, personsArraySchema} from '../schemas/persons-array.schema';


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
            persons: data.persons.map(p =>
              p.id === personId ? {...p, loci} : p
            )
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

        addLocusToPersonById: (personId: number, locusName: string): void => {

          personsSignal.update(data => ({
            persons: data.persons.map(p =>
              p.id === personId
                ? {...p, loci: [...p.loci, { id: 0, locus_name: locusName, alleles: '' }]}
                : p
            )
          }));
        },

        removeLocusFromPersonById: (personId: number, locusIndex: number): void => {

          personsSignal.update(data => ({
            persons: data.persons.map(p =>
              p.id === personId
                ? {...p, loci: p.loci.filter((_, i) => i !== locusIndex)}
                : p
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


        getLocusAtIndex: (personId: number, index: number): { id: number; locus_name: string; alleles: string } | null => {
          const form = personsArrayForm!();
          const currentValue = form.value();
          const person = currentValue.persons.find(p => p.id === personId);
          return person?.loci[index] || null;
        },

        getPersonLociFieldNames: (personId: number): string[] => {
          const formInstance = personsArrayForm!();
          const currentValue = formInstance.value();

          const person = currentValue.persons.find(p => p.id === personId);
          if (!person) return [];

          return person.loci.map(l => l.locus_name).filter(Boolean);
        },

      };
    })
  );
}
