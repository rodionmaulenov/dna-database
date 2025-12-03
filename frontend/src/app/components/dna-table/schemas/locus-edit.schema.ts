import {schema, required, Schema, validate, disabled} from '@angular/forms/signals';
import {Signal} from '@angular/core';

export interface LocusEditFormData {
  id: number;
  locus_name: string;
  alleles: string;
}

export const createLocusEditSchema = (
  isEditMode: Signal<boolean>
): Schema<LocusEditFormData> => {
  return schema<LocusEditFormData>((path) => {

    // locus_name never editable (it's the identifier)
    disabled(path.locus_name, () => true);

    // alleles editable only in edit mode
    disabled(path.alleles, () => !isEditMode());

    required(path.alleles, { message: 'Alleles are required' });

    validate(path.alleles, (ctx) => {
      const value = ctx.value();
      if (!value) return null;

      const alleles = value.split(/[,\/]/).map((a: string) => a.trim());

      if (alleles.length !== 2) {
        return {
          kind: 'invalid_allele_count',
          message: 'Must be 2 alleles'
        };
      }

      const pattern = /^\d+(\.\d+)?$/;
      for (const allele of alleles) {
        if (!pattern.test(allele)) {
          return {
            kind: 'invalid_allele_format',
            message: 'Format 9, 12.1'
          };
        }
      }

      return null;
    });
  });
};

