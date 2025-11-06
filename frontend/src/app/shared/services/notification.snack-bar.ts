import {Component, inject} from '@angular/core';
import {MAT_SNACK_BAR_DATA} from '@angular/material/snack-bar';
import {MatIconModule} from '@angular/material/icon';

@Component({
  selector: 'notification-snackbar',
  standalone: true,
  imports: [MatIconModule],
  template: `
    <div style="display: flex; align-items: center; gap: 8px;">
      <mat-icon>{{ data.icon }}</mat-icon>
      <span>{{ data.message }}</span>
    </div>
  `
})
export class NotificationSnackbar {
  data: { message: string; icon: string } = inject(MAT_SNACK_BAR_DATA);
}
