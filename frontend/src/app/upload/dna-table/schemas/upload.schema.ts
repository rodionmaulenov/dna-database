import { schema, required, validate, customError } from '@angular/forms/signals';

export interface UploadFormData {
  files: File[];
}

export const uploadSchema = schema<UploadFormData>((path) => {
  required(path.files, {
    message: 'Please select at least one DNA report file'
  });

  // Validate array of files
  validate(path.files, (ctx) => {
    const files = ctx.value();

    if (!files || files.length === 0) {
      return customError({
        kind: 'no_files',
        message: 'Please select at least one file'
      });
    }

    // Validate each file
    for (const file of files) {
      if (!file.name.endsWith('.pdf')) {
        return customError({
          kind: 'invalid_file_type',
          message: `Only PDF files allowed. "${file.name}" is not a PDF.`
        });
      }

      // Check file size (max 10MB each)
      const maxSize = 10 * 1024 * 1024;
      if (file.size > maxSize) {
        return customError({
          kind: 'file_too_large',
          message: `"${file.name}" is too large. Max 10MB per file.`
        });
      }
    }

    return null;
  });
});
