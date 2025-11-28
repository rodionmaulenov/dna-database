import {ChangeDetectionStrategy, Component, inject, input} from '@angular/core';
import {TableRowData} from '../../../models';
import {DnaTableStore} from '../../dna-table.store';
import {MatDividerModule} from '@angular/material/divider';
import {PersonForm} from '../person-form/person-form';
import {LociForm} from '../loci-form/loci-form';


@Component({
  selector: 'app-expandable-row',
  imports: [MatDividerModule, PersonForm, LociForm],
  standalone: true,
  templateUrl: './expandable-row.html',
  styleUrl: './expandable-row.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class ExpandableRow {
  store = inject(DnaTableStore);

  element = input.required<TableRowData>();

}
