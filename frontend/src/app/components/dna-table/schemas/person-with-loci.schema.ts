import {schema, required, Schema, applyEach, disabled} from '@angular/forms/signals';
import {createLocusEditSchema, LocusEditFormData} from './locus-edit.schema';
import {Signal} from '@angular/core';

export interface PersonWithLociFormData {
  id: number;
  name: string;
  role: 'father' | 'mother' | 'child';
  loci: LocusEditFormData[];
}

export const createPersonWithLociSchema = (
  isEditMode: Signal<boolean>
): Schema<PersonWithLociFormData> => {
  return schema<PersonWithLociFormData>((path) => {
    required(path.id, { message: 'ID is required' });
    required(path.name, { message: 'Name is required' });
    required(path.role, { message: 'Role is required' });
    disabled(path.role, () => !isEditMode());
    disabled(path.name, () => !isEditMode());
    applyEach(path.loci, createLocusEditSchema(isEditMode));
  });
};
