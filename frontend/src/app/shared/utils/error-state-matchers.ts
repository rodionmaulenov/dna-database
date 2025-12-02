import { ErrorStateMatcher } from '@angular/material/core';

export class ImmediateErrorStateMatcher implements ErrorStateMatcher {
  isErrorState(control: any): boolean {
    return control && control.invalid && control.dirty;
  }
}
