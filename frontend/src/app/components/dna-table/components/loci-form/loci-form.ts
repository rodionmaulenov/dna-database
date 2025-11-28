import {ChangeDetectionStrategy, Component, effect, inject, input, signal, untracked} from '@angular/core';
import {DnaTableStore} from '../../dna-table.store';
import {TableRowData} from '../../../models';
import {ImmediateErrorStateMatcher} from '../../../../shared/utils/error-state-matchers';
import {MatFormFieldModule} from '@angular/material/form-field';
import {MatSelectModule} from '@angular/material/select';
import {Field} from '@angular/forms/signals';
import {MatInputModule} from '@angular/material/input';
import {MatButtonModule} from '@angular/material/button';
import {MatTooltipModule} from '@angular/material/tooltip';
import {MatIconModule} from '@angular/material/icon';
import {FormsModule} from '@angular/forms';

@Component({
  selector: 'app-loci-form',
  imports: [
    MatFormFieldModule, MatSelectModule, Field, MatInputModule,
    MatButtonModule, MatTooltipModule, MatIconModule, FormsModule
  ],
  standalone: true,
  templateUrl: './loci-form.html',
  styleUrl: './loci-form.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class LociForm {
  store = inject(DnaTableStore);

  element = input.required<TableRowData>();
  selectLocusName = signal<string>('');

  immediateErrorMatcher = new ImmediateErrorStateMatcher();

  constructor() {
    // ✅ Load loci when component initializes (row expanded)
    effect(() => {
      const el = this.element();

      untracked(() => {
        if (el.loci && el.loci.length > 0) {
          this.store.loadPersonLoci(el.personId, el.loci.map(l => ({
            id: l.id,
            locus_name: l.locus_name,
            alleles: [l.allele_1, l.allele_2].filter(Boolean).join(', ')
          })));
        }
      });
    });
  }

  getAvailableLociForRow(): string[] {
    const formLociNames = this.store.getPersonLociFieldNames(this.element().personId);
    return this.store.getAvailableLoci(formLociNames);
  }

  onLocusSelected(locusName: string) {
    if (!locusName) return;
    this.store.addLocusToPersonById(this.element().personId, locusName);
    this.store.cancelAddingLocus();
    this.selectLocusName.set('');
  }

  isAddingLocus(): boolean {
    return this.store.isAddingLocus(this.element().personId);
  }

  startAddingLocus() {
    const availableLoci = this.getAvailableLociForRow();
    if (availableLoci.length === 0) return;
    this.store.startAddingLocus(this.element().personId);
  }

  removeLocus(index: number) {
    const locus = this.store.getLocusAtIndex(this.element().personId, index);
    if (locus && locus.id > 0) {
      this.store.trackDeletedLocus(this.element().personId, locus.id);
    }
    this.store.removeLocusFromPersonById(this.element().personId, index);
  }

  cancelAddLocus() {
    this.store.cancelAddingLocus();
  }

}
