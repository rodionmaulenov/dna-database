import {ChangeDetectionStrategy, Component, inject} from '@angular/core';
import {MatButtonModule} from '@angular/material/button';
import {MatIconModule} from '@angular/material/icon';
import {DnaTable} from './dna-table/dna-table';
import {UploadTopSheet} from './upload-top-sheet/upload-top-sheet';
import {MatBottomSheet} from '@angular/material/bottom-sheet';
import {DnaTableStore} from './dna-table/dna-table.store';
import {MatchResult} from './models';
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
      disableClose: false,
      hasBackdrop: true,
      panelClass: 'upload-top-sheet'
    })

    sheetRef.afterDismissed().subscribe((result) => {
      if (result?.action === 'view_match') {
        this.navigateToMatch(result.match);
      }
    });
  }

  navigateToMatch(match: MatchResult): void {
    this.tableStore.filterByPerson({
      personId: match.person_id,
      personRole: match.role
    });
  }

  setFilter(filter: 'parent' | 'child') {
    this.tableStore.setRoleFilter(filter);
  }

  clearFilter() {
    this.tableStore.clearPersonFilter();
  }
}
