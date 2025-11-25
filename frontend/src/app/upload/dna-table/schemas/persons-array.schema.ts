import {schema, Schema, applyEach} from '@angular/forms/signals';
import {personWithLociSchema, PersonWithLociFormData} from './person-with-loci.schema';

export interface PersonsArrayFormData {
  persons: PersonWithLociFormData[];
}

export const personsArraySchema: Schema<PersonsArrayFormData> = schema<PersonsArrayFormData>((path) => {
  applyEach(path.persons, personWithLociSchema);
});
