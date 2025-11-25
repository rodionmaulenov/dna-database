import {ChangeDetectionStrategy, Component, effect, inject} from '@angular/core';
import {MatTableDataSource, MatTableModule} from '@angular/material/table';
import {MatProgressSpinnerModule} from '@angular/material/progress-spinner';
import {MatInputModule} from '@angular/material/input';
import {MatIconModule} from '@angular/material/icon';
import {MatButtonModule} from '@angular/material/button';
import {FormsModule, ReactiveFormsModule} from '@angular/forms';
import {MatButtonToggleModule} from '@angular/material/button-toggle';
import {MatPaginatorModule} from '@angular/material/paginator';
import {MatChipsModule} from '@angular/material/chips';
import {DatePipe} from '@angular/common';
import {DnaTableStore} from './dna-table.store';
import {TableRowData} from './models';
import {DeleteConfirmDialog} from './delete-confirm-dialog/delete-confirm-dialog';
import {MatDialog} from '@angular/material/dialog';
import {MatSelectModule} from '@angular/material/select';
import {MatTooltipModule} from '@angular/material/tooltip';
import {ScrollingModule} from '@angular/cdk/scrolling';
import {Field} from '@angular/forms/signals';
import {ImmediateErrorStateMatcher} from '../../shared/utils/error-state-matchers';
import {UploadedFile} from '../models';


@Component({
  selector: 'app-dna-table',
  imports: [
    MatTableModule, MatProgressSpinnerModule, MatInputModule, MatIconModule, MatButtonModule, ReactiveFormsModule,
    MatButtonToggleModule, MatPaginatorModule, MatChipsModule, DatePipe, MatSelectModule, MatTooltipModule,
    FormsModule, ScrollingModule, Field
  ],
  standalone: true,
  templateUrl: './dna-table.html',
  styleUrl: './dna-table.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DnaTable {
  store = inject(DnaTableStore);
  private dialog = inject(MatDialog);

  immediateErrorMatcher = new ImmediateErrorStateMatcher();
  dataSource = new MatTableDataSource<TableRowData>([]);
  selectedLocusName: string = '';

  columnsToDisplay = [
    'number', 'name', 'role', 'loci_count', 'related_person', 'file', 'actions'
  ];

  isLoading =  this.store.isLoading;
  total = this.store.total;
  pageIndex = this.store.pageIndex;
  pageSize = this.store.pageSize;

  constructor() {
    effect(() => {
      this.dataSource.data = this.store.filteredTableData();

      this.store.loadAllPersons(
        this.store.filteredTableData().map(row => ({
          id: row.personId,
          name: row.name,
          role: row.role
        }))
      );
    });
  }

  trackByPersonId(_: number, row: TableRowData): number {
    return row.personId;
  }

  loadPage(pageIndex: number) {
    this.store.loadPage(pageIndex);
  }

  isExpanded(row: TableRowData): boolean {
    return this.store.isRowExpanded(row.personId);
  }

  getPersonIds(persons: Array<{ id: number; name: string; role: string }>): number[] {
    return persons.map(p => p.id);
  }

  onLocusSelected(row: TableRowData, locusName: string) {
    if (!locusName) return;
    this.store.addLocusToPersonById(row.personId, locusName);
    this.store.cancelAddingLocus();
    this.selectedLocusName = '';
  }

  getAvailableLociForRow(row: TableRowData): string[] {
    const formLociNames = this.store.getPersonLociFromForm(row.personId);
    return this.store.getAvailableLoci(formLociNames);
  }

  removeLocus(row: TableRowData, index: number) {
    const locus = this.store.getLocusAtIndex(row.personId, index);  // ✅ Get from form
    if (locus && locus.id > 0) {
      this.store.trackDeletedLocus(row.personId, locus.id);
    }
    this.store.removeLocusFromPersonById(row.personId, index);
  }

  isAddingLocus(row: TableRowData): boolean {
    return this.store.isAddingLocus(row.personId);
  }

  startAddingLocus(row: TableRowData) {
    const formLociNames = this.store.getPersonLociFromForm(row.personId);
    const availableLoci = this.store.getAvailableLoci(formLociNames);
    if (availableLoci.length === 0) return;
    this.store.startAddingLocus(row.personId);
  }

  cancelAddLocus() {
    this.store.cancelAddingLocus();
  }

  getFiles(element: TableRowData): Array<{ id: number; file: string; uploaded_at: string }> {
    return element.files || [];
  }


  confirmDelete(row: TableRowData) {
    const dialogRef = this.dialog.open(DeleteConfirmDialog, {
      width: '400px',
      data: {
        type: 'person',
        name: row.name,
        role: row.role,
        lociCount: row.loci_count
      }
    });

    dialogRef.afterClosed().subscribe(confirmed => {
      if (confirmed) {
        this.store.deletePerson(row.personId);
      }
    });
  }

  confirmDeleteFile(element: TableRowData, file: UploadedFile, index: number): void {
    const dialogRef = this.dialog.open(DeleteConfirmDialog, {
      data: {
        type: 'file',
        fileIndex: index + 1
      }
    });

    dialogRef.afterClosed().subscribe(confirmed => {
      if (confirmed) {
        this.store.deleteFile({ personId: element.personId, fileId: file.id });
      }
    });
  }
}
