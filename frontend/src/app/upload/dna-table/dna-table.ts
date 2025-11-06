import {ChangeDetectionStrategy, Component, inject, OnInit} from '@angular/core';
import {MatTableModule} from '@angular/material/table';
import {MatProgressSpinnerModule} from '@angular/material/progress-spinner';
import {MatInputModule} from '@angular/material/input';
import {MatIconModule} from '@angular/material/icon';
import {MatButtonModule} from '@angular/material/button';
import {ReactiveFormsModule} from '@angular/forms';
import {MatButtonToggleModule} from '@angular/material/button-toggle';
import {MatPaginatorModule, PageEvent} from '@angular/material/paginator';
import {MatChipsModule} from '@angular/material/chips';
import {DatePipe} from '@angular/common';
import {DnaTableStore} from './dna-table.store';
import {DnaTableFormService} from './dna-table-form.service';
import {TableRowData} from './models';
import {DeleteConfirmDialog} from './delete-confirm-dialog/delete-confirm-dialog';
import {MatDialog} from '@angular/material/dialog';

@Component({
  selector: 'app-dna-table',
  imports: [
    MatTableModule,
    MatProgressSpinnerModule,
    MatInputModule,
    MatIconModule,
    MatButtonModule,
    ReactiveFormsModule,
    MatButtonToggleModule,
    MatPaginatorModule,
    MatChipsModule,
    DatePipe,
  ],
  standalone: true,
  templateUrl: './dna-table.html',
  styleUrl: './dna-table.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DnaTable implements OnInit {
  store = inject(DnaTableStore);
  formService = inject(DnaTableFormService);
  private dialog = inject(MatDialog);

  columnsToDisplay = [
    'number', 'name', 'role', 'loci_count', 'overall_confidence',
    'uploaded_at', 'related_person', 'file', 'actions'
  ];

  ngOnInit() {
    this.store.loadTableData({ page: 1 });
  }

  filterByPerson(personId: number, personRole: string) {
    this.store.filterByPerson({personId, personRole});
  }

  toggle(row: TableRowData) {
    this.store.toggleExpandedRow(row.personId);
  }

  isExpanded(row: TableRowData): boolean {
    return this.store.isRowExpanded(row.personId);
  }

  onPageChange(event: PageEvent) {
    const page = event.pageIndex + 1;
    const pageSize = event.pageSize;

    this.store.changePage({page, pageSize});
  }

  hasChanges(row: TableRowData): boolean {
    const form = this.formService.getRowForm(row);
    return form.dirty;
  }

  isUpdating(row: TableRowData): boolean {
    return this.store.isRowUpdating(row.personId);
  }

  updateRow(row: TableRowData) {
    const form = this.formService.getRowForm(row);

    let nameUpdate: string | undefined;
    const lociUpdates: Array<{ id: number; allele_1: string; allele_2: string }> = [];

    // Collect name update
    const nameControl = form.get('name');
    if (nameControl?.dirty && nameControl?.valid) {
      nameUpdate = nameControl.value;
    }

    // Collect loci updates
    const lociArray = form.get('loci') as any;
    for (let i = 0; i < row.loci.length; i++) {
      const locusControl = lociArray.at(i);
      const allelesControl = locusControl.get('alleles');

      if (allelesControl?.dirty && allelesControl?.valid) {
        const locusId = locusControl.get('id')?.value;
        const {allele_1, allele_2} = this.formService.parseAlleles(allelesControl.value);

        lociUpdates.push({id: locusId, allele_1, allele_2});
      }
    }

    // Trigger reactive update
    if (nameUpdate || lociUpdates.length > 0) {
      this.store.updateRow({row, nameUpdate, lociUpdates});
      form.markAsPristine();
    }
  }

  confirmDelete(row: TableRowData) {
    const dialogRef = this.dialog.open(DeleteConfirmDialog, {
      width: '400px',
      data: {
        name: row.name,
        role: row.role,
        lociCount: row.loci_count
      }
    });

    dialogRef.afterClosed().subscribe(confirmed => {
      if (confirmed) {
        this.store.deleteRecord(row.id);
      }
    });
  }
}
