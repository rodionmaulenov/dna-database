import {Injectable, inject} from '@angular/core';
import {FormBuilder, FormGroup, FormArray, Validators} from '@angular/forms';
import {TableRowData} from './models';

@Injectable({
  providedIn: 'root'
})
export class DnaTableFormService {
  private fb = inject(FormBuilder);
  private rowForms = new Map<number, FormGroup>();

  getRowForm(row: TableRowData): FormGroup {
    if (!this.rowForms.has(row.personId)) {
      this.rowForms.set(row.personId, this.createRowForm(row));
    }
    return this.rowForms.get(row.personId)!;
  }

  private createRowForm(row: TableRowData): FormGroup {
    return this.fb.group({
      name: [row.name, [Validators.required, Validators.minLength(2)]],
      role: [row.role, [Validators.required]],
      loci: this.fb.array(
        row.loci.map(locus => this.fb.group({
          id: [locus.id],
          alleles: [
            this.formatAlleles(locus.allele_1, locus.allele_2),
            [Validators.required]
          ]
        }))
      )
    });
  }

  getLociArray(row: TableRowData): FormArray {
    const form = this.getRowForm(row);
    return form.get('loci') as FormArray;
  }

  addLocus(row: TableRowData, locusName: string): void {
    const lociArray = this.getLociArray(row);

    lociArray.push(this.fb.group({
      id: [null],
      locus_name: [locusName],
      alleles: ['', [Validators.required]]
    }));

    const currentLociCount = row.loci.length;
    const newLocusGroup = lociArray.at(currentLociCount) as FormGroup;

    Object.keys(newLocusGroup.controls).forEach(key => {
      console.log(newLocusGroup.controls);
      newLocusGroup.get(key)?.markAsTouched();
      newLocusGroup.get(key)?.markAsDirty();
    });
  }

  removeLocus(row: TableRowData, index: number): void {
    const lociArray = this.getLociArray(row);

    // Remove from form
    lociArray.removeAt(index);

    // Mark as dirty
    lociArray.markAsDirty();

    const form = this.getRowForm(row);
    form.markAsDirty();
  }

  getLocusFormGroup(row: TableRowData, index: number): FormGroup {
    const form = this.getRowForm(row);
    const lociArray = form.get('loci') as FormArray;
    return lociArray.at(index) as FormGroup;
  }

  formatAlleles(allele1: string, allele2: string): string {
    return `${allele1}, ${allele2}`;
  }

  parseAlleles(value: string): { allele_1: string; allele_2: string } {
    const parts = value.split(',').map(s => s.trim());
    return {
      allele_1: parts[0] || '',
      allele_2: parts[1] || ''
    };
  }

}
