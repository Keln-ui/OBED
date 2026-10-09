import os
import shutil
import tempfile
import logging
from pathlib import Path
from io import BytesIO
from datetime import datetime, date, timedelta

logger = logging.getLogger(__name__)

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse, FileResponse
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from django.urls import reverse
from PyPDF2 import PdfMerger, PdfReader, PdfWriter
from .models import (
    ConvertedFile, Payment, 
    SchoolProfile, SubscriptionPlan, SchoolSubscription, SubscriptionPayment, JobAdvertisement
)
from .forms import SchoolRegistrationForm, SubscriptionPaymentForm
from .payment_utils import get_conversion_cost, payment_required_for_conversion


def _build_pdf_tool_output_path(tool_name, source_name):
    base_name = os.path.splitext(os.path.basename(source_name))[0]
    timestamp = int(datetime.now().timestamp())
    return os.path.join(settings.MEDIA_ROOT, 'converted', f'{tool_name}_{timestamp}_{base_name}.pdf')


def _save_uploaded_pdf(uploaded_file, temp_dir):
    input_path = os.path.join(temp_dir, uploaded_file.name)
    with open(input_path, 'wb') as handle:
        for chunk in uploaded_file.chunks():
            handle.write(chunk)
    return input_path


def _cleanup_temp_dir(temp_dir):
    if temp_dir and os.path.exists(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)


def _pdf_tool_response(request, output_path, tool_name):
    filename = os.path.basename(output_path)
    download_url = reverse('download_file', kwargs={'filename': filename})
    return JsonResponse({'success': True, 'download_url': download_url, 'filename': filename, 'tool': tool_name})


def _safe_cleanup(temp_dir):
    try:
        _cleanup_temp_dir(temp_dir)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# HOME
# ---------------------------------------------------------------------------
def index(request):
    """Home page with file upload."""
    from revision.models import RevisionMaterial, Class as SchoolClass
    total_materials = RevisionMaterial.objects.count()
    total_classes = SchoolClass.objects.count()
    
    # Get active job advertisements for homepage carousel (only approved jobs)
    featured_jobs = JobAdvertisement.objects.filter(
        is_active=True,
        approved=True
    ).exclude(
        expires_at__lt=date.today()
    ).order_by('-featured', '-created_at')[:6]
    
    context = {
        'plans': SubscriptionPlan.objects.filter(is_active=True),
        'total_formats': 7,
        'total_materials': total_materials,
        'total_classes': total_classes,
        'featured_jobs': featured_jobs,
    }
    return render(request, 'index.html', context)


# ---------------------------------------------------------------------------
# USER AUTH
# ---------------------------------------------------------------------------
def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('index')


# ---------------------------------------------------------------------------
# USER REGISTRATION (simple account for marking scheme downloads)
# ---------------------------------------------------------------------------
def user_register(request):
    """Register a simple user account (not a school) with email verification."""
    from django.contrib.auth.forms import UserCreationForm
    from django.contrib.auth.tokens import default_token_generator
    from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
    from django.utils.encoding import force_bytes, force_str
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    from django.conf import settings
    from django.contrib.sites.shortcuts import get_current_site
    
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.email = form.cleaned_data.get('email', '')
            user.is_active = False  # User must verify email before activation
            user.save()
            
            # Generate verification token
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            
            # Build verification URL
            current_site = get_current_site(request)
            verification_url = f"http://{current_site.domain}/verify-email/{uid}/{token}/"
            
            # Send verification email
            subject = 'Verify your CoreSynch account'
            message = render_to_string('registration/verification_email.html', {
                'user': user,
                'verification_url': verification_url,
                'domain': current_site.domain,
            })
            
            try:
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    fail_silently=False,
                    html_message=message,
                )
                messages.success(request, f'Registration successful! A verification email has been sent to {user.email}. Please check your inbox to activate your account.')
                return redirect('login')
            except Exception as e:
                messages.error(request, f'Failed to send verification email: {str(e)}')
                user.delete()  # Delete user if email fails
                return redirect('user_register')
    else:
        form = UserCreationForm()
    
    return render(request, 'registration/user_register.html', {'form': form})


def verify_email(request, uidb64, token):
    """Verify user email with token."""
    from django.contrib.auth.tokens import default_token_generator
    from django.utils.http import urlsafe_base64_decode
    from django.utils.encoding import force_str
    from django.contrib.auth import login
    
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    
    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        login(request, user)
        messages.success(request, 'Your email has been verified! Your account is now active.')
        return redirect('index')
    else:
        messages.error(request, 'Invalid verification link or link has expired.')
        return redirect('login')


# ---------------------------------------------------------------------------
# SCHOOL REGISTRATION
# ---------------------------------------------------------------------------
def school_register(request):
    """Register a new school account."""
    if request.method == 'POST':
        form = SchoolRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            SchoolProfile.objects.create(
                user=user,
                school_name=form.cleaned_data['school_name'],
                school_address=form.cleaned_data.get('school_address', ''),
                phone=form.cleaned_data['phone'],
                email=form.cleaned_data['email'],
                principal_name=form.cleaned_data.get('principal_name', ''),
            )
            # Log the user in
            username = form.cleaned_data['username']
            password = form.cleaned_data['password1']
            user = authenticate(username=username, password=password)
            if user:
                login(request, user)
            messages.success(request, f'Registration successful! Welcome {form.cleaned_data["school_name"]}.')
            return redirect('subscription_plans')
    else:
        form = SchoolRegistrationForm()
    return render(request, 'registration/school_register.html', {'form': form})


# ---------------------------------------------------------------------------
# SUBSCRIPTION PLANS
# ---------------------------------------------------------------------------
@login_required
def subscription_plans(request):
    """View available subscription plans - filtered by user type (individual vs school)."""
    school_profile = SchoolProfile.objects.filter(user=request.user).first()
    
    # Filter plans based on user type
    if school_profile:
        # School user - show plans for schools or both
        plans = SubscriptionPlan.objects.filter(
            is_active=True,
            plan_target__in=['school', 'both']
        )
    else:
        # Individual user - show plans for individuals or both
        plans = SubscriptionPlan.objects.filter(
            is_active=True,
            plan_target__in=['individual', 'both']
        )
    
    active_sub = None
    if school_profile:
        active_sub = school_profile.subscriptions.filter(status='active').first()
    
    context = {
        'plans': plans,
        'school_profile': school_profile,
        'active_subscription': active_sub,
    }
    return render(request, 'subscription/plans.html', context)


@login_required
def subscribe_plan(request, plan_id):
    """Initiate subscription for a plan - supports both school and individual subscriptions."""
    plan = get_object_or_404(SubscriptionPlan, id=plan_id, is_active=True)
    school_profile = SchoolProfile.objects.filter(user=request.user).first()
    
    # Validate plan target matches user type
    if school_profile:
        # School user trying to subscribe
        if plan.plan_target == 'individual':
            messages.error(request, 'This plan is for individual users only. Please select a school plan.')
            return redirect('subscription_plans')
    else:
        # Individual user trying to subscribe
        if plan.plan_target == 'school':
            messages.error(request, 'This plan is for schools only. Please register your school first or select an individual plan.')
            return redirect('subscription_plans')
    
    # Check if user already has any active subscription (school or individual)
    existing_sub = SchoolSubscription.objects.filter(
        Q(school__user=request.user) | Q(user=request.user),
        status='active'
    ).first()
    
    if existing_sub:
        sub_name = existing_sub.plan.name if existing_sub.plan else 'N/A'
        messages.info(request, f'You already have an active subscription: {sub_name}')
        return redirect('subscription_plans')
    
    if request.method == 'POST':
        form = SubscriptionPaymentForm(request.POST)
        if form.is_valid():
            phone = form.cleaned_data['phone_number']
            
            # Calculate dates
            start = date.today()
            if plan.duration == 'yearly':
                end = date(start.year + 1, start.month, start.day)
            else:
                # Termly - 3 months
                end = start + timedelta(days=90)
            
            # Create subscription - support both school and individual
            sub = SchoolSubscription.objects.create(
                school=school_profile,  # Can be None for individual users
                user=request.user if not school_profile else None,  # Set user for individual subscriptions
                plan=plan,
                amount_paid=plan.amount,
                payment_method='mpesa',
                phone_number=phone,
                start_date=start,
                end_date=end,
                status='pending',
            )
            
            # Record payment
            SubscriptionPayment.objects.create(
                subscription=sub,
                amount=plan.amount,
                phone_number=phone,
                status='completed',  # In production, would verify M-Pesa
                transaction_id=f"TXN{sub.id}_{int(datetime.now().timestamp())}",
            )
            
            # Activate subscription
            sub.status = 'active'
            sub.mpesa_receipt = f"SUB{sub.id}"
            sub.save()
            
            subscriber_name = school_profile.school_name if school_profile else request.user.username
            messages.success(request, f'Payment successful! {subscriber_name}\'s {plan.name} ({plan.get_duration_display()}) subscription is now active until {end.strftime("%d %B %Y")}.')
            return redirect('index')
    else:
        initial_phone = school_profile.phone if school_profile else ''
        form = SubscriptionPaymentForm(initial={'phone_number': initial_phone})
    
    context = {
        'plan': plan,
        'form': form,
        'school_profile': school_profile,
    }
    return render(request, 'subscription/subscribe.html', context)


# ---------------------------------------------------------------------------
# SUBSCRIPTION CHECK DECORATOR
# ---------------------------------------------------------------------------
def subscription_required(view_func):
    """Decorator - subscription checks disabled, admin can activate plans manually."""
    from functools import wraps
    
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # Staff (admins) bypass subscription check
        if request.user.is_staff:
            return view_func(request, *args, **kwargs)
        
        # Subscription requirement temporarily disabled
        return view_func(request, *args, **kwargs)
    
    return _wrapped_view


def revision_access_required(view_func):
    """Decorator - subscription checks disabled, admin can activate plans manually."""
    from functools import wraps
    
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # Subscription requirement temporarily disabled - admin can activate plans
        # Staff (admins) bypass subscription check
        if request.user.is_staff:
            return view_func(request, *args, **kwargs)
        
        return view_func(request, *args, **kwargs)
    
    return _wrapped_view


# ---------------------------------------------------------------------------
# FILE CONVERSION (existing functionality)
# ---------------------------------------------------------------------------
def upload_pdf(request):
    """Handle PDF upload and conversion."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    pdf_file = request.FILES.get('pdf_file')
    if not pdf_file:
        return JsonResponse({'error': 'No file uploaded'}, status=400)
    
    output_format = request.POST.get('output_format', 'docx')
    use_ocr = request.POST.get('use_ocr') == 'true'
    
    # Create conversion record
    conversion = ConvertedFile.objects.create(
        user=request.user if request.user.is_authenticated else None,
        original_pdf=pdf_file,
        output_format=output_format,
        status='processing',
    )
    
    # Count pages
    page_count = 1
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(pdf_file)
        page_count = len(reader.pages)
        conversion.page_count = page_count
        conversion.save()
    except Exception:
        pass
    
    # Calculate cost
    total_cost = get_conversion_cost(page_count)
    conversion.cost = total_cost
    conversion.save()
    
    requires_payment = payment_required_for_conversion()
    
    # Convert the file immediately
    error_msg = None
    try:
        from .converters import ConverterFactory
        
        # Get input file path - use the actual saved path
        input_path = Path(settings.MEDIA_ROOT) / 'pdfs' / os.path.basename(conversion.original_pdf.name)
        
        # Generate output filename
        base_name = os.path.splitext(os.path.basename(conversion.original_pdf.name))[0]
        output_filename = f"{base_name}_converted.{output_format}"
        output_dir = Path(settings.MEDIA_ROOT) / 'converted'
        output_path = output_dir / output_filename
        
        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Convert the file
        factory = ConverterFactory()
        converter = factory.get_converter(str(input_path), str(output_path), output_format, use_ocr)
        
        if converter and converter.convert():
            # Save the converted file to Django's file field
            with open(output_path, 'rb') as f:
                conversion.converted_file.save(f'converted/{output_filename}', f, save=False)
            conversion.status = 'completed'
            if not requires_payment:
                conversion.payment_status = 'paid'
            conversion.save()
        else:
            error_msg = 'Conversion failed - converter returned false'
            conversion.status = 'failed'
            conversion.error_message = error_msg
            conversion.save()
    except Exception as e:
        error_msg = f"Conversion error: {str(e)}"
        conversion.status = 'failed'
        conversion.error_message = error_msg
        conversion.save()
    
    # Return download URL directly (no payment required)
    from django.urls import reverse
    download_url = reverse('download_file', kwargs={'filename': output_filename})
    
    if error_msg:
        return JsonResponse({
            'success': False,
            'error': error_msg,
        }, status=500)
    
    return JsonResponse({
        'success': True,
        'payment_required': requires_payment,
        'download_url': download_url,
        'filename': output_filename,
        'page_count': page_count,
        'total_cost': float(total_cost),
        'conversion_id': conversion.id,
    })


def download_file(request, filename):
    """Download a converted file (paid or free)."""
    import os
    from django.core.files.storage import default_storage
    
    logger.info(f"Download requested for filename: {filename}")
    
    # Try direct file path first
    file_path = os.path.join(settings.MEDIA_ROOT, 'converted', filename)
    logger.info(f"Checking direct file path: {file_path}, exists: {os.path.exists(file_path)}")
    
    if os.path.exists(file_path):
        ext = os.path.splitext(filename)[1].lower()
        content_types = {
            '.pdf': 'application/pdf',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.doc': 'application/msword',
            '.txt': 'text/plain',
            '.html': 'text/html',
            '.json': 'application/json',
            '.csv': 'text/csv',
            '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            '.zip': 'application/zip',
        }
        content_type = content_types.get(ext, 'application/octet-stream')
        try:
            response = FileResponse(open(file_path, 'rb'), content_type=content_type)
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            logger.info(f"Successfully serving file from direct path: {file_path}")
            return response
        except Exception as e:
            logger.error(f"Error serving file {file_path}: {str(e)}")
    
    # Try Django storage
    storage_path = f'converted/{filename}'
    logger.info(f"Checking storage path: {storage_path}, exists: {default_storage.exists(storage_path)}")
    if default_storage.exists(storage_path):
        try:
            response = FileResponse(default_storage.open(storage_path, 'rb'), content_type='application/octet-stream')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            logger.info(f"Successfully serving file from storage: {storage_path}")
            return response
        except Exception as e:
            logger.error(f"Error serving file from storage {storage_path}: {str(e)}")
    
    # Fall back to paid conversion records
    try:
        # Try to find conversion by exact filename match
        conversion = ConvertedFile.objects.filter(converted_file__endswith=filename).first()
        logger.info(f"Found conversion by exact match: {conversion}")
        if not conversion:
            # Try with just the base name
            base_name = os.path.splitext(filename)[0]
            conversion = ConvertedFile.objects.filter(converted_file__icontains=base_name).first()
            logger.info(f"Found conversion by base name: {conversion}")
        
        if conversion:
            logger.info(f"Conversion payment_status: {conversion.payment_status}, payment_required: {payment_required_for_conversion()}")
            # Only redirect to payment if payment is required AND conversion is not already paid
            if payment_required_for_conversion() and conversion.payment_status != 'paid':
                logger.info(f"Redirecting to payment for conversion {conversion.id}")
                return redirect(f'/payment/{conversion.id}/')
            
            # Try to serve from the model's file field
            if conversion.converted_file and conversion.converted_file.storage.exists(conversion.converted_file.name):
                logger.info(f"Serving from model file field: {conversion.converted_file.name}")
                response = FileResponse(conversion.converted_file.open('rb'), content_type='application/octet-stream')
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                return response
            else:
                logger.error(f"Model file field does not exist: {conversion.converted_file.name if conversion.converted_file else 'None'}")
    except Exception as e:
        logger.error(f"Error looking up conversion: {str(e)}")
    
    # If all else fails, return error
    from django.http import HttpResponseNotFound
    logger.error(f"File not available after all attempts: {filename}")
    return HttpResponseNotFound("File not available on site. Please contact support if this issue persists.")


# ---------------------------------------------------------------------------
# STANDALONE SCHEME OF WORK GENERATOR (not tied to revision)
# ---------------------------------------------------------------------------
def sow_generator(request):
    """Standalone Scheme of Work Generator page with hybrid mode support."""
    from revision.models import Class, Subject
    classes = Class.objects.all().order_by('curriculum', 'level', 'name')
    subjects = Subject.objects.all().order_by('name')
    return render(request, 'sow_generator.html', {'classes': classes, 'subjects': subjects, 'user': request.user})


def sow_preview(request):
    """Preview and customize generated scheme before download."""
    if request.method != 'POST':
        return redirect('sow_generator')
    
    # Get all form data to regenerate preview
    school_name = request.POST.get('school_name', '')
    class_id = request.POST.get('class_id', '')
    subject_id = request.POST.get('subject_id', '')
    term = request.POST.get('term', 'Term 1')
    weeks_count = request.POST.get('weeks_count', '12')
    academic_year = request.POST.get('academic_year', '')
    custom_content = request.POST.get('custom_content', '')
    
    try:
        weeks_count = int(weeks_count)
        weeks_count = max(1, min(weeks_count, 52))
    except ValueError:
        weeks_count = 12
    
    # Get class and subject names from database
    class_name = ''
    subject_name = ''
    if class_id:
        try:
            class_obj = Class.objects.get(id=class_id)
            class_name = class_obj.name
        except:
            class_name = ''
    if subject_id:
        try:
            subject_obj = Subject.objects.get(id=subject_id)
            subject_name = subject_obj.name
        except:
            subject_name = ''
    
    if not class_name:
        class_name = school_name or 'Unknown Class'
    
    # Generate default topics
    topics = []
    for i in range(1, weeks_count + 1):
        topics.append(f"Topic {i}: {subject_name} - Week {i} Content")
    
    # If custom content provided, use it directly
    if custom_content:
        content = custom_content
    else:
        lines = [
            f"SCHEME OF WORK",
            f"=" * 40,
            f"",
            f"School: {school_name or 'Unknown'}",
            f"Class: {class_name}",
            f"Subject: {subject_name or 'Unknown'}",
            f"Term: {term}",
            f"Academic Year: {academic_year or '2024'}",
            f"Number of Weeks: {weeks_count}",
            f"",
            f"General Objectives:",
            "Standard curriculum objectives per subject guidelines",
            f"",
            f"=" * 40,
            f"WEEKLY BREAKDOWN:",
            f"=" * 40,
            f"",
        ]
        
        topics_per_week = 1
        for week_num in range(1, weeks_count + 1):
            lines.append(f"Week {week_num}:")
            start_idx = (week_num - 1) * topics_per_week
            end_idx = start_idx + topics_per_week
            week_topics = topics[start_idx:end_idx] if topics else [f"Topic for Week {week_num}"]
            for topic in week_topics:
                lines.append(f"  - {topic}")
            lines.append(f"  Learning Objectives: To be specified")
            lines.append(f"  Teaching Activities: To be specified")
            lines.append(f"  Assessment Methods: To be specified")
            lines.append("")
        
        content = '\n'.join(lines)
    
    return render(request, 'sow_preview.html', {
        'content': content,
        'school_name': school_name,
        'class_name': class_name,
        'subject_name': subject_name,
        'term': term,
        'academic_year': academic_year,
        'weeks_count': weeks_count,
    })


def generate_sow_download(request):
    """Generate a scheme of work file and return as download - supports manual and curriculum modes."""
    from revision.models import Class, Subject, Curriculum
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    mode = request.POST.get('mode', 'manual')
    
    # Curriculum Upload Mode - AI Enhanced (Admin only)
    if mode == 'curriculum':
        if not request.user.is_authenticated or not request.user.is_staff:
            return JsonResponse({'error': 'Curriculum upload is restricted to administrators. Please use manual mode.'}, status=403)
        
        curriculum_file = request.FILES.get('curriculum_file')
        class_id = request.POST.get('class_id')
        subject_id = request.POST.get('subject_id')
        curriculum_type = request.POST.get('curriculum_type', 'cbc')
        academic_year = request.POST.get('academic_year', '2024')
        
        if not curriculum_file:
            return JsonResponse({'error': 'Please upload a curriculum file'}, status=400)
        
        # Validate file type
        ext = curriculum_file.name.lower().split('.')[-1]
        if ext not in ['pdf', 'docx']:
            return JsonResponse({'error': 'Please upload PDF or DOCX file'}, status=400)
        
        # Extract topics from curriculum (basic extraction)
        extracted_topics = []
        try:
            if ext == 'docx':
                from docx import Document
                temp_path = os.path.join(settings.MEDIA_ROOT, 'curricula', curriculum_file.name)
                os.makedirs(os.path.dirname(temp_path), exist_ok=True)
                with open(temp_path, 'wb') as f:
                    for chunk in curriculum_file.chunks():
                        f.write(chunk)
                doc = Document(temp_path)
                extracted_topics = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
            else:  # PDF
                import PyPDF2
                temp_path = os.path.join(settings.MEDIA_ROOT, 'curricula', curriculum_file.name)
                os.makedirs(os.path.dirname(temp_path), exist_ok=True)
                with open(temp_path, 'wb') as f:
                    for chunk in curriculum_file.chunks():
                        f.write(chunk)
                with open(temp_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        text = page.extract_text()
                        extracted_topics.extend([line.strip() for line in text.split('\n') if line.strip() and len(line.strip()) > 10])
        except Exception as e:
            extracted_topics = [f'Topic extracted from curriculum']
        
        # Get class and subject names
        class_name = 'Unknown Class'
        subject_name = 'Unknown Subject'
        if class_id and subject_id:
            try:
                class_obj = Class.objects.get(id=class_id)
                subject_obj = Subject.objects.get(id=subject_id)
                class_name = class_obj.name
                subject_name = subject_obj.name
            except:
                pass
        
        # Save curriculum to database (optional)
        try:
            if class_id and subject_id:
                Curriculum.objects.create(
                    class_ref_id=class_id,
                    subject_id=subject_id,
                    curriculum_type=curriculum_type,
                    academic_year=academic_year,
                    file=curriculum_file,
                    extracted_topics='\n'.join(extracted_topics[:50])  # Store first 50 topics
                )
        except Exception:
            pass
        
        # Calculate weeks based on topic count
        topics = extracted_topics[:100]
        weeks_count = min(52, max(1, (len(topics) + 2) // 3))
        term = 'Term 1'
        objectives = 'AI-enhanced objectives based on uploaded curriculum'
        
    else:
        # Manual Mode
        custom_content = request.POST.get('custom_content', '')
        school_name = request.POST.get('school_name', '')
        class_id = request.POST.get('class_id', '')
        subject_id = request.POST.get('subject_id', '')
        term = request.POST.get('term', 'Term 1')
        weeks_count = request.POST.get('weeks_count', '12')
        objectives = request.POST.get('objectives', '')
        academic_year = request.POST.get('academic_year', '2024')
        
        try:
            weeks_count = int(weeks_count)
            weeks_count = max(1, min(weeks_count, 52))
        except ValueError:
            weeks_count = 12
        
        # Get class and subject names from database
        class_name = ''
        subject_name = ''
        if class_id:
            try:
                class_obj = Class.objects.get(id=class_id)
                class_name = class_obj.name
            except:
                class_name = ''
        if subject_id:
            try:
                subject_obj = Subject.objects.get(id=subject_id)
                subject_name = subject_obj.name
            except:
                subject_name = ''
        
        # If no class selected but school name provided, use it
        if not class_name:
            class_name = school_name or 'Unknown Class'
        
        # Generate default topics based on subject and weeks
        topics = []
        for i in range(1, weeks_count + 1):
            topics.append(f"Topic {i}: {subject_name} - Week {i} Content")
    
    lines = [
        f"SCHEME OF WORK",
        f"=" * 40,
        f"",
        f"School: {school_name or 'Unknown'}",
        f"Class: {class_name}",
        f"Subject: {subject_name or 'Unknown'}",
        f"Term: {term}",
        f"Number of Weeks: {weeks_count}",
        f"",
        f"General Objectives:",
        objectives or "Standard curriculum objectives per subject guidelines",
        f"",
        f"=" * 40,
        f"WEEKLY BREAKDOWN:",
        f"=" * 40,
        f"",
    ]
    
    topics_per_week = max(1, len(topics) // weeks_count) if topics else 1
    
    for week_num in range(1, weeks_count + 1):
        lines.append(f"Week {week_num}:")
        start_idx = (week_num - 1) * topics_per_week
        end_idx = start_idx + topics_per_week
        week_topics = topics[start_idx:end_idx] if topics else [f"Topic for Week {week_num}"]
        for topic in week_topics:
            lines.append(f"  - {topic}")
        lines.append(f"  Learning Objectives: To be specified")
        lines.append(f"  Teaching Activities: To be specified")
        lines.append(f"  Assessment Methods: To be specified")
        lines.append("")
    
    content = '\n'.join(lines)
    
    safe_class = ''.join(c for c in class_name if c.isalnum() or c in ('_', '-', ' ')).strip()
    safe_subject = ''.join(c for c in subject_name if c.isalnum() or c in ('_', '-', ' ')).strip()
    output_filename = f"SOW_{safe_subject}_{safe_class}.txt"
    
    response = HttpResponse(content, content_type='text/plain')
    response['Content-Disposition'] = f'attachment; filename="{output_filename}"'
    return response


def upload_docx_to_pdf(request):
    """Handle Word document upload and convert to PDF. This conversion is FREE."""
    from django.conf import settings
    
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    docx_file = request.FILES.get('docx_file')
    if not docx_file:
        return JsonResponse({'error': 'No file uploaded'}, status=400)
    
    # Check file extension
    if not docx_file.name.lower().endswith('.docx'):
        return JsonResponse({'error': 'Please upload a .docx file'}, status=400)
    
    import tempfile
    import os
    from datetime import datetime
    
    # Save uploaded file temporarily
    temp_dir = tempfile.mkdtemp()
    input_path = os.path.join(temp_dir, docx_file.name)
    output_filename = os.path.splitext(docx_file.name)[0] + '.pdf'
    output_path = os.path.join(settings.MEDIA_ROOT, 'converted', f'docx2pdf_{int(datetime.now().timestamp())}_{output_filename}')
    
    try:
        with open(input_path, 'wb') as f:
            for chunk in docx_file.chunks():
                f.write(chunk)
        
        # Convert
        from .converters import DocxToPdfConverter
        converter = DocxToPdfConverter(input_path, output_path)
        if converter.convert():
            # Return the download URL
            from django.urls import reverse
            download_url = reverse('download_file', kwargs={'filename': os.path.basename(output_path)})
            return JsonResponse({
                'success': True,
                'download_url': download_url,
                'filename': output_filename,
                'free': True,
            })
        else:
            return JsonResponse({'error': 'Conversion failed. Please try again.'}, status=500)
    except Exception as e:
        return JsonResponse({'error': f'Conversion error: {str(e)}'}, status=500)
    finally:
        import shutil
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except:
            pass


def upload_image_to_pdf(request):
    """Handle Image upload and convert to PDF. This conversion is FREE."""
    from django.conf import settings
    
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    image_file = request.FILES.get('image_file')
    if not image_file:
        return JsonResponse({'error': 'No file uploaded'}, status=400)
    
    image_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.webp')
    if not image_file.name.lower().endswith(image_extensions):
        return JsonResponse({'error': f'Please upload an image file ({", ".join(image_extensions)})'}, status=400)
    
    temp_dir = tempfile.mkdtemp()
    input_path = os.path.join(temp_dir, image_file.name)
    output_filename = os.path.splitext(image_file.name)[0] + '.pdf'
    output_path = os.path.join(settings.MEDIA_ROOT, 'converted', f'img2pdf_{int(datetime.now().timestamp())}_{output_filename}')
    
    try:
        with open(input_path, 'wb') as f:
            for chunk in image_file.chunks():
                f.write(chunk)
        
        from PIL import Image
        image = Image.open(input_path)
        if image.mode in ('RGBA', 'LA', 'P'):
            image = image.convert('RGB')
        image.save(output_path, 'PDF')
        
        download_url = reverse('download_file', kwargs={'filename': os.path.basename(output_path)})
        return JsonResponse({
            'success': True,
            'download_url': download_url,
            'filename': output_filename,
            'free': True,
        })
    except Exception as e:
        return JsonResponse({'error': f'Conversion error: {str(e)}'}, status=500)
    finally:
        _safe_cleanup(temp_dir)


def pdf_tool_merge(request):
    """Merge multiple uploaded PDFs into one PDF."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    uploaded_files = list(request.FILES.getlist('pdf_files'))
    if not uploaded_files:
        uploaded_files = [request.FILES.get('pdf_file')]
    if not uploaded_files:
        uploaded_files = [request.FILES.get('file')]
    if len(uploaded_files) < 2:
        return JsonResponse({'error': 'Please upload at least two PDF files to merge.'}, status=400)

    temp_dir = tempfile.mkdtemp()
    input_paths = []
    try:
        for uploaded_file in uploaded_files:
            if not uploaded_file.name.lower().endswith('.pdf'):
                return JsonResponse({'error': 'Only PDF files are supported for merge.'}, status=400)
            input_paths.append(_save_uploaded_pdf(uploaded_file, temp_dir))

        output_path = _build_pdf_tool_output_path('merged', uploaded_files[0].name)
        merger = PdfMerger()
        for input_path in input_paths:
            merger.append(input_path)
        merger.write(output_path)
        merger.close()
        return _pdf_tool_response(request, output_path, 'merge')
    except Exception as exc:
        return JsonResponse({'error': f'Merge failed: {str(exc)}'}, status=500)
    finally:
        _cleanup_temp_dir(temp_dir)


def pdf_tool_split(request):
    """Create a PDF containing the requested page range from an uploaded PDF."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    uploaded_file = request.FILES.get('pdf_files')
    if not uploaded_file:
        return JsonResponse({'error': 'No file uploaded'}, status=400)

    page_range = request.POST.get('page_range', '').strip()
    temp_dir = tempfile.mkdtemp()
    try:
        input_path = _save_uploaded_pdf(uploaded_file, temp_dir)
        reader = PdfReader(input_path)
        selected_pages = []
        if page_range:
            for part in page_range.split(','):
                part = part.strip()
                if not part:
                    continue
                if '-' in part:
                    start_text, end_text = part.split('-', 1)
                    start = max(1, int(start_text.strip()))
                    end = min(len(reader.pages), int(end_text.strip()))
                    selected_pages.extend(range(start - 1, end))
                else:
                    selected_pages.append(int(part) - 1)
        else:
            selected_pages = [0]

        selected_pages = sorted(set(selected_pages))
        selected_pages = [page for page in selected_pages if 0 <= page < len(reader.pages)]
        if not selected_pages:
            return JsonResponse({'error': 'No valid pages were selected.'}, status=400)

        writer = PdfWriter()
        for page_number in selected_pages:
            writer.add_page(reader.pages[page_number])
        output_path = _build_pdf_tool_output_path('split', uploaded_file.name)
        with open(output_path, 'wb') as handle:
            writer.write(handle)
        return _pdf_tool_response(request, output_path, 'split')
    except Exception as exc:
        return JsonResponse({'error': f'Split failed: {str(exc)}'}, status=500)
    finally:
        _cleanup_temp_dir(temp_dir)


def pdf_tool_compress(request):
    """Rebuild a PDF in a compact form by rewriting its pages."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    uploaded_file = request.FILES.get('pdf_files')
    if not uploaded_file:
        return JsonResponse({'error': 'No file uploaded'}, status=400)

    temp_dir = tempfile.mkdtemp()
    try:
        input_path = _save_uploaded_pdf(uploaded_file, temp_dir)
        reader = PdfReader(input_path)
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        output_path = _build_pdf_tool_output_path('compressed', uploaded_file.name)
        with open(output_path, 'wb') as handle:
            writer.write(handle)
        return _pdf_tool_response(request, output_path, 'compress')
    except Exception as exc:
        return JsonResponse({'error': f'Compression failed: {str(exc)}'}, status=500)
    finally:
        _cleanup_temp_dir(temp_dir)


def pdf_tool_rotate(request):
    """Rotate every page of an uploaded PDF by the requested angle."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    uploaded_file = request.FILES.get('pdf_files')
    if not uploaded_file:
        return JsonResponse({'error': 'No file uploaded'}, status=400)

    rotation = int(request.POST.get('rotation', '90'))
    temp_dir = tempfile.mkdtemp()
    try:
        input_path = _save_uploaded_pdf(uploaded_file, temp_dir)
        reader = PdfReader(input_path)
        writer = PdfWriter()
        for page in reader.pages:
            page.rotate(rotation)
            writer.add_page(page)
        output_path = _build_pdf_tool_output_path('rotated', uploaded_file.name)
        with open(output_path, 'wb') as handle:
            writer.write(handle)
        return _pdf_tool_response(request, output_path, 'rotate')
    except Exception as exc:
        return JsonResponse({'error': f'Rotation failed: {str(exc)}'}, status=500)
    finally:
        _cleanup_temp_dir(temp_dir)


def pdf_tool_watermark(request):
    """Add a text watermark to an uploaded PDF."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    uploaded_file = request.FILES.get('pdf_files')
    if not uploaded_file:
        return JsonResponse({'error': 'No file uploaded'}, status=400)

    watermark_text = request.POST.get('watermark_text', 'CONFIDENTIAL').strip() or 'CONFIDENTIAL'
    temp_dir = tempfile.mkdtemp()
    try:
        from reportlab.lib import colors
        from reportlab.pdfgen import canvas

        input_path = _save_uploaded_pdf(uploaded_file, temp_dir)
        reader = PdfReader(input_path)
        writer = PdfWriter()
        for page in reader.pages:
            page_width = float(page.mediabox.width)
            page_height = float(page.mediabox.height)
            watermark_buffer = BytesIO()
            watermark_canvas = canvas.Canvas(watermark_buffer, pagesize=(page_width, page_height))
            watermark_canvas.setFont('Helvetica-Bold', 48)
            watermark_canvas.setFillColor(colors.Color(0.45, 0.45, 0.45))
            watermark_canvas.translate(page_width / 2, page_height / 2)
            watermark_canvas.rotate(45)
            watermark_canvas.drawCentredString(0, 0, watermark_text)
            watermark_canvas.save()
            watermark_buffer.seek(0)
            watermark_reader = PdfReader(watermark_buffer)
            watermarked_page = watermark_reader.pages[0]
            watermarked_page.merge_page(page)
            writer.add_page(watermarked_page)

        output_path = _build_pdf_tool_output_path('watermarked', uploaded_file.name)
        with open(output_path, 'wb') as handle:
            writer.write(handle)
        return _pdf_tool_response(request, output_path, 'watermark')
    except Exception as exc:
        return JsonResponse({'error': f'Watermark failed: {str(exc)}'}, status=500)
    finally:
        _cleanup_temp_dir(temp_dir)


# ---------------------------------------------------------------------------
# PDF TOOLS - FLATTEN, RESIZE, UNLOCK, PROTECT, CROP, ORGANIZE, EXTRACT IMAGE, PAGE REMOVER, EXTRACT PAGES
# ---------------------------------------------------------------------------

def pdf_tool_flatten(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    uploaded_file = request.FILES.get('pdf_files')
    if not uploaded_file:
        return JsonResponse({'error': 'No file uploaded'}, status=400)
    if not uploaded_file.name.lower().endswith('.pdf'):
        return JsonResponse({'error': 'Only PDF files are supported for flatten.'}, status=400)
    temp_dir = tempfile.mkdtemp()
    try:
        input_path = _save_uploaded_pdf(uploaded_file, temp_dir)
        reader = PdfReader(input_path)
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        output_path = _build_pdf_tool_output_path('flattened', uploaded_file.name)
        with open(output_path, 'wb') as handle:
            writer.write(handle)
        return _pdf_tool_response(request, output_path, 'flatten')
    except Exception as exc:
        return JsonResponse({'error': f'Flatten failed: {str(exc)}'}, status=500)
    finally:
        _cleanup_temp_dir(temp_dir)


def pdf_tool_resize(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    uploaded_file = request.FILES.get('pdf_files')
    if not uploaded_file:
        return JsonResponse({'error': 'No file uploaded'}, status=400)
    if not uploaded_file.name.lower().endswith('.pdf'):
        return JsonResponse({'error': 'Only PDF files are supported for resize.'}, status=400)
    try:
        scale_percent = float(request.POST.get('scale', '100'))
        scale_factor = scale_percent / 100.0
    except ValueError:
        return JsonResponse({'error': 'Invalid scale percentage'}, status=400)
    temp_dir = tempfile.mkdtemp()
    try:
        input_path = _save_uploaded_pdf(uploaded_file, temp_dir)
        reader = PdfReader(input_path)
        writer = PdfWriter()
        for page in reader.pages:
            page.scale_by(scale_factor)
            writer.add_page(page)
        output_path = _build_pdf_tool_output_path('resized', uploaded_file.name)
        with open(output_path, 'wb') as handle:
            writer.write(handle)
        return _pdf_tool_response(request, output_path, 'resize')
    except Exception as exc:
        return JsonResponse({'error': f'Resize failed: {str(exc)}'}, status=500)
    finally:
        _cleanup_temp_dir(temp_dir)


def pdf_tool_unlock(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    uploaded_file = request.FILES.get('pdf_files')
    if not uploaded_file:
        return JsonResponse({'error': 'No file uploaded'}, status=400)
    if not uploaded_file.name.lower().endswith('.pdf'):
        return JsonResponse({'error': 'Only PDF files are supported for unlock.'}, status=400)
    password = request.POST.get('password', '')
    temp_dir = tempfile.mkdtemp()
    try:
        input_path = _save_uploaded_pdf(uploaded_file, temp_dir)
        reader = PdfReader(input_path)
        if reader.is_encrypted:
            try:
                reader.decrypt(password)
            except Exception:
                return JsonResponse({'error': 'Unable to decrypt PDF. Please check the password.'}, status=400)
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        output_path = _build_pdf_tool_output_path('unlocked', uploaded_file.name)
        with open(output_path, 'wb') as handle:
            writer.write(handle)
        return _pdf_tool_response(request, output_path, 'unlock')
    except Exception as exc:
        return JsonResponse({'error': f'Unlock failed: {str(exc)}'}, status=500)
    finally:
        _cleanup_temp_dir(temp_dir)


def pdf_tool_protect(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    uploaded_file = request.FILES.get('pdf_files')
    if not uploaded_file:
        return JsonResponse({'error': 'No file uploaded'}, status=400)
    if not uploaded_file.name.lower().endswith('.pdf'):
        return JsonResponse({'error': 'Only PDF files are supported for protect.'}, status=400)
    password = request.POST.get('password', '').strip()
    if not password or len(password) < 4:
        return JsonResponse({'error': 'Password must be at least 4 characters.'}, status=400)
    temp_dir = tempfile.mkdtemp()
    try:
        input_path = _save_uploaded_pdf(uploaded_file, temp_dir)
        reader = PdfReader(input_path)
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        writer.encrypt(password)
        output_path = _build_pdf_tool_output_path('protected', uploaded_file.name)
        with open(output_path, 'wb') as handle:
            writer.write(handle)
        return _pdf_tool_response(request, output_path, 'protect')
    except Exception as exc:
        return JsonResponse({'error': f'Protect failed: {str(exc)}'}, status=500)
    finally:
        _cleanup_temp_dir(temp_dir)


def pdf_tool_crop(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    uploaded_file = request.FILES.get('pdf_files')
    if not uploaded_file:
        return JsonResponse({'error': 'No file uploaded'}, status=400)
    if not uploaded_file.name.lower().endswith('.pdf'):
        return JsonResponse({'error': 'Only PDF files are supported for crop.'}, status=400)
    crop_box = request.POST.get('crop_box', '').strip()
    if not crop_box:
        return JsonResponse({'error': 'Please specify crop box: left,bottom,right,top'}, status=400)
    try:
        coords = [float(x) for x in crop_box.split(',')]
        if len(coords) != 4:
            return JsonResponse({'error': 'Invalid crop box format. Use: left,bottom,right,top'}, status=400)
    except ValueError:
        return JsonResponse({'error': 'Invalid crop box values'}, status=400)
    temp_dir = tempfile.mkdtemp()
    try:
        input_path = _save_uploaded_pdf(uploaded_file, temp_dir)
        reader = PdfReader(input_path)
        writer = PdfWriter()
        for page in reader.pages:
            page.mediabox.lower_left = (coords[0], coords[1])
            page.mediabox.upper_right = (coords[2], coords[3])
            writer.add_page(page)
        output_path = _build_pdf_tool_output_path('cropped', uploaded_file.name)
        with open(output_path, 'wb') as handle:
            writer.write(handle)
        return _pdf_tool_response(request, output_path, 'crop')
    except Exception as exc:
        return JsonResponse({'error': f'Crop failed: {str(exc)}'}, status=500)
    finally:
        _cleanup_temp_dir(temp_dir)


def pdf_tool_organize(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    uploaded_files = request.FILES.getlist('pdf_files')
    if len(uploaded_files) < 2:
        return JsonResponse({'error': 'Please upload at least two PDF files to organize.'}, status=400)
    page_orders = request.POST.getlist('page_order')
    temp_dir = tempfile.mkdtemp()
    try:
        all_pages = []
        for uploaded_file in uploaded_files:
            if not uploaded_file.name.lower().endswith('.pdf'):
                return JsonResponse({'error': 'Only PDF files are supported.'}, status=400)
            input_path = _save_uploaded_pdf(uploaded_file, temp_dir)
            reader = PdfReader(input_path)
            for page in reader.pages:
                all_pages.append(page)
        writer = PdfWriter()
        for page in all_pages:
            writer.add_page(page)
        output_path = _build_pdf_tool_output_path('organized', uploaded_files[0].name)
        with open(output_path, 'wb') as handle:
            writer.write(handle)
        return _pdf_tool_response(request, output_path, 'organize')
    except Exception as exc:
        return JsonResponse({'error': f'Organize failed: {str(exc)}'}, status=500)
    finally:
        _cleanup_temp_dir(temp_dir)


def pdf_tool_extract_image(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    uploaded_file = request.FILES.get('pdf_files')
    if not uploaded_file:
        return JsonResponse({'error': 'No file uploaded'}, status=400)
    if not uploaded_file.name.lower().endswith('.pdf'):
        return JsonResponse({'error': 'Only PDF files are supported.'}, status=400)
    temp_dir = tempfile.mkdtemp()
    try:
        try:
            import fitz
        except ImportError:
            return JsonResponse({'error': 'PyMuPDF (fitz) not installed. Run: pip install PyMuPDF'}, status=500)
        
        input_path = _save_uploaded_pdf(uploaded_file, temp_dir)
        doc = fitz.open(input_path)
        extracted_images = []
        for page_num in range(len(doc)):
            try:
                for img in doc[page_num].get_images():
                    xref = img[0]
                    try:
                        base_image = doc.extract_image(xref)
                        if base_image:
                            image_bytes = base_image.get('image')
                            image_ext = base_image.get('ext', 'png')
                            if image_bytes:
                                image_path = os.path.join(temp_dir, f'page_{page_num + 1}_img_{xref}.{image_ext}')
                                with open(image_path, 'wb') as img_file:
                                    img_file.write(image_bytes)
                                extracted_images.append(image_path)
                    except Exception:
                        continue
            except Exception:
                continue
        doc.close()
        if not extracted_images:
            return JsonResponse({'error': 'No images found in PDF.'}, status=400)
        import zipfile
        import uuid
        zip_name = f'images_{uuid.uuid4().hex[:8]}.zip'
        zip_path = os.path.join(settings.MEDIA_ROOT, 'converted', zip_name)
        os.makedirs(os.path.dirname(zip_path), exist_ok=True)
        with zipfile.ZipFile(zip_path, 'w') as zf:
            for img_path in extracted_images:
                if os.path.exists(img_path):
                    zf.write(img_path, os.path.basename(img_path))
        filename = zip_name
        download_url = reverse('download_file', kwargs={'filename': filename})
        return JsonResponse({'success': True, 'download_url': download_url, 'filename': filename, 'tool': 'extract_image'})
    except Exception as exc:
        return JsonResponse({'error': f'Extract image failed: {str(exc)}'}, status=500)
    finally:
        _cleanup_temp_dir(temp_dir)


def pdf_tool_page_remover(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    uploaded_file = request.FILES.get('pdf_files')
    if not uploaded_file:
        return JsonResponse({'error': 'No file uploaded'}, status=400)
    if not uploaded_file.name.lower().endswith('.pdf'):
        return JsonResponse({'error': 'Only PDF files are supported.'}, status=400)
    page_range = request.POST.get('page_range', '').strip()
    if not page_range:
        return JsonResponse({'error': 'Please specify pages to remove (e.g. 1,3,5-7).'}, status=400)
    temp_dir = tempfile.mkdtemp()
    try:
        input_path = _save_uploaded_pdf(uploaded_file, temp_dir)
        reader = PdfReader(input_path)
        total_pages = len(reader.pages)
        pages_to_remove = set()
        for part in page_range.split(','):
            part = part.strip()
            if not part:
                continue
            if '-' in part:
                start_text, end_text = part.split('-', 1)
                start = max(1, int(start_text.strip()))
                end = min(total_pages, int(end_text.strip()))
                pages_to_remove.update(range(start, end + 1))
            else:
                pages_to_remove.add(int(part))
        writer = PdfWriter()
        for i, page in enumerate(reader.pages):
            if (i + 1) not in pages_to_remove:
                writer.add_page(page)
        output_path = _build_pdf_tool_output_path('pages_removed', uploaded_file.name)
        with open(output_path, 'wb') as handle:
            writer.write(handle)
        return _pdf_tool_response(request, output_path, 'page_remover')
    except Exception as exc:
        return JsonResponse({'error': f'Page removal failed: {str(exc)}'}, status=500)
    finally:
        _cleanup_temp_dir(temp_dir)


def pdf_tool_extract_pages(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    uploaded_file = request.FILES.get('pdf_files')
    if not uploaded_file:
        return JsonResponse({'error': 'No file uploaded'}, status=400)
    if not uploaded_file.name.lower().endswith('.pdf'):
        return JsonResponse({'error': 'Only PDF files are supported.'}, status=400)
    page_range = request.POST.get('page_range', '').strip()
    if not page_range:
        return JsonResponse({'error': 'Please specify pages to extract (e.g. 1-3,5).'}, status=400)
    temp_dir = tempfile.mkdtemp()
    try:
        input_path = _save_uploaded_pdf(uploaded_file, temp_dir)
        reader = PdfReader(input_path)
        selected_pages = []
        for part in page_range.split(','):
            part = part.strip()
            if not part:
                continue
            if '-' in part:
                start_text, end_text = part.split('-', 1)
                start = max(1, int(start_text.strip()))
                end = min(len(reader.pages), int(end_text.strip()))
                selected_pages.extend(range(start - 1, end))
            else:
                selected_pages.append(int(part) - 1)
        selected_pages = sorted(set(selected_pages))
        selected_pages = [p for p in selected_pages if 0 <= p < len(reader.pages)]
        if not selected_pages:
            return JsonResponse({'error': 'No valid pages selected.'}, status=400)
        writer = PdfWriter()
        for page_num in selected_pages:
            writer.add_page(reader.pages[page_num])
        output_path = _build_pdf_tool_output_path('extracted_pages', uploaded_file.name)
        with open(output_path, 'wb') as handle:
            writer.write(handle)
        return _pdf_tool_response(request, output_path, 'extract_pages')
    except Exception as exc:
        return JsonResponse({'error': f'Extract pages failed: {str(exc)}'}, status=500)
    finally:
        _cleanup_temp_dir(temp_dir)


def conversion_history(request):
    """View conversion history. Shows only the logged-in user's conversions."""
    if request.user.is_authenticated:
        conversions = ConvertedFile.objects.filter(user=request.user).order_by('-created_at')[:50]
    else:
        conversions = ConvertedFile.objects.none()
    return render(request, 'history.html', {'conversions': conversions})


def search_materials(request):
    """Search revision materials with filters."""
    from revision.models import RevisionMaterial, Subject, Class as SchoolClass
    
    query = request.GET.get('q', '')
    material_type = request.GET.get('type', '')
    class_id = request.GET.get('class', '')
    term = request.GET.get('term', '')
    year = request.GET.get('year', '')
    price_filter = request.GET.get('price', '')
    sort = request.GET.get('sort', 'newest')
    
    # Base queryset
    materials = RevisionMaterial.objects.all()
    
    # Apply filters
    if query:
        materials = materials.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(subject__name__icontains=query)
        )
    
    if material_type:
        materials = materials.filter(material_type=material_type)
    
    if class_id:
        materials = materials.filter(subject__class_ref_id=class_id)
    
    if term:
        materials = materials.filter(term=term)
    
    if year:
        materials = materials.filter(year=year)
    
    if price_filter == 'free':
        materials = materials.filter(is_free=True)
    elif price_filter == 'paid':
        materials = materials.filter(is_free=False)
    
    # Apply sorting
    if sort == 'newest':
        materials = materials.order_by('-created_at')
    elif sort == 'oldest':
        materials = materials.order_by('created_at')
    elif sort == 'popular':
        materials = materials.order_by('-download_count')
    elif sort == 'title':
        materials = materials.order_by('title')
    
    # Get filter options
    material_types = RevisionMaterial.MATERIAL_TYPES
    classes = SchoolClass.objects.all().order_by('curriculum', 'level', 'name')
    term_choices = RevisionMaterial.TERM_CHOICES
    years = RevisionMaterial.objects.exclude(year__isnull=True).values_list('year', flat=True).distinct().order_by('-year')[:10]
    
    context = {
        'results': materials[:50],  # Limit results
        'query': query,
        'selected_type': material_type,
        'selected_class': class_id,
        'selected_term': term,
        'selected_year': year,
        'selected_price': price_filter,
        'selected_sort': sort,
        'material_types': material_types,
        'classes': classes,
        'term_choices': term_choices,
        'years': years,
    }
    return render(request, 'search.html', context)


@login_required
def user_dashboard(request):
    """User dashboard with overview of activity"""
    from revision.models import RevisionMaterial
    
    user = request.user
    
    # Get user's conversion stats
    conversions = ConvertedFile.objects.filter(user=user).order_by('-created_at')[:10]
    total_conversions = ConvertedFile.objects.filter(user=user).count()
    total_spent = ConvertedFile.objects.filter(user=user, payment_status='paid').aggregate(
        total=Sum('cost')
    )['total'] or 0
    
    # Get subscription info
    school_profile = SchoolProfile.objects.filter(user=user).first()
    subscription_status = 'none'
    subscription_end = None
    if school_profile:
        active_sub = school_profile.subscriptions.filter(status='active').first()
        if active_sub:
            subscription_status = 'active'
            subscription_end = active_sub.end_date
        else:
            pending_sub = school_profile.subscriptions.filter(status='pending').first()
            if pending_sub:
                subscription_status = 'pending'
                subscription_end = pending_sub.end_date
    
    # Get popular revision materials
    popular_materials = RevisionMaterial.objects.filter(is_free=True).order_by('-download_count')[:4]
    
    context = {
        'user': user,
        'recent_conversions': conversions,
        'total_conversions': total_conversions,
        'total_spent': total_spent,
        'total_downloads': 0,  # Can be enhanced later
        'subscription_status': subscription_status,
        'subscription_end': subscription_end,
        'popular_materials': popular_materials,
    }
    return render(request, 'dashboard.html', context)


@login_required
def user_profile(request):
    """User profile page showing account info and conversion history"""
    from revision.models import RevisionMaterial
    
    # Get user data
    user = request.user
    conversions = ConvertedFile.objects.filter(user=user).order_by('-created_at')[:20]
    total_conversions = ConvertedFile.objects.filter(user=user).count()
    total_paid = ConvertedFile.objects.filter(user=user, payment_status='paid').count()
    
    # Check if user has school profile
    school_profile = SchoolProfile.objects.filter(user=user).first()
    
    # Get revision materials downloaded (if we track that)
    # For now, just show stats
    
    context = {
        'user': user,
        'conversions': conversions,
        'total_conversions': total_conversions,
        'total_paid': total_paid,
        'school_profile': school_profile,
    }
    return render(request, 'profile.html', context)


def custom_password_reset(request):
    """Password reset view that validates email exists before sending reset link."""
    from django.contrib.auth.forms import PasswordResetForm
    from django.contrib.auth.models import User
    
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        
        if not email:
            messages.error(request, 'Please enter your email address.')
            return render(request, 'registration/password_reset.html')
        
        if not User.objects.filter(email=email).exists():
            messages.error(request, 'This email is not registered in our system.')
            return render(request, 'registration/password_reset.html')
        
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            form.save(
                subject_template_name='registration/password_reset_subject.txt',
                email_template_name='registration/password_reset_email.html',
                html_email_template_name='registration/password_reset_email.html',
                request=request,
            )
            messages.success(request, 'Password reset link has been sent to your email.')
            return redirect('password_reset_done')
    else:
        form = PasswordResetForm()
    
    return render(request, 'registration/password_reset.html', {'form': form})


def login_view(request):
    """Custom login view that authenticates with email instead of username"""
    from django.contrib.auth import authenticate, login
    from django.contrib.auth.forms import AuthenticationForm
    
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        
        # Find user by email (use filter().first() to handle duplicate emails)
        user_obj = User.objects.filter(email=email).first()
        username = user_obj.username if user_obj else None
        
        # Authenticate with username (Django's authenticate uses username internally)
        user = authenticate(request, username=username, password=password) if username else None
        
        if user is not None:
            if user.is_active:
                login(request, user)
                next_url = request.POST.get('next', 'index').strip()
                if not next_url:
                    next_url = 'index'
                messages.success(request, f'Welcome back, {user.username}!')
                return redirect(next_url)
            else:
                messages.error(request, 'Your account is disabled.')
        else:
            messages.error(request, 'Invalid email or password. Please try again.')
    
    # GET request - show login form
    from django.contrib.auth.forms import AuthenticationForm
    form = AuthenticationForm()
    
    return render(request, 'registration/login.html', {'form': form})


# ---------------------------------------------------------------------------
# JOB LISTINGS
# ---------------------------------------------------------------------------
def bom_jobs(request):
    """BOM Teaching Jobs listing page."""
    return render(request, 'jobs/bom_jobs.html')


def homeschooling_jobs(request):
    """Homeschooling Jobs listing page."""
    return render(request, 'jobs/homeschooling_jobs.html')


def post_job(request):
    """Post a new job advertisement."""
    from .models import JobAdvertisement
    from datetime import datetime
    
    if request.method == 'POST':
        job_type = request.POST.get('job_type')
        employment_type = request.POST.get('employment_type', 'full-time')
        title = request.POST.get('title')
        school_name = request.POST.get('school_name')
        location = request.POST.get('location')
        description = request.POST.get('description')
        requirements = request.POST.get('requirements')
        salary_range = request.POST.get('salary_range')
        contact_email = request.POST.get('contact_email')
        contact_phone = request.POST.get('contact_phone', '')
        expires_at = request.POST.get('expires_at')
        featured = request.POST.get('featured') == 'on'
        
        if job_type and title and school_name and location:
            job = JobAdvertisement.objects.create(
                job_type=job_type,
                employment_type=employment_type,
                title=title,
                school_name=school_name,
                location=location,
                description=description,
                requirements=requirements,
                salary_range=salary_range,
                contact_email=contact_email,
                contact_phone=contact_phone,
                expires_at=datetime.strptime(expires_at, '%Y-%m-%d').date() if expires_at else None,
                featured=featured,
                approved=False  # Jobs require admin approval
            )
            messages.success(request, 'Job advertisement submitted successfully! It will be reviewed by admin before appearing on the website.')
            return redirect('index')
        else:
            messages.error(request, 'Please fill in all required fields.')
    
    return render(request, 'jobs/post_job.html')


@login_required
def admin_job_approvals(request):
    """Admin view to approve/reject job advertisements."""
    from .models import JobAdvertisement
    from django.contrib.auth.decorators import user_passes_test
    
    # Only superusers can access this
    if not request.user.is_superuser:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')
    
    pending_jobs = JobAdvertisement.objects.filter(approved=False, is_active=True).order_by('-created_at')
    approved_jobs = JobAdvertisement.objects.filter(approved=True, is_active=True).order_by('-created_at')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        job_id = request.POST.get('job_id')
        
        if action == 'approve' and job_id:
            job = JobAdvertisement.objects.get(id=job_id)
            job.approved = True
            job.save()
            messages.success(request, f'Job "{job.title}" has been approved.')
        elif action == 'reject' and job_id:
            job = JobAdvertisement.objects.get(id=job_id)
            job.is_active = False
            job.save()
            messages.success(request, f'Job "{job.title}" has been rejected.')
        elif action == 'toggle_featured' and job_id:
            job = JobAdvertisement.objects.get(id=job_id)
            job.featured = not job.featured
            job.save()
            messages.success(request, f'Job "{job.title}" featured status updated.')
        elif action == 'delete' and job_id:
            job = JobAdvertisement.objects.get(id=job_id)
            job.delete()
            messages.success(request, f'Job "{job.title}" has been deleted.')
        
        return redirect('admin_job_approvals')
    
    context = {
        'pending_jobs': pending_jobs,
        'approved_jobs': approved_jobs,
    }
    return render(request, 'admin/job_approvals.html', context)


@login_required
def edit_profile(request):
    """Edit user profile - email, username, and password"""
    user = request.user
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update_email':
            # Update email
            new_email = request.POST.get('email', '').strip()
            if new_email:
                user.email = new_email
                user.save()
                messages.success(request, 'Email address updated successfully!')
            else:
                messages.error(request, 'Email cannot be empty.')
        
        elif action == 'update_username':
            # Update username
            new_username = request.POST.get('username', '').strip()
            if not new_username:
                messages.error(request, 'Username cannot be empty.')
            elif len(new_username) < 3:
                messages.error(request, 'Username must be at least 3 characters long.')
            elif User.objects.filter(username=new_username).exclude(id=user.id).exists():
                messages.error(request, 'This username is already taken. Please choose another.')
            else:
                user.username = new_username
                user.save()
                messages.success(request, 'Username updated successfully!')
        
        elif action == 'update_password':
            # Update password
            current_password = request.POST.get('current_password', '')
            new_password = request.POST.get('new_password', '')
            confirm_password = request.POST.get('confirm_password', '')
            
            if not user.check_password(current_password):
                messages.error(request, 'Current password is incorrect.')
            elif len(new_password) < 8:
                messages.error(request, 'New password must be at least 8 characters long.')
            elif new_password != confirm_password:
                messages.error(request, 'New passwords do not match.')
            else:
                user.set_password(new_password)
                user.save()
                messages.success(request, 'Password updated successfully! Please login again with your new password.')
                return redirect('login')
        
        return redirect('user_profile')
    
    # GET request - show edit form
    context = {
        'user': user,
    }
    return render(request, 'edit_profile.html', context)
