import {ChangeDetectionStrategy, Component, inject} from '@angular/core';
import {UploadStore} from '../upload.store';
import {MatBottomSheetRef} from '@angular/material/bottom-sheet';
import {MatButtonModule} from '@angular/material/button';
import {MatIconModule} from '@angular/material/icon';
import {MatDividerModule} from '@angular/material/divider';
import {MatListModule} from '@angular/material/list';
import {MatProgressSpinnerModule} from '@angular/material/progress-spinner';
import {MatFormFieldModule} from '@angular/material/form-field';
import {MatSelectModule} from '@angular/material/select';
import {MatChip} from '@angular/material/chips';
import {MatchResult} from '../models';
import {MatInputModule} from '@angular/material/input';
import {FormsModule} from '@angular/forms';


@Component({
  selector: 'app-upload-top-sheet',
  imports: [
    MatButtonModule, MatListModule, MatDividerModule, MatProgressSpinnerModule, MatIconModule, MatFormFieldModule,
    MatSelectModule, MatChip, MatInputModule, FormsModule
  ],
  standalone: true,
  templateUrl: './upload-top-sheet.html',
  styleUrl: './upload-top-sheet.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class UploadTopSheet {
  store = inject(UploadStore);
  private bottomSheetRef = inject(MatBottomSheetRef<UploadTopSheet>);

  onFileSelect(event: any): void {
    const files: FileList = event.target.files;
    if (!files.length) return;

    const filesArray = Array.from(files);
    this.store.addFiles(filesArray);
    event.target.value = '';
  }

  viewMatch(match: MatchResult): void {
    this.bottomSheetRef.dismiss({
      action: 'view_match',
      match: match
    });
  }

  upload(): void {
    this.store.uploadAll();
  }

  removeFile(index: number): void {
    this.store.removeFile(index);
  }

  clearAll(): void {
    this.store.clearAll();
  }

  close(): void {
    this.bottomSheetRef.dismiss();
  }

}
