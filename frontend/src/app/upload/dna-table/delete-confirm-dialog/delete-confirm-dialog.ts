import {ChangeDetectionStrategy, Component, inject} from '@angular/core';
import {MAT_DIALOG_DATA, MatDialogModule} from '@angular/material/dialog';
import {MatButtonModule} from '@angular/material/button';
import {MatIconModule} from '@angular/material/icon';

@Component({
  selector: 'delete-confirm-dialog',
  standalone: true,
  imports: [MatDialogModule, MatButtonModule, MatIconModule],
  styles: `
    ::ng-deep .mat-mdc-dialog-title {
      padding: 6px 24px 13px 24px !important;
      &::before {
        display: none !important;
      }
    }
    .flex-header{
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      height: 48px;
    }
    .report-icon{
      color: orange;
      height: 34px;
      width: 34px;
      font-size: 34px;
    }
  `,
  template: `
    <h2 mat-dialog-title>
      <div class="flex-header">
        <span>Confirm Deletion</span>
        <mat-icon class="report-icon">report</mat-icon>
      </div>
    </h2>
    <mat-dialog-content>
      <p><strong>Are you sure you want to delete this record?</strong></p>
      <p>Name: {{ data.name }}</p>
      <p>Role: {{ data.role }}</p>
      <p>Loci: {{ data.lociCount }}</p>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button [mat-dialog-close]="false">Cancel</button>
      <button mat-raised-button color="warn" [mat-dialog-close]="true">
        Delete
      </button>
    </mat-dialog-actions>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class DeleteConfirmDialog {
  data = inject(MAT_DIALOG_DATA);
}
