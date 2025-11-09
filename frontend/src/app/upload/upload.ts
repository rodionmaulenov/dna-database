import {ChangeDetectionStrategy, Component, inject} from '@angular/core';
import {MatButtonModule} from '@angular/material/button';
import {MatIconModule} from '@angular/material/icon';
import {DnaTable} from './dna-table/dna-table';
import {UploadTopSheet} from './upload-top-sheet/upload-top-sheet';
import {MatBottomSheet} from '@angular/material/bottom-sheet';
import {DnaTableStore} from './dna-table/dna-table.store';
import {MatButtonToggleModule} from '@angular/material/button-toggle';
import {MatChipsModule} from '@angular/material/chips';

@Component({
  selector: 'app-upload',
  standalone: true,
  imports: [
    MatButtonModule,
    MatIconModule,
    DnaTable,
    MatButtonToggleModule,
    MatChipsModule
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
    })

    sheetRef.afterDismissed().subscribe((result) => {
      if (result?.action === 'view_match') {
        const match = result.match;
        // ✅ BACKEND: Search for matches (backend call)
        this.tableStore.searchMatches({
          personId: match.person_id,
          personRole: match.role
        });
      }
      // ✅ ADD THIS - User clicked on error link
      if (result?.action === 'view_person') {
        this.tableStore.searchMatches({
          personId: result.personId,
          personRole: result.role
        });
      }
    });
  }

  setFilter(filter: 'parent' | 'child') {
    this.tableStore.setRoleFilter(filter);
  }

  // ✅ Clear local filter only
  clearLocalFilter() {
    this.tableStore.clearLocalFilter();
  }

  // ✅ Clear backend search
  clearSearch() {
    this.tableStore.clearSearch();
  }

  // ✅ Clear multiple person filter
  clearMultipleFilter() {
    this.tableStore.clearMultipleFilter();
  }
}
