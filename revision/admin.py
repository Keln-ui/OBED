from django.contrib import admin
from django.utils.html import format_html
from .models import Class, Subject, RevisionMaterial, Curriculum, SchemeOfWork


@admin.register(Curriculum)
class CurriculumAdmin(admin.ModelAdmin):
    list_display = ['subject', 'class_ref', 'curriculum_type', 'academic_year', 'is_active', 'uploaded_at']
    list_filter = ['curriculum_type', 'academic_year', 'is_active', 'class_ref__curriculum', 'class_ref__level']
    search_fields = ['subject__name', 'class_ref__name']
    ordering = ['-academic_year', 'subject']


@admin.register(SchemeOfWork)
class SchemeOfWorkAdmin(admin.ModelAdmin):
    list_display = ['title', 'subject', 'class_ref', 'term', 'academic_year', 'weeks_count', 'download_count', 'is_active', 'uploaded_at']
    list_filter = ['term', 'academic_year', 'is_active', 'class_ref__curriculum', 'class_ref__level', 'subject']
    search_fields = ['title', 'description', 'subject__name', 'class_ref__name']
    ordering = ['-academic_year', 'subject', 'term']
    readonly_fields = ['download_count', 'uploaded_at', 'updated_at']
    
    fieldsets = (
        ('Scheme Information', {
            'fields': ('title', 'subject', 'class_ref', 'description')
        }),
        ('Term & Period', {
            'fields': ('term', 'academic_year', 'weeks_count'),
            'classes': ('wide',),
        }),
        ('File', {
            'fields': ('file',),
        }),
        ('Status', {
            'fields': ('is_active',),
        }),
        ('Statistics', {
            'fields': ('download_count',),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('uploaded_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    list_display = ['name', 'curriculum', 'level', 'created_at']
    list_filter = ['curriculum', 'level', 'created_at']
    search_fields = ['name', 'description']
    ordering = ['curriculum', 'level', 'name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description')
        }),
        ('Curriculum & Level', {
            'fields': ('curriculum', 'level'),
            'classes': ('wide',),
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )
    readonly_fields = ['created_at']


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'class_ref', 'curriculum', 'level', 'materials_count', 'created_at']
    list_filter = ['class_ref__curriculum', 'class_ref__level', 'class_ref']
    search_fields = ['name', 'description', 'class_ref__name']
    ordering = ['class_ref', 'name']
    
    fieldsets = (
        ('Subject Information', {
            'fields': ('name', 'class_ref', 'description')
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )
    readonly_fields = ['created_at']
    
    def curriculum(self, obj):
        if obj.class_ref:
            return obj.class_ref.get_curriculum_display()
        return 'General'
    curriculum.short_description = 'Curriculum'
    curriculum.admin_order_field = 'class_ref__curriculum'
    
    def level(self, obj):
        if obj.class_ref:
            return obj.class_ref.get_level_display()
        return '-'
    level.short_description = 'Level'
    level.admin_order_field = 'class_ref__level'
    
    def materials_count(self, obj):
        count = obj.materials.count()
        url = f'/admin/revision/revisionmaterial/?subject__id__exact={obj.id}'
        return format_html('<a href="{}" style="font-weight: 600; color: #667eea;">{} materials</a>', url, count)
    materials_count.short_description = 'Materials'


@admin.register(RevisionMaterial)
class RevisionMaterialAdmin(admin.ModelAdmin):
    list_display = ['title', 'subject', 'material_type', 'term', 'year', 
                    'is_free', 'price_display', 'download_count', 'created_at']
    list_filter = ['material_type', 'term', 'is_free', 'year',
                   'subject__class_ref__curriculum', 
                   'subject__class_ref__level', 'created_at']
    search_fields = ['title', 'description', 'subject__name', 
                     'subject__class_ref__name']
    ordering = ['-created_at']
    readonly_fields = ['download_count', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Material Information', {
            'fields': ('title', 'subject', 'description')
        }),
        ('Classification', {
            'fields': ('material_type', 'term', 'year'),
            'classes': ('wide',),
        }),
        ('Pricing & Access', {
            'fields': ('is_free', 'price'),
            'classes': ('wide',),
        }),
        ('File', {
            'fields': ('file',),
        }),
        ('Statistics', {
            'fields': ('download_count',),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    def price_display(self, obj):
        if obj.is_free:
            return format_html('<span style="color: #10b981; font-weight: 600;">FREE</span>')
        return format_html('<span style="color: #f59e0b; font-weight: 600;">KSH {}</span>', obj.price)
    price_display.short_description = 'Price'