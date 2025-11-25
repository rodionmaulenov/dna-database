"""
DNA-related constants used across the application
"""

# Gender markers (not saved to database)
GENDER_MARKERS = ['amelogenin', 'y indel', 'y-indel']

# Critical loci for duplicate detection (most reliable)
CRITICAL_LOCI = [
    'D8S1179', 'D21S11', 'D7S820', 'D3S1358',
    'FGA', 'D13S317', 'D16S539'
]

# All valid STR loci names
VALID_LOCI = [
    'D1S1656', 'D2S441', 'D2S1338', 'D3S1358', 'D5S818',
    'D6S1043', 'D7S820', 'D8S1179', 'D10S1248', 'D12S391',
    'D13S317', 'D16S539', 'D18S51', 'D19S433', 'D21S11',
    'D22S1045', 'CSF1PO', 'FGA', 'TH01', 'TPOX', 'vWA',
    'Penta D', 'Penta E'
]