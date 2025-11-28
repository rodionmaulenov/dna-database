import { schema, required, Schema, applyEach } from '@angular/forms/signals';
import { locusEditSchema, LocusEditFormData } from './locus-edit.schema';

export interface PersonWithLociFormData {
  id: number;
  name: string;
  role: 'father' | 'mother' | 'child';
  loci: LocusEditFormData[];
}

export const personWithLociSchema: Schema<PersonWithLociFormData> = schema<PersonWithLociFormData>((path) => {
  required(path.id, { message: 'ID is required' });
  required(path.name, { message: 'Name is required' });
  required(path.role, { message: 'Role is required' });
  applyEach(path.loci, locusEditSchema);
});
