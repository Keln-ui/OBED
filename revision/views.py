from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
import os
import logging
from .models import Class, Subject, RevisionMaterial, SchemeOfWork
from .forms import SchemeOfWorkGeneratorForm
from pdf_converter.views import revision_access_required
from pdf_converter.payment_utils import payment_required_for_revision, get_revision_material_price

logger = logging.getLogger(__name__)


def revision_home(request):
    """Home page for revision materials"""
    from django.db.models import Sum, Count
    
    # Get all classes grouped by curriculum and level
    cbe_primary = Class.objects.filter(curriculum='cbe', level='primary')
    cbe_secondary = Class.objects.filter(curriculum='cbe', level='secondary')
    cbe_college = Class.objects.filter(curriculum='cbe', level='college')
    
    eight_four_primary = Class.objects.filter(curriculum='844', level='primary')
    eight_four_secondary = Class.objects.filter(curriculum='844', level='secondary')
    eight_four_college = Class.objects.filter(curriculum='844', level='college')
    
    # Get recent materials
    recent_materials = RevisionMaterial.objects.all().order_by('-created_at')[:10]
    
    # Stats
    total_materials = RevisionMaterial.objects.count()
    free_count = RevisionMaterial.objects.filter(is_free=True).count()
    premium_count = total_materials - free_count
    total_downloads = RevisionMaterial.objects.aggregate(total=Sum('download_count'))['total'] or 0
    cbe_total = cbe_primary.count() + cbe_secondary.count() + cbe_college.count()
    eight_four_total = eight_four_primary.count() + eight_four_secondary.count() + eight_four_college.count()
    
    context = {
        'cbe_primary': cbe_primary,
        'cbe_secondary': cbe_secondary,
        'cbe_college': cbe_college,
        'eight_four_primary': eight_four_primary,
        'eight_four_secondary': eight_four_secondary,
        'eight_four_college': eight_four_college,
        'recent_materials': recent_materials,
        'total_materials': total_materials,
        'free_count': free_count,
        'premium_count': premium_count,
        'total_downloads': total_downloads,
        'cbe_total': cbe_total,
        'eight_four_total': eight_four_total,
    }
    
    return render(request, 'revision/home.html', context)


def class_subjects(request, class_id):
    """View all subjects for a specific class"""
    class_obj = get_object_or_404(Class, id=class_id)
    subjects = Subject.objects.filter(class_ref=class_obj).order_by('name')
    
    context = {
        'class_obj': class_obj,
        'subjects': subjects,
    }
    
    return render(request, 'revision/class_subjects.html', context)


@revision_access_required
def subject_materials(request, subject_id):
    """View all materials for a specific subject"""
    subject = get_object_or_404(Subject, id=subject_id)
    materials = RevisionMaterial.objects.filter(subject=subject).order_by('-created_at')
    
    # Group materials by type
    materials_by_type = {}
    for material in materials:
        mat_type = material.get_material_type_display()
        if mat_type not in materials_by_type:
            materials_by_type[mat_type] = []
        materials_by_type[mat_type].append(material)
    
    context = {
        'subject': subject,
        'materials': materials,
        'materials_by_type': materials_by_type,
    }
    
    return render(request, 'revision/subject_materials.html', context)


@revision_access_required
def material_detail(request, material_id):
    """View details of a specific material"""
    material = get_object_or_404(RevisionMaterial, id=material_id)
    
    context = {
        'material': material,
    }
    
    return render(request, 'revision/material_detail.html', context)


@revision_access_required
def download_material(request, material_id):
    """Download a revision material. Marking schemes require login."""
    material = get_object_or_404(RevisionMaterial, id=material_id)
    
    # Marking schemes require authentication
    if material.material_type == 'marking_scheme' and not request.user.is_authenticated:
        return redirect(f'/accounts/login/?next=/revision/material/{material_id}/')
    
    # Check if payment is required globally or for this material
    if payment_required_for_revision(material):
        price = get_revision_material_price(material)
        if price > 0:
            # In a real implementation, redirect to payment page
            # For now, show a message that payment is required
            messages.error(request, f'Payment of KSH {price} is required to download this material. Please contact the administrator.')
            return redirect('material_detail', material_id=material.id)
    
    # All other materials or authenticated users: allow download
    material.increment_downloads()
    
    # Serve the file
    file_path = os.path.join(settings.MEDIA_ROOT, str(material.file))
    if os.path.exists(file_path):
        with open(file_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/octet-stream')
            response['Content-Disposition'] = f'attachment; filename="{os.path.basename(material.file.name)}"'
            return response
    else:
        return HttpResponse('File not found', status=404)


@revision_access_required
def preview_material(request, material_id):
    """Preview a revision material - show first page as text overview"""
    material = get_object_or_404(RevisionMaterial, id=material_id)
    
    preview_text = ""
    preview_pages = 0
    total_pages = 0
    file_type = ""
    preview_available = False
    
    file_path = os.path.join(settings.MEDIA_ROOT, str(material.file))
    
    if os.path.exists(file_path):
        filename_lower = material.file.name.lower()
        file_type = filename_lower.split('.')[-1].upper() if '.' in material.file.name else 'UNKNOWN'
        
        try:
            if filename_lower.endswith('.pdf'):
                import PyPDF2
                with open(file_path, 'rb') as f:
                    pdf_reader = PyPDF2.PdfReader(f)
                    total_pages = len(pdf_reader.pages)
                    preview_pages = min(2, total_pages)
                    
                    preview_lines = []
                    for page_num in range(preview_pages):
                        page = pdf_reader.pages[page_num]
                        text = page.extract_text()
                        if text:
                            lines = text.strip().split('\n')
                            preview_lines.extend(lines[:30])
                    
                    if preview_lines:
                        preview_text = '\n'.join(preview_lines)[:2000]
                        preview_available = True
                    else:
                        # PDF exists but has no extractable text (scanned/image-based)
                        preview_text = "This PDF appears to contain scanned images rather than selectable text. A text preview cannot be generated. Download the file to view its contents."
                        
            elif filename_lower.endswith('.txt'):
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    total_pages = 1
                    preview_pages = 1
                    preview_text = content[:2000]
                    preview_available = True
                    
            elif filename_lower.endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                # Image files - can't show text preview but could show thumbnail
                preview_text = f"This is an image file ({file_type}). A text preview is not available. Download the file to view it."
                
            elif filename_lower.endswith(('.docx', '.doc')):
                preview_text = f"This is a Word document ({file_type}). A text preview is not available in the browser. Download the file to view it."
                
            elif filename_lower.endswith('.pptx'):
                preview_text = f"This is a PowerPoint file ({file_type}). A text preview is not available. Download the file to view it."
                
            else:
                preview_text = f"This file type ({file_type}) is not supported for preview. Download the file to view its contents."
                
        except ImportError as e:
            logger.warning(f"Missing library for preview: {str(e)}")
            preview_text = f"A required library is missing to preview this file. Download the file to view its contents."
            
        except Exception as e:
            logger.warning(f"Could not generate preview for {material.file.name}: {str(e)}")
            preview_text = f"An error occurred while trying to generate a preview for this file. Download the file to view its contents."
    
    context = {
        'material': material,
        'preview_text': preview_text,
        'preview_pages': preview_pages,
        'total_pages': total_pages,
        'file_type': file_type,
        'preview_available': preview_available,
        'is_paid': material.is_free,  # Free materials are effectively "paid"
    }
    
    return render(request, 'revision/material_preview.html', context)


@revision_access_required
def browse_materials(request):
    """Browse all materials with filters"""
    curriculum = request.GET.get('curriculum', '')
    level = request.GET.get('level', '')
    class_id = request.GET.get('class', '')
    material_type = request.GET.get('type', '')
    term = request.GET.get('term', '')
    
    materials = RevisionMaterial.objects.all()
    
    if curriculum:
        materials = materials.filter(subject__class_ref__curriculum=curriculum)
    if level:
        materials = materials.filter(subject__class_ref__level=level)
    if class_id:
        materials = materials.filter(subject__class_ref_id=class_id)
    if material_type:
        materials = materials.filter(material_type=material_type)
    if term:
        materials = materials.filter(term=term)
    
    materials = materials.order_by('-created_at')
    
    # Get filter options
    curricula = Class.CURRICULUM_CHOICES
    levels = Class.LEVEL_CHOICES
    types = RevisionMaterial.MATERIAL_TYPES
    terms = RevisionMaterial.TERM_CHOICES
    
    # Get classes for selected curriculum/level
    classes = []
    if curriculum and level:
        classes = Class.objects.filter(curriculum=curriculum, level=level)
    
    context = {
        'materials': materials,
        'curricula': curricula,
        'levels': levels,
        'types': types,
        'terms': terms,
        'classes': classes,
        'selected_curriculum': curriculum,
        'selected_level': level,
        'selected_class': class_id,
        'selected_type': material_type,
        'selected_term': term,
    }
    
    return render(request, 'revision/browse.html', context)


@revision_access_required
def browse_by_subject(request):
    """Browse all subjects with their materials count"""
    # Get all subjects with material count
    from django.db.models import Count
    subjects = Subject.objects.annotate(
        material_count=Count('materials')
    ).filter(material_count__gt=0).order_by('class_ref__curriculum', 'class_ref__name', 'name')
    
    # Group by curriculum
    cbe_subjects = subjects.filter(class_ref__curriculum='cbe')
    eight_four_subjects = subjects.filter(class_ref__curriculum='844')
    
    context = {
        'cbe_subjects': cbe_subjects,
        'eight_four_subjects': eight_four_subjects,
        'total_subjects': subjects.count(),
    }
    
    return render(request, 'revision/browse_by_subject.html', context)


def browse_schemes(request):
    """Browse all admin-uploaded schemes of work"""
    curriculum = request.GET.get('curriculum', '')
    level = request.GET.get('level', '')
    class_id = request.GET.get('class', '')
    subject_id = request.GET.get('subject', '')
    term = request.GET.get('term', '')
    
    schemes = SchemeOfWork.objects.filter(is_active=True)
    
    if curriculum:
        schemes = schemes.filter(class_ref__curriculum=curriculum)
    if level:
        schemes = schemes.filter(class_ref__level=level)
    if class_id:
        schemes = schemes.filter(class_ref_id=class_id)
    if subject_id:
        schemes = schemes.filter(subject_id=subject_id)
    if term:
        schemes = schemes.filter(term=term)
    
    schemes = schemes.order_by('-academic_year', 'subject', 'term')
    
    context = {
        'schemes': schemes,
        'curricula': Class.CURRICULUM_CHOICES,
        'levels': Class.LEVEL_CHOICES,
        'selected_curriculum': curriculum,
        'selected_level': level,
        'selected_class': class_id,
        'selected_subject': subject_id,
        'selected_term': term,
    }
    
    return render(request, 'revision/browse_schemes.html', context)


def download_scheme(request, scheme_id):
    """Download a scheme of work"""
    scheme = get_object_or_404(SchemeOfWork, id=scheme_id, is_active=True)
    scheme.increment_downloads()
    
    file_path = os.path.join(settings.MEDIA_ROOT, str(scheme.file))
    if os.path.exists(file_path):
        with open(file_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/octet-stream')
            response['Content-Disposition'] = f'attachment; filename="{os.path.basename(scheme.file.name)}"'
            return response
    else:
        return HttpResponse('File not found', status=404)


@user_passes_test(lambda u: u.is_authenticated and u.is_staff)
def link_material(request):
    """Link a past paper to its marking scheme or vice versa (Admin only)"""
    if request.method == 'POST':
        material_id = request.POST.get('material_id')
        related_material_id = request.POST.get('related_material_id')
        
        if material_id and related_material_id:
            try:
                material = get_object_or_404(RevisionMaterial, id=material_id)
                related_material = get_object_or_404(RevisionMaterial, id=related_material_id)
                
                # Link both ways
                material.related_material = related_material
                material.save()
                
                # If the related material doesn't have a link back, create it
                if not related_material.related_material:
                    related_material.related_material = material
                    related_material.save()
                
                messages.success(request, f'Successfully linked "{material.title}" with "{related_material.title}"')
            except Exception as e:
                messages.error(request, f'Error linking materials: {str(e)}')
        else:
            messages.error(request, 'Please select both materials to link')
        
        return redirect('link_material')
    
    # GET request - show the form
    past_papers = RevisionMaterial.objects.filter(material_type='past_paper').order_by('-created_at')
    marking_schemes = RevisionMaterial.objects.filter(material_type='marking_scheme').order_by('-created_at')
    
    context = {
        'past_papers': past_papers,
        'marking_schemes': marking_schemes,
    }
    
    return render(request, 'revision/link_material.html', context)


@user_passes_test(lambda u: u.is_authenticated and u.is_staff)
def generate_scheme_of_work(request):
    """Generate a scheme of work file and save it as a revision material."""
    if request.method == 'POST':
        form = SchemeOfWorkGeneratorForm(request.POST)
        if form.is_valid():
            class_ref = form.cleaned_data['class_ref']
            subject = form.cleaned_data['subject']
            term = form.cleaned_data['term']
            weeks_count = form.cleaned_data['weeks_count']
            topics = form.cleaned_data['topics']
            objectives = form.cleaned_data['objectives']
            
            # Build the scheme of work content
            lines = [
                f"SCHEME OF WORK",
                f"=" * 40,
                f"",
                f"Class: {class_ref.name}",
                f"Curriculum: {class_ref.get_curriculum_display()}",
                f"Subject: {subject.name}",
                f"Term: {dict(RevisionMaterial.TERM_CHOICES).get(term, term)}",
                f"Number of Weeks: {weeks_count}",
                f"",
                f"General Objectives:",
                objectives or "Not specified",
                f"",
                f"=" * 40,
                f"WEEKLY BREAKDOWN:",
                f"=" * 40,
                f"",
            ]
            
            # Split topics into weeks
            topic_list = [t.strip() for t in topics.split('\n') if t.strip()]
            topics_per_week = max(1, len(topic_list) // weeks_count) if topic_list else 1
            
            for week_num in range(1, weeks_count + 1):
                lines.append(f"Week {week_num}:")
                start_idx = (week_num - 1) * topics_per_week
                end_idx = start_idx + topics_per_week
                week_topics = topic_list[start_idx:end_idx] if topic_list else [f"Topic for Week {week_num}"]
                for topic in week_topics:
                    lines.append(f"  - {topic}")
                lines.append(f"  Learning Objectives: To be specified")
                lines.append(f"  Teaching Activities: To be specified")
                lines.append(f"  Assessment Methods: To be specified")
                lines.append("")
            
            content = '\n'.join(lines)
            
            # Save file
            safe_filename = f"SOW_{subject.name}_{class_ref.name}_{term}.txt"
            safe_filename = ''.join(c for c in safe_filename if c.isalnum() or c in ('_', '-', '.')).strip()
            storage_path = f"revision_materials/{safe_filename}"
            generated_file = ContentFile(content.encode('utf-8'))
            saved_path = default_storage.save(storage_path, generated_file)
            
            material = RevisionMaterial.objects.create(
                subject=subject,
                title=f"Scheme of Work - {subject.name} - {class_ref.name}",
                material_type='other',
                term=term,
                description=f"Scheme of Work for {subject.name}, {class_ref.name}",
                file=saved_path,
                is_free=True,
            )
            
            messages.success(request, f'Scheme of Work for {subject.name} has been generated successfully.')
            return redirect('material_detail', material_id=material.id)
    else:
        form = SchemeOfWorkGeneratorForm()
    
    return render(request, 'revision/generate_scheme_of_work.html', {'form': form})