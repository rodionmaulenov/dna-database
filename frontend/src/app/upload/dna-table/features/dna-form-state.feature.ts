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

        // ✅ LOAD ALL PERSONS AT ONCE (when data arrives from backend)
        loadAllPersons: (persons: Array<{
          id: number;
          name: string;
          role: 'father' | 'mother' | 'child';
        }>): void => {
          const form = personsArrayForm!();
          form.value.set({
            persons: persons.map(p => ({
              id: p.id,
              name: p.name,
              role: p.role,
              loci: []
            }))
          });
        },

        // ✅ LOAD PERSONS LOCUS AT ONCE (when toggle expand button)
        loadPersonLoci: (personId: number, loci: Array<{
          id: number;  // ✅ Add ID
          locus_name: string;
          alleles: string
        }>): void => {
          const form = personsArrayForm!();
          form.value.update(data => ({
            persons: data.persons.map(p =>
              p.id === personId
                ? {...p, loci}
                : p
            )
          }));
        },

        // ✅ UPDATE SPECIFIC PERSON BY ID
        updatePersonById: (personId: number, updates: {
          name?: string;
          role?: 'father' | 'mother' | 'child';
        }): void => {
          const form = personsArrayForm!();
          form.value.update(data => ({
            persons: data.persons.map(p =>
              p.id === personId ? {...p, ...updates} : p
            )
          }));
        },

        // ✅ ADD LOCUS TO PERSON BY ID
        addLocusToPersonById: (personId: number, locusName: string): void => {
          const form = personsArrayForm!();
          form.value.update(data => ({
            persons: data.persons.map(p =>
              p.id === personId
                ? {
                  ...p,
                  loci: [...p.loci, {
                    id: 0,  // ✅ New locus has ID 0
                    locus_name: locusName,
                    alleles: ''
                  }]
                }
                : p
            )
          }));
        },

        // ✅ REMOVE LOCUS FROM PERSON BY ID
        removeLocusFromPersonById: (personId: number, locusIndex: number): void => {
          const form = personsArrayForm!();
          form.value.update(data => ({
            persons: data.persons.map(p =>
              p.id === personId
                ? {...p, loci: p.loci.filter((_, i) => i !== locusIndex)}
                : p
            )
          }));
        },

        // ✅ Get loci names from form for specific person
        getPersonLociFromForm: (personId: number): string[] => {
          const formInstance = personsArrayForm!();
          const currentValue = formInstance.value();

          const person = currentValue.persons.find(p => p.id === personId);
          if (!person) return [];

          return person.loci.map(l => l.locus_name).filter(Boolean);
        },

        resetForm: (): void => {
          const form = personsArrayForm!();
          form.reset();
          form.value.set({persons: []});
        },

      };
    })
  );
}
