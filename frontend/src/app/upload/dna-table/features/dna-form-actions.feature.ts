import {signalStoreFeature, withMethods} from '@ngrx/signals';

export function withDnaFormActions(
  addLocusToPersonById: (personId: number, locusName: string) => void,
  removeLocusFromPersonById: (personId: number, index: number) => void,
  setCurrentEditingPerson: (personId: number | null) => void,
) {

  return signalStoreFeature(
    withMethods((_) => {
      return {

        addLocus: (personId: number, locusName: string): void => {
          addLocusToPersonById(personId, locusName);
        },

        removeLocus: (personId: number, index: number): void => {
          removeLocusFromPersonById(personId, index);
        },


        saveChanges: (): void => {
          setCurrentEditingPerson(null);
        },

      };
    })
  );
}
