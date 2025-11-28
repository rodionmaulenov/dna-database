import { schema, required } from '@angular/forms/signals';

export interface UploadFormData {
  files: File[];
}

export const uploadSchema = schema<UploadFormData>((path) => {
  required(path.files, {
    message: 'Please select at least one DNA report file'
  });
});
