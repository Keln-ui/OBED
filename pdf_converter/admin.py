from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from .models import ConvertedFile, Payment, SchoolProfile, SubscriptionPlan, SchoolSubscription, SubscriptionPayment, PaymentSettings


# ---------------------------------------------------------------------------
# Custom User Admin — uses Django's default deletion behavior
# ---------------------------------------------------------------------------
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass
admin.site.register(User, UserAdmin)


# ---------------------------------------------------------------------------
# ConvertedFile Admin
# ---------------------------------------------------------------------------
@admin.register(ConvertedFile)
class ConvertedFileAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_filename', 'output_format', 'page_count', 'cost',
                    'payment_status', 'status', 'created_at')
    list_filter = ('output_format', 'payment_status', 'status')
    search_fields = ('original_pdf',)
    readonly_fields = ('created_at',)

    def get_filename(self, obj):
        return obj.original_pdf_filename
    get_filename.short_description = 'File Name'


# ---------------------------------------------------------------------------
# Payment Admin
# ---------------------------------------------------------------------------
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversion', 'amount', 'phone_number', 'mpesa_receipt', 'status', 'created_at')
    list_filter = ('status',)
    readonly_fields = ('created_at', 'updated_at')


# ---------------------------------------------------------------------------
# SchoolProfile Admin
# ---------------------------------------------------------------------------
@admin.register(SchoolProfile)
class SchoolProfileAdmin(admin.ModelAdmin):
    list_display = ('school_name', 'phone', 'email', 'principal_name', 'is_active', 'registered_at')
    list_filter = ('is_active',)
    search_fields = ('school_name', 'phone', 'email')
    readonly_fields = ('registered_at',)


# ---------------------------------------------------------------------------
# SubscriptionPlan Admin
# ---------------------------------------------------------------------------
@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'plan_type', 'plan_target', 'duration', 'amount',
                    'includes_revision_access', 'includes_pdf_conversion', 'includes_ocr', 'is_active')
    list_filter = ('plan_type', 'plan_target', 'duration', 'is_active',
                   'includes_revision_access', 'includes_pdf_conversion', 'includes_ocr')
    search_fields = ('name', 'description')
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'plan_type', 'plan_target', 'duration', 'amount', 'description')
        }),
        ('Access Control', {
            'fields': ('includes_revision_access', 'includes_pdf_conversion', 'includes_ocr'),
            'description': 'Select what features this plan includes'
        }),
        ('Limits', {
            'fields': ('max_teachers', 'max_classes')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )


# ---------------------------------------------------------------------------
# SchoolSubscription Admin
# ---------------------------------------------------------------------------
@admin.register(SchoolSubscription)
class SchoolSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('school', 'plan', 'amount_paid', 'start_date', 'end_date', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('school__school_name',)
    readonly_fields = ('created_at', 'updated_at')


# ---------------------------------------------------------------------------
# SubscriptionPayment Admin
# ---------------------------------------------------------------------------
@admin.register(SubscriptionPayment)
class SubscriptionPaymentAdmin(admin.ModelAdmin):
    list_display = ('subscription', 'amount', 'phone_number', 'mpesa_receipt', 'status', 'created_at')
    list_filter = ('status',)
    readonly_fields = ('created_at', 'updated_at')


# ---------------------------------------------------------------------------
# PaymentSettings Admin (singleton)
# ---------------------------------------------------------------------------
@admin.register(PaymentSettings)
class PaymentSettingsAdmin(admin.ModelAdmin):
    list_display = ('is_free_period', 'conversion_cost_per_page', 'global_revision_price', 'free_period_start', 'free_period_end', 'updated_at')
    readonly_fields = ('updated_at',)

    def has_add_permission(self, request):
        return not PaymentSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
