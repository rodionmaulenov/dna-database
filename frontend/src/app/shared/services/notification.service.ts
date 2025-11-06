import {inject, Injectable} from '@angular/core';
import {MatSnackBar} from '@angular/material/snack-bar';
import {NotificationSnackbar} from './notification.snack-bar';

@Injectable({
  providedIn: 'root'
})
export class NotificationService {
  private snackBar = inject(MatSnackBar);

  success(message: string, duration: number = 3000): void {
    this.snackBar.openFromComponent(NotificationSnackbar, {
      duration,
      horizontalPosition: 'end',
      verticalPosition: 'top',
      panelClass: ['success-snackbar'],
      data: {message, icon: 'check_circle'}
    });
  }

  error(message: string, duration: number = 5000): void {
    this.snackBar.openFromComponent(NotificationSnackbar, {
      duration,
      horizontalPosition: 'end',
      verticalPosition: 'top',
      panelClass: ['error-snackbar'],
      data: {message, icon: 'error'}
    });
  }

  warning(message: string, duration: number = 4000): void {
    this.snackBar.openFromComponent(NotificationSnackbar, {
      duration,
      horizontalPosition: 'end',
      verticalPosition: 'top',
      panelClass: ['warning-snackbar'],
      data: {message, icon: 'warning'}
    });
  }

  info(message: string, duration: number = 3000): void {
    this.snackBar.openFromComponent(NotificationSnackbar, {
      duration,
      horizontalPosition: 'end',
      verticalPosition: 'top',
      panelClass: ['info-snackbar'],
      data: {message, icon: 'info'}
    });
  }
}
