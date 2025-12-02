import {
  ChangeDetectionStrategy, Component, DestroyRef, effect, ElementRef, inject, input, signal, viewChild
} from '@angular/core';
import {DeleteConfirmDialog} from '../../../delete-confirm-dialog/delete-confirm-dialog';
import {DnaTableStore} from '../../dna-table.store';
import {MatDialog} from '@angular/material/dialog';
import {MatIconModule} from '@angular/material/icon';
import {MatDividerModule} from '@angular/material/divider';
import {MatButtonModule} from '@angular/material/button';
import {MatTooltipModule} from '@angular/material/tooltip';
import {TableRowData} from '../../models';
import {MatChipsModule} from '@angular/material/chips';
import {UploadTopSheet} from '../../../upload-top-sheet/upload-top-sheet';
import {MatBottomSheet} from '@angular/material/bottom-sheet';


@Component({
  selector: 'app-table-header',
  standalone: true,
  imports: [
    MatIconModule, MatDividerModule, MatButtonModule, MatTooltipModule, MatChipsModule
  ],
  templateUrl: './table-header.html',
  styleUrl: './table-header.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class TableHeader {
  readonly store = inject(DnaTableStore);
  private dialog = inject(MatDialog);
  private bottomSheet = inject(MatBottomSheet);
  private destroyRef = inject(DestroyRef);

  selectionLength = input.required<number>()
  selectionHasValue = input.required<boolean>()
  selectedNames = input.required<string[]>()
  selectedIds = input.required<number[]>()

  sentinel = viewChild.required<ElementRef>('sentinel');
  isStuck = signal(false);

  dataSource = this.store.dataSource;
  expandedRowId = this.store.expandedRowId;
  filterByRole = this.store.localRoleFilter;

  constructor() {
    effect(() => {
      const el = this.sentinel();
      this.observer.observe(el.nativeElement);
    });

    this.destroyRef.onDestroy(() => this.observer.disconnect());
  }

  private observer = new IntersectionObserver(
    ([entry]) => this.isStuck.set(!entry.isIntersecting),
    { threshold: 0 }
  );

  getExpandedElement(): TableRowData | null {
    const id = this.expandedRowId();
    if (!id) return null;
    return this.dataSource().data.find(el => el.personId === id) || null;
  }

  deleteSelected(): void {
    if (!this.selectionHasValue()) return;

    const dialogRef = this.dialog.open(DeleteConfirmDialog, {
      data: {
        type: 'persons',
        count: this.selectionLength(),
        names: this.selectedNames()
      }
    });

    dialogRef.afterClosed().subscribe(confirmed => {
      if (confirmed) {
        const selectedPersonIds = this.selectedIds;
        this.store.deletePersons(selectedPersonIds);
      }
    });
  }

  openUploadSheet(): void {
    const sheetRef = this.bottomSheet.open(UploadTopSheet, {
      hasBackdrop: true,
      panelClass: 'components-top-sheet'
    });

    sheetRef.afterDismissed().subscribe((result) => {
      if (result?.action === 'view_match') {
        this.store.filterByPerson(
          result.match.person_id,
          result.match.role,
          result.match.name
        );
      }

      if (result?.action === 'view_person') {
        this.store.filterByPerson(
          result.personId,
          result.role,
          result.personName
        );
      }
    });
  }

  setRoleFilter(value: 'parent' | 'child' | null) {
    this.store.setRoleFilter(value);
  }
}
