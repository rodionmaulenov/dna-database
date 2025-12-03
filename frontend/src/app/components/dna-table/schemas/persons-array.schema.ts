import {schema, Schema, applyEach} from '@angular/forms/signals';
import {PersonWithLociFormData, createPersonWithLociSchema} from './person-with-loci.schema';
import {Signal} from '@angular/core';

export interface PersonsArrayFormData {
  persons: PersonWithLociFormData[];
}

export const createPersonsArraySchema = (
  isEditMode: Signal<boolean>
): Schema<PersonsArrayFormData> => {
  return schema<PersonsArrayFormData>((path) => {
    applyEach(path.persons, createPersonWithLociSchema(isEditMode));
  });
};
