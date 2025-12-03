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
import {TableHeader} from './components/table-header/table-header';


@Component({
  selector: 'app-dna-table',
  imports: [
    MatTableModule, MatProgressSpinnerModule, MatInputModule, MatIconModule, MatButtonModule,
    MatButtonToggleModule, MatPaginatorModule, MatChipsModule, DatePipe, MatSelectModule, MatTooltipModule,
    ScrollingModule, ExpandableRow, MatCheckboxModule, TableHeader,
  ],
  standalone: true,
  templateUrl: './dna-table.html',
  styleUrl: './dna-table.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DnaTable {
  store = inject(DnaTableStore);
  private dialog = inject(MatDialog);

  columnsToDisplay = ['select', 'name', 'role', 'loci_count', 'related_person', 'file', 'expand'];
  headerColumns = ['select', 'paginator-header'];

  isLoading = this.store.isLoading;
  dataSource = this.store.dataSource;
  selection = this.store.selection;
  selectedNames = this.selection.selected.map(e => e.name);
  selectedIds = this.selection.selected.map(e => e.personId);
  expandedRowId = this.store.expandedRowId;

  trackByPersonId(_: number, row: TableRowData): number {
    return row.personId;
  }

  getFiles(element: TableRowData): Array<{ id: number; file: string; uploaded_at: string }> {
    return element.files || [];
  }

  toggleExpanded(row: TableRowData) {
    const isExpanding = this.expandedRowId() !== row.personId;

    this.store.toggleExpandedRow(row.personId);

    if (isExpanding) {
      setTimeout(() => {
        // ✅ Check if row is still expanded (user didn't close it)
        if (this.expandedRowId() !== row.personId) {
          return; // User closed the row, don't scroll
        }

        const rowEl = document.querySelector(`[data-person-id="${row.personId}"]`);
        if (rowEl) {
          const isAtBottom = (window.innerHeight + window.scrollY) >= (document.body.scrollHeight - 10);

          if (isAtBottom) {
            return;
          }

          const headerHeight = 73;
          const targetTop = rowEl.getBoundingClientRect().top + window.scrollY - headerHeight;
          this.smoothScrollTo(targetTop, 0);
        }
      }, 600);
    }
  }

  private smoothScrollTo(targetY: number, duration: number) {
    const startY = window.scrollY;
    const distance = targetY - startY;

    if (Math.abs(distance) < 5) return;

    const startTime = performance.now();

    const animate = (currentTime: number) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const easeOut = 1 - Math.pow(1 - progress, 3);

      window.scrollTo(0, startY + distance * easeOut);

      if (progress < 1) {
        requestAnimationFrame(animate);
      }
    };

    requestAnimationFrame(animate);
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

  getFileName(url: string): string {
    const name = url.split('/').pop() || 'file';           // "Ionescu%20Eduard%20Test.pdf"
    const decoded = decodeURIComponent(name);               // "Ionescu Eduard Test.pdf"
    const nameWithoutExt = decoded.replace('.pdf', '');     // "Ionescu Eduard Test"
    return nameWithoutExt.length > 12
      ? nameWithoutExt.substring(0, 12) + '...'
      : nameWithoutExt;                                     // "Ionescu Edua..."
  }
}
