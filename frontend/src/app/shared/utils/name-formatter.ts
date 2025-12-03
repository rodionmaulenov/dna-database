export function formatPersonName(name: string, maxParts: number = 2): string {
  if (!name) return '';

  // Remove special characters (keep letters, spaces, hyphens)
  const cleaned = name
    .replace(/[.,;:!?'"()[\]{}0-9]/g, '')  // Remove punctuation & numbers
    .replace(/\s+/g, ' ')                   // Normalize spaces
    .trim();

  // Split by space (hyphenated parts stay together)
  const parts = cleaned.split(' ').filter(p => p.length > 0);

  // Return max parts
  return parts.slice(0, maxParts).join(' ');
}
