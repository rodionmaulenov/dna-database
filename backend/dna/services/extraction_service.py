"""
DNA Extraction Service
======================
Extracts DNA data from PDF files using AWS Textract + Claude AI validation.

Main functions:
- extract_from_pdf(): Extract DNA data from PDF file
- extract_and_save(): Extract and save to database (full pipeline)
"""
import logging
import json
import os
from typing import Dict, Any, Optional

import anthropic

from dna.services.textract_service import TextractService
from dna.pdf_processor import process_dna_report_pdf
from dna.utils.file_helpers import save_temp_file
from dna.services.dna_persistence_service import save_dna_extraction_to_database

logger = logging.getLogger(__name__)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def normalize_alleles(value: str) -> list[str]:
    """Split '15.15' or '15,16' into ['15', '15'] or ['15', '16']"""
    value = value.strip()
    if not value or value == '-':
        return []

    if ',' in value:
        return [a.strip() for a in value.split(',') if a.strip()]

    if '.' in value:
        parts = value.split('.')
        if len(parts) == 2 and len(parts[1]) > 1:
            return [parts[0], parts[1]]
        else:
            return [value]

    return [value]


def normalize_role(role_text: str) -> str:
    """Normalize role to standard value"""
    role_lower = role_text.lower().strip()

    # English
    if 'father' in role_lower:
        return 'father'
    elif 'mother' in role_lower:
        return 'mother'
    elif 'child' in role_lower:
        return 'child'

    # Ukrainian
    elif 'батько' in role_lower or 'вірогідний' in role_lower:
        return 'father'
    elif 'мати' in role_lower or 'матi' in role_lower:
        return 'mother'
    elif 'дитина' in role_lower:
        return 'child'

    return role_lower


def detect_role_from_amelogenin(alleles: list[str]) -> str:
    """Detect if person is male or female from Amelogenin"""
    if not alleles:
        return 'unknown'

    value = ''.join(alleles).upper().replace(' ', '').replace(',', '')

    if 'XY' in value or value == 'XY':
        return 'father'
    elif 'XX' in value or value == 'XX':
        return 'mother'

    return 'unknown'


def is_empty_column(table: list[list[str]], col: int, data_start_row: int) -> bool:
    """Check if entire column has no data (all empty or '-')"""
    for row in table[data_start_row:]:
        if col < len(row):
            value = row[col].strip()
            if value and value != '-':
                return False
    return True


def find_header_and_role_rows(table: list[list[str]]) -> tuple[int, int, int]:
    """
    Find which rows contain headers, roles, and where data starts.
    Returns: (header_row, role_row, data_start_row)
    """
    role_keywords = ['father', 'mother', 'child', 'батько', 'мати', 'дитина', 'alleged', 'вірогідний']

    if not table or len(table) < 2:
        return (0, -1, 1)

    row0_first = table[0][0].lower().strip() if table[0] else ''
    locus_keywords = ['locus', 'локус', 'marker', 'маркер', 'фрагменти', 'фрагменти днк']
    row0_is_locus = any(kw in row0_first for kw in locus_keywords)

    def has_roles(row):
        if not row:
            return False
        for cell in row[1:]:
            if cell and any(kw in cell.lower() for kw in role_keywords):
                return True
        return False

    row0_has_roles = has_roles(table[0])
    row1_has_roles = has_roles(table[1]) if len(table) > 1 else False

    if not row0_is_locus and row1_has_roles:
        return (-1, 1, 2)

    if row0_is_locus and row0_has_roles and not row1_has_roles:
        return (0, 0, 1)

    if row0_is_locus and row1_has_roles:
        return (0, 1, 2)

    if row0_is_locus and not row1_has_roles:
        return (0, -1, 1)

    return (0, -1, 1)


def detect_laboratory(all_tables: list) -> str:
    """Detect which lab produced the report"""
    text = str(all_tables).lower()

    if 'євролаб' in text or 'eurolab' in text:
        return 'eurolab'
    elif 'mother and child' in text:
        return 'mother_and_child'
    elif 'biotexcom' in text:
        return 'biotexcom'
    else:
        return 'unknown'


def detect_table_language(table: list[list[str]]) -> str:
    """Detect if table is English or Ukrainian"""
    if not table:
        return 'unknown'

    text = ' '.join([' '.join(row) for row in table]).lower()

    english_markers = ['alleged father', 'alleged mother', 'child', 'locus']
    english_count = sum(1 for marker in english_markers if marker in text)

    ukrainian_markers = ['батько', 'мати', 'дитина', 'локус']
    ukrainian_count = sum(1 for marker in ukrainian_markers if marker in text)

    if english_count > ukrainian_count:
        return 'english'
    elif ukrainian_count > english_count:
        return 'ukrainian'
    else:
        return 'unknown'


def select_best_dna_table(all_tables: list[list[list[str]]]) -> tuple:
    """Select best table: English > Largest"""
    if not all_tables:
        return None, 'no_tables'

    if len(all_tables) == 1:
        return all_tables[0], 'only_one'

    scored_tables = []

    for table in all_tables:
        if not table or not table[0]:
            continue

        size = len(table) * len(table[0])
        language = detect_table_language(table)

        score = size
        if language == 'english':
            score += 10000  # Prefer English
        elif language == 'ukrainian':
            score += 5000

        scored_tables.append({
            'table': table,
            'score': score,
            'language': language
        })

    if not scored_tables:
        return None, 'no_valid'

    best = max(scored_tables, key=lambda x: x['score'])
    return best['table'], best['language']


# ============================================================
# TEXTRACT PARSING
# ============================================================

def extract_all_tables_from_textract(blocks: list[dict]) -> list[list[list[str]]]:
    """Extract ALL tables from Textract blocks"""
    id_map = {block['Id']: block for block in blocks}

    table_blocks = [b for b in blocks if b['BlockType'] == 'TABLE']

    if not table_blocks:
        return []

    all_tables = []

    for table_block in table_blocks:
        child_ids = []
        if 'Relationships' in table_block:
            for rel in table_block['Relationships']:
                if rel['Type'] == 'CHILD':
                    child_ids = rel['Ids']
                    break

        if not child_ids:
            continue

        max_row = 0
        max_col = 0
        cells_data = []

        for child_id in child_ids:
            block = id_map.get(child_id)
            if not block:
                continue

            row = block.get('RowIndex', 0)
            col = block.get('ColumnIndex', 0)
            max_row = max(max_row, row)
            max_col = max(max_col, col)

            cell_text = ''
            if 'Relationships' in block:
                for rel in block['Relationships']:
                    if rel['Type'] == 'CHILD':
                        words = []
                        for word_id in rel['Ids']:
                            word_block = id_map.get(word_id)
                            if word_block and word_block['BlockType'] == 'WORD':
                                words.append(word_block.get('Text', ''))
                        cell_text = ' '.join(words)

            cells_data.append({'row': row, 'col': col, 'text': cell_text})

        if max_row > 0 and max_col > 0:
            table = [['' for _ in range(max_col)] for _ in range(max_row)]
            for cell in cells_data:
                table[cell['row'] - 1][cell['col'] - 1] = cell['text']
            all_tables.append(table)

    return all_tables


def parse_dna_table(table: list[list[str]], data_start_row: int, role_row: int, header_row: int) -> list[dict]:
    """Parse DNA table and extract persons with alleles"""
    max_col = len(table[0]) if table else 0
    persons = []

    for col in range(1, max_col):
        role_text = table[role_row][col] if role_row >= 0 and len(table) > role_row else ''

        if header_row >= 0 and header_row != role_row:
            name = table[header_row][col] if len(table) > header_row else ''
        else:
            name = ''

        if is_empty_column(table, col, data_start_row):
            continue

        skip_keywords = ['index', 'relation', 'status', 'match', 'getting', 'alleles']
        combined_text = f"{name} {role_text}".lower()
        if any(kw in combined_text for kw in skip_keywords) and not any(
                r in combined_text for r in ['father', 'mother', 'child']):
            continue

        role = normalize_role(role_text)

        if name:
            name_lower = name.lower()
            if any(kw in name_lower for kw in ['father', 'mother', 'child', 'alleged', 'status', 'getting']):
                name = ''

        persons.append({
            'col': col,
            'name': name,
            'role': role,
            'alleles': {}
        })

    # Extract alleles
    for row in table[data_start_row:]:
        locus = row[0] if row else ''
        if not locus:
            continue

        for person in persons:
            col = person['col']
            if col < len(row):
                person['alleles'][locus] = normalize_alleles(row[col])

    # Detect role from Amelogenin if missing
    for person in persons:
        if not person['role'] or person['role'] == '' or person['role'] == 'unknown':
            amelogenin = person['alleles'].get('Amelogenin', [])
            person['role'] = detect_role_from_amelogenin(amelogenin)

    return persons


# ============================================================
# CLAUDE VALIDATION
# ============================================================

def validate_with_claude(persons: list[dict], raw_table: list[list[str]], all_tables: list = None) -> dict:
    """Send extracted DNA data to Claude for validation and fixing OCR errors."""
    client = anthropic.Anthropic()

    prompt = f"""You are a DNA data validator. Fix OCR errors and fill missing data.
                
DNA LOCUS TABLE (main table):
{json.dumps(raw_table, indent=2, ensure_ascii=False)}

ALL TABLES FROM DOCUMENT (includes Examination Record with names):
{json.dumps(all_tables, indent=2, ensure_ascii=False)}

EXTRACTED DATA:
{json.dumps(persons, indent=2, ensure_ascii=False)}

---

🔧 FIX THESE ISSUES:

1. **MISSING NAMES** - If name is empty:
   - Look in ALL TABLES for "Examination Record" section
   - Find table with columns like "Name", "Claimed relationship", "DNA source"
   - Match role (Alleged Father, Child, Mother) with name from that table

2. **MERGED LOCI** - Split into separate entries:
   - "D8S1179 D21S11" with values "12, 13 29, 33.2" 
   - → D8S1179: ["12", "13"] AND D21S11: ["29", "33.2"]

3. **LOCUS NAME TYPOS** - Auto-correct:
   - D5S8l8, D5S8I8, D5S81B → D5S818
   - D138317, D13S3l7 → D13S317
   - CSF1P0 (zero) → CSF1PO (letter O)
   - D2IS11 → D21S11
   - VWA → vWA
   - TH01 or THO1 → TH01

4. **ALLELE FORMAT** - Fix OCR errors:
   - "8.8" → ["8", "8"] (two same alleles)
   - "15.16" → ["15", "16"] (OCR read comma as dot)
   - "9.3" → ["9.3"] (keep - real microvariant)
   - "33.2" → ["33.2"] (keep - real microvariant)

5. **ROLE DETECTION** - If role is empty, use Amelogenin:
   - XY → "father" (male)
   - XX → "mother" (female)

6. **EMPTY VALUES** - Keep as empty array: []

7. **SKIP EMPTY PERSONS** - If person has no allele data, remove them

---

📋 VALID LOCUS NAMES:
D1S1656, D2S441, D2S1338, D3S1358, D5S818, D6S1043, D7S820, D8S1179,
D10S1248, D12S391, D13S317, D16S539, D18S51, D19S433, D21S11, D22S1045,
CSF1PO, FGA, TH01, TPOX, vWA, Penta D, Penta E, Amelogenin, Y indel

---

Return ONLY valid JSON (no markdown, no explanation):
{{
  "persons": [
    {{
      "name": "Person Name",
      "role": "father|mother|child",
      "alleles": {{
        "D3S1358": ["15", "16"],
        "Amelogenin": ["X", "Y"]
      }}
    }}
  ],
  "fixes_applied": ["fix 1", "fix 2"]
}}"""

    response = client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}]
    )

    result_text = response.content[0].text

    if '```' in result_text:
        result_text = result_text.split('```')[1]
        if result_text.startswith('json'):
            result_text = result_text[4:]
    result_text = result_text.strip()

    result = json.loads(result_text)

    # Calculate Claude cost
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    # Haiku pricing: $0.25/1M input, $1.25/1M output
    claude_cost = (input_tokens * 0.25 / 1_000_000) + (output_tokens * 1.25 / 1_000_000)

    result['claude_cost'] = round(claude_cost, 6)
    result['claude_tokens'] = {'input': input_tokens, 'output': output_tokens}

    return result


# ============================================================
# MAIN EXTRACTION FUNCTION
# ============================================================

def extract_from_pdf(pdf_path: str) -> dict:
    """Extract DNA data from PDF"""
    logger.info(f"📄 Starting extraction from: {pdf_path}")

    # Convert PDF to images (all pages)
    images = process_dna_report_pdf(
        pdf_path=pdf_path,
        enhance=True,
        detect_tables=False,
        textract_client=None,
        best_page_only=False
    )

    if not images:
        return {'success': False, 'error': 'No images generated'}

    logger.info(f"📄 Processing {len(images)} page(s)")

    # Extract tables from all pages
    textract = TextractService()
    all_pages_tables = []
    textract_cost = 0.0015 * len(images)

    for idx, image in enumerate(images):
        logger.info(f"🔍 Page {idx + 1}/{len(images)}")
        raw_response = textract.extract_raw(image)
        blocks = raw_response.get('Blocks', [])

        page_tables = extract_all_tables_from_textract(blocks)
        if page_tables:
            all_pages_tables.extend(page_tables)

    if not all_pages_tables:
        return {'success': False, 'error': 'No tables found'}

    # Select best table (English preferred)
    table, language = select_best_dna_table(all_pages_tables)

    if not table:
        return {'success': False, 'error': 'No valid table'}

    logger.info(f"✅ Selected {language} table from {len(all_pages_tables)} tables")

    # Detect laboratory
    laboratory = detect_laboratory(all_pages_tables)

    # Parse table
    header_row, role_row, data_start_row = find_header_and_role_rows(table)
    persons = parse_dna_table(table, data_start_row, role_row, header_row)

    persons_for_validation = [
        {'name': p['name'], 'role': p['role'], 'alleles': p['alleles']}
        for p in persons
    ]

    # Validate with Claude
    claude_cost = 0.0
    claude_tokens = {}
    try:
        validated = validate_with_claude(persons_for_validation, table, all_pages_tables)
        response_persons = validated['persons']
        fixes_applied = validated.get('fixes_applied', [])
        claude_cost = validated.get('claude_cost', 0.0)
        claude_tokens = validated.get('claude_tokens', {})
    except Exception as e:
        logger.error(f"Claude failed: {e}")
        response_persons = persons_for_validation
        fixes_applied = []

    total_cost = textract_cost + claude_cost

    logger.info(f"✅ Extraction complete")
    logger.info(f"💰 Total cost: ${total_cost:.4f}")

    return {
        'success': True,
        'persons': response_persons,
        'laboratory': laboratory,
        'loci_count': len(response_persons[0]['alleles']) if response_persons else 0,
        'fixes_applied': fixes_applied,
        'cost': {
            'textract': textract_cost,
            'claude': claude_cost,
            'total': round(total_cost, 6),
            'claude_tokens': claude_tokens,
        }
    }

# ============================================================
# FORMAT CONVERTER
# ============================================================

def convert_to_save_format(extraction_result: dict) -> dict:
    """
    Convert extract_from_pdf() output to save format.
    Priority: Father > Mother (paternity tests focus on father)
    """
    persons = extraction_result.get('persons', [])

    result = {
        'parent': None,
        'parent_role': 'unknown',
        'children': [],
    }

    father_data = None
    mother_data = None

    for person in persons:
        name = person.get('name', 'Unknown')
        role = person.get('role', 'unknown').lower()
        alleles_dict = person.get('alleles', {})

        # Convert alleles dict → loci list
        loci = []
        for locus_name, allele_values in alleles_dict.items():
            locus_data = {
                'locus_name': locus_name,
                'allele_1': allele_values[0] if len(allele_values) > 0 else None,
                'allele_2': allele_values[1] if len(allele_values) > 1 else (
                    allele_values[0] if len(allele_values) == 1 else None
                ),
            }
            loci.append(locus_data)

        person_data = {'name': name, 'loci': loci}

        # ✅ Store father and mother separately
        if role == 'father':
            father_data = person_data
        elif role == 'mother':
            mother_data = person_data
        elif role == 'child':
            result['children'].append(person_data)

    # ✅ Prioritize father over mother
    if father_data:
        result['parent'] = father_data
        result['parent_role'] = 'father'
    elif mother_data:
        result['parent'] = mother_data
        result['parent_role'] = 'mother'

    return result


# ============================================================
# FULL PIPELINE: EXTRACT AND SAVE
# ============================================================

def extract_and_save(file: Any, filename: Optional[str] = None) -> Dict[str, Any]:
    """
    Full pipeline: Extract DNA from PDF and save to database.

    Args:
        file: Uploaded file object (Django/Ninja)
        filename: Optional filename override

    Returns:
        Dict with keys:
            - success: bool
            - persons: List[Dict] (extracted data)
            - laboratory: str
            - loci_count: int
            - fixes_applied: List[str]
            - saved_to_db: bool
            - uploaded_file_id: Optional[int]
            - save_errors: List[str]
            - links: List[Dict] (for duplicate error navigation)
    """

    # Step 1: Save to temp
    temp_path: str = save_temp_file(file)
    logger.info(f"📁 Temp file: {temp_path}")

    if not filename:
        filename = getattr(file, 'name', 'dna_report.pdf')

    # Step 2: Extract from PDF
    result: Dict[str, Any] = extract_from_pdf(temp_path)

    # Step 3: If extraction failed, cleanup and return
    if not result.get('success', False):
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return result

    # Step 4: Convert format for database
    save_format: Dict[str, Any] = convert_to_save_format(result)

    # Step 5: Save to database
    save_result: Dict[str, Any] = save_dna_extraction_to_database(
        extraction_result=save_format,
        filename=filename,
        local_file_path=temp_path
    )

    # Step 6: Merge results
    result['saved_to_db'] = save_result.get('success', False)
    result['uploaded_file_id'] = save_result.get('uploaded_file_id')
    result['save_errors'] = save_result.get('errors', [])
    result['links'] = save_result.get('links', [])

    # Log final cost
    cost: Dict[str, Any] = result.get('cost', {})
    if cost:
        logger.info(f"💰 Total extraction cost: ${cost.get('total', 0):.4f}")

    return result