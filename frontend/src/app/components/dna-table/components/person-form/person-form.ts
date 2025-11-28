import {ChangeDetectionStrategy, Component, effect, inject, input, untracked} from '@angular/core';
import {MatFormFieldModule} from '@angular/material/form-field';
import {MatSelectModule} from '@angular/material/select';
import {MatInputModule} from '@angular/material/input';
import {MatIconModule} from '@angular/material/icon';
import {Field} from '@angular/forms/signals';
import {DnaTableStore} from '../../dna-table.store';
import {TableRowData} from '../../../models';
import {ImmediateErrorStateMatcher} from '../../../../shared/utils/error-state-matchers';


@Component({
  selector: 'app-person-form',
  standalone: true,
  imports: [MatFormFieldModule, MatSelectModule, MatInputModule, MatIconModule, Field],
  templateUrl: './person-form.html',
  styleUrl: './person-form.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class PersonForm {
  store = inject(DnaTableStore);

  element = input.required<TableRowData>();

  immediateErrorMatcher = new ImmediateErrorStateMatcher();

  constructor() {
    effect(() => {
      const el = this.element();

      untracked(() => {
        this.store.loadPerson({
          id: el.personId,
          name: el.name,
          role: el.role
        });
      });
    });
  }

  getPersonFormFields() {
    return this.store.getPersonFormFields(this.element().personId);
  }
}
