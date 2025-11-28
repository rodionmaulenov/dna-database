import {ChangeDetectionStrategy, Component, inject} from '@angular/core';
import {MatTableModule} from '@angular/material/table';
import {MatProgressSpinnerModule} from '@angular/material/progress-spinner';
import {MatInputModule} from '@angular/material/input';
import {MatIconModule} from '@angular/material/icon';
import {MatButtonModule} from '@angular/material/button';
import {MatButtonToggleModule} from '@angular/material/button-toggle';
import {MatPaginatorModule} from '@angular/material/paginator';
import {MatChipsModule} from '@angular/material/chips';
import {DatePipe} from '@angular/common';
import {DnaTableStore} from './dna-table.store';
import {TableRowData} from './models';
import {DeleteConfirmDialog} from '../delete-confirm-dialog/delete-confirm-dialog';
import {MatDialog} from '@angular/material/dialog';
import {MatSelectModule} from '@angular/material/select';
import {MatTooltipModule} from '@angular/material/tooltip';
import {ScrollingModule} from '@angular/cdk/scrolling';
import {UploadedFile} from '../models';
import {ExpandableRow} from './components/expandable-row/expandable-row';
import {MatCheckboxModule} from '@angular/material/checkbox';


@Component({
  selector: 'app-dna-table',
  imports: [
    MatTableModule, MatProgressSpinnerModule, MatInputModule, MatIconModule, MatButtonModule,
    MatButtonToggleModule, MatPaginatorModule, MatChipsModule, DatePipe, MatSelectModule, MatTooltipModule,
    ScrollingModule, ExpandableRow, MatCheckboxModule,
  ],
  standalone: true,
  templateUrl: './dna-table.html',
  styleUrl: './dna-table.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DnaTable {
  store = inject(DnaTableStore);
  private dialog = inject(MatDialog);

  columnsToDisplay = [
    'select', 'number', 'expand', 'name', 'role', 'loci_count', 'related_person', 'file'
  ];

  isLoading = this.store.isLoading;
  dataSource = this.store.dataSource;
  selection = this.store.selection;
  total = this.store.total;
  pageIndex = this.store.pageIndex;
  pageSize = this.store.pageSize;
  expandedRowId = this.store.expandedRowId;

  trackByPersonId(_: number, row: TableRowData): number {
    return row.personId;
  }

  loadPage(pageIndex: number) {
    this.store.loadPage(pageIndex);
  }

  getPersonIds(persons: Array<{ id: number; name: string; role: string }>): number[] {
    return persons.map(p => p.id);
  }

  getExpandedElement(): TableRowData | null {
    const id = this.expandedRowId();
    if (!id) return null;
    return this.dataSource().data.find(el => el.personId === id) || null;
  }

  getFiles(element: TableRowData): Array<{ id: number; file: string; uploaded_at: string }> {
    return element.files || [];
  }

  toggleExpanded(row: TableRowData) {
    this.store.toggleExpandedRow(row.personId);
  }

  deleteSelected(): void {
    if (!this.selection.hasValue()) return;

    const dialogRef = this.dialog.open(DeleteConfirmDialog, {
      data: {
        type: 'persons',
        count: this.selection.selected.length,
        names: this.selection.selected.map(r => r.name)
      }
    });

    dialogRef.afterClosed().subscribe(confirmed => {
      if (confirmed) {
        const selectedPersonIds = this.selection.selected.map(r => r.personId);
        this.store.deletePersons(selectedPersonIds);
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
        this.store.deleteFile({personId: element.personId, fileId: file.id});
      }
    });
  }
}
