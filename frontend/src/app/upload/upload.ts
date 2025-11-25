import {ChangeDetectionStrategy, Component, inject} from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { MatChipsModule } from '@angular/material/chips';
import { MatBottomSheet } from '@angular/material/bottom-sheet';
import { DnaTable } from './dna-table/dna-table';
import { UploadTopSheet } from './upload-top-sheet/upload-top-sheet';
import { DnaTableStore } from './dna-table/dna-table.store';


@Component({
  selector: 'app-upload',
  standalone: true,
  imports: [
    MatButtonModule, MatIconModule, MatButtonToggleModule, MatChipsModule, DnaTable
  ],
  templateUrl: './upload.html',
  styleUrl: './upload.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Upload {
  tableStore = inject(DnaTableStore);
  private bottomSheet = inject(MatBottomSheet);

  openUploadSheet(): void {
    const sheetRef = this.bottomSheet.open(UploadTopSheet, {
      hasBackdrop: true,
      panelClass: 'upload-top-sheet'
    });

    sheetRef.afterDismissed().subscribe((result) => {
      if (result?.action === 'view_match') {
        this.tableStore.filterByPerson(
          result.match.person_id,
          result.match.role,
          result.match.name
        );
      }

      if (result?.action === 'view_person') {
        this.tableStore.filterByPerson(
          result.personId,
          result.role,
          result.personName
        );
      }
    });
  }

  setRoleFilter(value: 'parent' | 'child' | null) {
    this.tableStore.setRoleFilter(value);
  }

  clearPersonFilter() {
    this.tableStore.clearFilter();
  }
}
