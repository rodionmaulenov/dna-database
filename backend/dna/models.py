from django.db import models


class UploadedFile(models.Model):
    file = models.FileField(upload_to='uploads/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']


class Person(models.Model):
    ROLE_CHOICES = [
        ('father', 'Father'),
        ('mother', 'Mother'),
        ('child', 'Child'),
    ]

    uploaded_file = models.ForeignKey(UploadedFile, on_delete=models.CASCADE, related_name='persons')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    name = models.CharField(max_length=255)
    loci_count = models.IntegerField(default=0, help_text="Number of analyzed loci")

    class Meta:
        indexes = [
            models.Index(fields=['role']),
        ]



class DNALocus(models.Model):
    LOCUS_NAMES = [
        'D1S1656', 'D2S441', 'D2S1338', 'D3S1358', 'D5S818',
        'D6S1043', 'D7S820', 'D8S1179', 'D10S1248', 'D12S391',
        'D13S317', 'D16S539', 'D18S51', 'D19S433', 'D21S11',
        'D22S1045', 'CSF1PO', 'FGA', 'TH01', 'TPOX', 'vWA',
        'Penta D', 'Penta E',
    ]
    LOCUS_CHOICES = [(name, name) for name in LOCUS_NAMES]

    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='loci')
    locus_name = models.CharField(max_length=50, choices=LOCUS_CHOICES)
    allele_1 = models.CharField(max_length=10, blank=True, null=True)
    allele_2 = models.CharField(max_length=10, blank=True, null=True)


    class Meta:
        unique_together = ['person', 'locus_name']
        indexes = [
            models.Index(fields=['locus_name']),  # Speed up locus lookups
            models.Index(fields=['allele_1', 'allele_2']),  # Speed up allele comparisons
            models.Index(fields=['person', 'locus_name']),  # Already optimized by unique_together
        ]
