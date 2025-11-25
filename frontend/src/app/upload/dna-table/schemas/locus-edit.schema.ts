import {schema, required, Schema, validate} from '@angular/forms/signals';

export interface LocusEditFormData {
  locus_name: string;
  alleles: string;
}

export const locusEditSchema: Schema<LocusEditFormData> = schema<LocusEditFormData>((path) => {
  required(path.alleles, {message: 'Alleles are required'});

  validate(path.alleles, (ctx) => {
    const value = ctx.value();

    const alleles = value.split(/[,\/]/).map((a: string) => a.trim());

    if (alleles.length !== 2 && value) {
      return {
        kind: 'invalid_allele_count',
        message: 'Must be 2 alleles'
      };
    }

    const pattern = /^\d+(\.\d+)?$/;

    for (const allele of alleles) {
      if (!pattern.test(allele) && value) {
        return {
          kind: 'invalid_allele_format',
          message: `Format 9, 12.1`
        };
      }
    }

    return null; // Valid
  });
});

