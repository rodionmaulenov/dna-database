import {ChangeDetectionStrategy, Component, effect, inject, input, untracked} from '@angular/core';
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

}
