from django.db import models
from django.contrib.auth.models import User


class ConvertedFile(models.Model):
    """Model to track converted files"""
    OUTPUT_FORMATS = [
        ('docx', 'Word Document (.docx)'),
        ('doc', 'Word 97-2003 (.doc)'),
        ('txt', 'Text File (.txt)'),
        ('html', 'HTML Document (.html)'),
        ('json', 'JSON Data (.json)'),
        ('csv', 'CSV Spreadsheet (.csv)'),
        ('pptx', 'PowerPoint Presentation (.pptx)'),
    ]
    
    PAYMENT_STATUS = [
        ('pending', 'Pending Payment'),
        ('paid', 'Paid'),
        ('failed', 'Payment Failed'),
    ]
    
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        help_text="User who uploaded this file"
    )
    original_pdf = models.FileField(upload_to='pdfs/')
    converted_file = models.FileField(upload_to='converted/', null=True, blank=True)
    output_format = models.CharField(max_length=10, choices=OUTPUT_FORMATS, default='docx')
    page_count = models.IntegerField(default=1)
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    mpesa_receipt = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='pending')
    error_message = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.original_pdf.name} - {self.output_format} - {self.status}"

    @property
    def original_pdf_filename(self):
        import os
        return os.path.basename(self.original_pdf.name) if self.original_pdf else ""

    @property
    def converted_file_filename(self):
        import os
        return os.path.basename(self.converted_file.name) if self.converted_file else ""


class Payment(models.Model):
    """Model to track M-Pesa payments"""
    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    conversion = models.ForeignKey(ConvertedFile, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    phone_number = models.CharField(max_length=20)
    mpesa_receipt = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payment {self.id} - {self.amount} KSH - {self.status}"


# ---------------------------------------------------------------------------
# SCHOOL REGISTRATION & SUBSCRIPTION SYSTEM
# ---------------------------------------------------------------------------
class SchoolProfile(models.Model):
    """Registered school with contact and subscription info"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='school_profile', null=True, blank=True)
    school_name = models.CharField(max_length=200)
    school_address = models.TextField(blank=True)
    phone = models.CharField(max_length=20)
    email = models.EmailField()
    principal_name = models.CharField(max_length=200, blank=True)
    registered_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True, help_text="School account is active")

    class Meta:
        ordering = ['school_name']
        verbose_name = 'School Profile'
        verbose_name_plural = 'School Profiles'

    def __str__(self):
        return self.school_name

    def has_active_subscription(self):
        """Check if this school has an active subscription."""
        return self.subscriptions.filter(
            status='active',
            end_date__gte=__import__('datetime').date.today()
        ).exists()


class SubscriptionPlan(models.Model):
    """Pre-defined subscription plans for schools"""
    DURATION_CHOICES = [
        ('termly', 'Per Term'),
        ('yearly', 'Per Year'),
    ]
    
    PLAN_TYPE_CHOICES = [
        ('basic', 'Basic - Conversion Only'),
        ('standard', 'Standard - Conversion + Revision'),
        ('premium', 'Premium - Full Access'),
    ]
    
    PLAN_TARGET_CHOICES = [
        ('individual', 'Individual Users'),
        ('school', 'Schools Only'),
        ('both', 'Both Individual & School'),
    ]
    
    name = models.CharField(max_length=100, help_text="e.g. Basic Plan, Premium Plan")
    plan_type = models.CharField(max_length=20, choices=PLAN_TYPE_CHOICES, default='standard')
    plan_target = models.CharField(max_length=20, choices=PLAN_TARGET_CHOICES, default='both', help_text="Who can subscribe to this plan")
    duration = models.CharField(max_length=10, choices=DURATION_CHOICES, default='yearly')
    amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Subscription fee in KSH")
    max_teachers = models.IntegerField(default=0, help_text="0 = unlimited")
    max_classes = models.IntegerField(default=0, help_text="0 = unlimited")
    includes_revision_access = models.BooleanField(default=True, help_text="Allow access to revision materials")
    includes_pdf_conversion = models.BooleanField(default=True, help_text="Allow PDF conversions")
    includes_ocr = models.BooleanField(default=False, help_text="Allow OCR for scanned documents")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['amount']
        verbose_name = 'Subscription Plan'
        verbose_name_plural = 'Subscription Plans'

    def __str__(self):
        return f"{self.name} - {self.get_duration_display()} ({self.amount} KSH)"


class SchoolSubscription(models.Model):
    """Tracks a school's subscription purchase"""
    STATUS_CHOICES = [
        ('pending', 'Pending Payment'),
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ]

    school = models.ForeignKey(SchoolProfile, on_delete=models.CASCADE, related_name='subscriptions', null=True, blank=True)
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, help_text="Individual user if not school-based")
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50, default='mpesa', help_text="e.g. mpesa, bank")
    mpesa_receipt = models.CharField(max_length=100, blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'School Subscription'
        verbose_name_plural = 'School Subscriptions'

    def __str__(self):
        school_name = self.school.school_name if self.school else 'No School'
        plan_name = self.plan.name if self.plan else 'No Plan'
        return f"{school_name} - {plan_name} - {self.status}"


class SubscriptionPayment(models.Model):
    """Payment record specifically for subscription purchases"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    subscription = models.ForeignKey(SchoolSubscription, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    phone_number = models.CharField(max_length=20)
    mpesa_receipt = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Subscription Payment'
        verbose_name_plural = 'Subscription Payments'

    def __str__(self):
        return f"Sub Payment {self.id} - {self.amount} KSH - {self.status}"


class PaymentSettings(models.Model):
    """Global payment settings controlled by admin."""
    is_free_period = models.BooleanField(
        default=True,
        help_text="When enabled, all conversions and revision materials are free regardless of individual pricing."
    )
    conversion_cost_per_page = models.DecimalField(
        max_digits=10, decimal_places=2, default=2.00,
        help_text="Cost per page in KSH for PDF conversions (applies when free period is OFF)."
    )
    global_revision_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        help_text="Default price in KSH for premium revision materials when free period is OFF. Individual material prices override this if set."
    )
    free_period_start = models.DateField(null=True, blank=True, help_text="Optional start date for automatic free period.")
    free_period_end = models.DateField(null=True, blank=True, help_text="Optional end date for automatic free period.")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Payment Settings'
        verbose_name_plural = 'Payment Settings'

    def __str__(self):
        return f"PaymentSettings (free_period={self.is_free_period})"

    @staticmethod
    def get_active_settings():
        settings_obj, _ = PaymentSettings.objects.get_or_create(pk=1)
        return settings_obj


# ---------------------------------------------------------------------------
# JOB ADVERTISEMENTS
# ---------------------------------------------------------------------------
class JobAdvertisement(models.Model):
    """Job advertisements for BOM and Homeschooling positions"""
    JOB_TYPE_CHOICES = [
        ('bom', 'BOM Teaching Job'),
        ('homeschooling', 'Homeschooling Job'),
    ]
    
    EMPLOYMENT_TYPE_CHOICES = [
        ('full-time', 'Full-time'),
        ('part-time', 'Part-time'),
        ('contract', 'Contract'),
    ]
    
    job_type = models.CharField(max_length=20, choices=JOB_TYPE_CHOICES)
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_TYPE_CHOICES, default='full-time')
    title = models.CharField(max_length=200)
    school_name = models.CharField(max_length=200)
    location = models.CharField(max_length=100)
    description = models.TextField()
    requirements = models.TextField(help_text="List job requirements (one per line)")
    salary_range = models.CharField(max_length=100, help_text="e.g. Ksh 35,000 - 45,000/month")
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    approved = models.BooleanField(default=False, help_text="Job must be approved by admin to appear on website")
    featured = models.BooleanField(default=False, help_text="Featured jobs appear first in rotation")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateField(null=True, blank=True, help_text="Job posting expiry date")
    
    class Meta:
        ordering = ['-featured', '-created_at']
        verbose_name = 'Job Advertisement'
        verbose_name_plural = 'Job Advertisements'
    
    def __str__(self):
        return f"{self.title} - {self.school_name}"
    
    def is_expired(self):
        """Check if job posting has expired"""
        if self.expires_at:
            return self.expires_at < __import__('datetime').date.today()
        return False