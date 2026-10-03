from django.db import models


class Class(models.Model):
    """Class level for revision materials"""
    CURRICULUM_CHOICES = [
        ('cbe', 'CBE (Competency-Based Curriculum)'),
        ('844', '8-4-4 Curriculum'),
    ]
    
    LEVEL_CHOICES = [
        ('primary', 'Primary'),
        ('secondary', 'Secondary'),
        ('college', 'College/University'),
    ]
    
    name = models.CharField(max_length=50, help_text="e.g., Form 1, Grade 4, Year 1")
    curriculum = models.CharField(max_length=10, choices=CURRICULUM_CHOICES)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['curriculum', 'level', 'name']
        unique_together = ['name', 'curriculum', 'level']
    
    def __str__(self):
        return f"{self.name} ({self.get_curriculum_display()} - {self.get_level_display()})"


class Subject(models.Model):
    """Subject for revision materials"""
    class_ref = models.ForeignKey(
        Class, 
        on_delete=models.CASCADE, 
        related_name='subjects',
        null=True,
        blank=True,
        help_text="Optional: Link to a specific class. Leave blank for general subjects."
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['class_ref', 'name']
        unique_together = ['class_ref', 'name']
    
    def __str__(self):
        if self.class_ref:
            return f"{self.name} - {self.class_ref.name}"
        return f"{self.name} (General)"


class RevisionMaterial(models.Model):
    """Revision materials (notes, past papers, etc.)"""
    MATERIAL_TYPES = [
        ('notes', 'Notes'),
        ('past_paper', 'Past Paper'),
        ('marking_scheme', 'Marking Scheme'),
        ('syllabus', 'Syllabus'),
        ('textbook', 'Textbook'),
        ('other', 'Other'),
    ]
    
    TERM_CHOICES = [
        ('term1', 'Term 1'),
        ('term2', 'Term 2'),
        ('term3', 'Term 3'),
        ('all', 'All Terms'),
    ]
    
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='materials')
    title = models.CharField(max_length=200)
    material_type = models.CharField(max_length=20, choices=MATERIAL_TYPES, default='notes')
    term = models.CharField(max_length=10, choices=TERM_CHOICES, default='all')
    description = models.TextField(blank=True)
    file = models.FileField(upload_to='revision_materials/')
    year = models.IntegerField(null=True, blank=True, help_text="Year of publication (for past papers)")
    is_free = models.BooleanField(default=True, help_text="Whether this material is free to access")
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Price in KSH (if not free)")
    download_count = models.IntegerField(default=0)
    related_material = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='linked_materials',
        help_text="Link to related material (e.g., link a past paper to its marking scheme)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.subject.name} ({self.get_term_display()})"
    
    def increment_downloads(self):
        self.download_count += 1
        self.save(update_fields=['download_count'])


class Curriculum(models.Model):
    """Store official curriculum documents for AI enhancement"""
    CURRICULUM_TYPE_CHOICES = [
        ('cbc', 'CBC (Competency-Based)'),
        ('844', '8-4-4 Curriculum'),
    ]
    
    class_ref = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='curricula')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='curricula')
    curriculum_type = models.CharField(max_length=20, choices=CURRICULUM_TYPE_CHOICES, default='cbc')
    academic_year = models.CharField(max_length=20, help_text="e.g., 2024, 2025")
    file = models.FileField(upload_to='curricula/', help_text="Upload official curriculum document (PDF/DOCX)")
    extracted_topics = models.TextField(blank=True, help_text="Extracted topics from curriculum (internal use)")
    is_active = models.BooleanField(default=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-academic_year', 'subject']
        unique_together = ['class_ref', 'subject', 'academic_year', 'curriculum_type']
    
    def __str__(self):
        return f"{self.subject.name} - {self.class_ref.name} ({self.academic_year})"


class SchemeOfWork(models.Model):
    """Pre-made scheme of work documents uploaded by admins for users to download"""
    class_ref = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='schemes')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='schemes')
    title = models.CharField(max_length=255, help_text="Title for the scheme (e.g., 'Mathematics Scheme of Work - Term 1 2024')")
    TERM_CHOICES = [
        ('term1', 'Term 1'),
        ('term2', 'Term 2'),
        ('term3', 'Term 3'),
    ]
    term = models.CharField(max_length=10, choices=TERM_CHOICES, default='term1')
    academic_year = models.CharField(max_length=20, help_text="e.g., 2024, 2025")
    weeks_count = models.IntegerField(default=12, help_text="Number of weeks in the scheme")
    file = models.FileField(upload_to='schemes_of_work/', help_text="Upload the scheme of work file (PDF/DOCX/TXT)")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    download_count = models.IntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-academic_year', 'subject', 'term']
        unique_together = ['class_ref', 'subject', 'term', 'academic_year']
    
    def __str__(self):
        return f"{self.subject.name} - {self.class_ref.name} ({self.get_term_display()}, {self.academic_year})"
    
    def increment_downloads(self):
        self.download_count += 1
        self.save(update_fields=['download_count'])