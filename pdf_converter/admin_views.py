from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta
from django.contrib import messages
from .models import ConvertedFile, Payment, SubscriptionPlan, SchoolSubscription, SchoolProfile, PaymentSettings
from revision.models import Subject, RevisionMaterial
from .forms import SubscriptionPlanForm
from .payment_utils import is_free_period, get_payment_settings


def is_staff(user):
    return user.is_authenticated and user.is_staff


def staff_login_required(view_func):
    """Decorator that always redirects to login if user is not staff"""
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f'/accounts/login/?next={request.path}')
        if not request.user.is_staff:
            return redirect(f'/accounts/login/?next={request.path}')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


@staff_login_required
def admin_dashboard(request):
    """Custom admin dashboard with analytics"""
    
    # Date ranges
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    # Overall statistics - Conversions
    total_conversions = ConvertedFile.objects.count()
    total_payments = Payment.objects.filter(status='completed').count()
    total_revenue = Payment.objects.filter(status='completed').aggregate(
        total=Sum('amount')
    )['total'] or 0
    
    # Revision materials statistics
    total_subjects = Subject.objects.count()
    total_materials = RevisionMaterial.objects.count()
    total_downloads = RevisionMaterial.objects.aggregate(
        total=Sum('download_count')
    )['total'] or 0
    free_materials = RevisionMaterial.objects.filter(is_free=True).count()
    paid_materials = RevisionMaterial.objects.filter(is_free=False).count()
    
    # Recent conversions
    recent_conversions = ConvertedFile.objects.all().order_by('-created_at')[:10]
    
    # Recent payments
    recent_payments = Payment.objects.filter(status='completed').order_by('-created_at')[:10]
    
    # Daily stats for the last 7 days
    daily_stats = []
    for i in range(7):
        date = today - timedelta(days=i)
        day_conversions = ConvertedFile.objects.filter(created_at__date=date).count()
        day_payments = Payment.objects.filter(
            created_at__date=date, 
            status='completed'
        ).count()
        day_revenue = Payment.objects.filter(
            created_at__date=date, 
            status='completed'
        ).aggregate(total=Sum('amount'))['total'] or 0
        daily_stats.append({
            'date': date,
            'conversions': day_conversions,
            'payments': day_payments,
            'revenue': day_revenue
        })
    daily_stats.reverse()
    
    # Payment status breakdown
    payment_status_counts = {
        'completed': Payment.objects.filter(status='completed').count(),
        'pending': Payment.objects.filter(status='pending').count(),
        'failed': Payment.objects.filter(status='failed').count(),
        'cancelled': Payment.objects.filter(status='cancelled').count(),
    }
    
    # Conversion status breakdown
    conversion_status_counts = {
        'completed': ConvertedFile.objects.filter(status='completed').count(),
        'processing': ConvertedFile.objects.filter(status='processing').count(),
        'failed': ConvertedFile.objects.filter(status='failed').count(),
        'pending': ConvertedFile.objects.filter(status='pending').count(),
    }
    
    # Top customers by payment amount
    top_customers = Payment.objects.filter(status='completed').values(
        'phone_number'
    ).annotate(
        total_paid=Sum('amount'),
        payment_count=Count('id')
    ).order_by('-total_paid')[:5]
    
    # Pending payments requiring attention
    pending_payments = Payment.objects.filter(status='pending').order_by('-created_at')[:10]
    
    # Failed conversions
    failed_conversions = ConvertedFile.objects.filter(status='failed').order_by('-created_at')[:10]
    
    # Revision materials by curriculum
    cbe_subjects = Subject.objects.filter(class_ref__curriculum='cbe').count()
    eight_four_subjects = Subject.objects.filter(class_ref__curriculum='844').count()
    
    # Most downloaded materials
    top_materials = RevisionMaterial.objects.all().order_by('-download_count')[:5]
    
    # Recent materials
    recent_materials = RevisionMaterial.objects.all().order_by('-created_at')[:5]
    
    # Format distribution
    format_distribution = ConvertedFile.objects.values('output_format').annotate(
        count=Count('id')
    ).order_by('-count')
    total_conversions_count = ConvertedFile.objects.count()
    for fmt in format_distribution:
        fmt['percentage'] = (fmt['count'] / total_conversions_count * 100) if total_conversions_count > 0 else 0
    
    # Average pages per conversion
    avg_pages = ConvertedFile.objects.aggregate(
        avg=Sum('page_count') / Count('id')
    )['avg'] or 0
    
    # Total file size processed (calculated in Python since FileField doesn't support aggregation)
    total_file_size = 0
    for conv in ConvertedFile.objects.all():
        if conv.original_pdf:
            try:
                total_file_size += conv.original_pdf.size
            except FileNotFoundError:
                # File was deleted from disk but record exists in DB
                pass
            except Exception:
                pass
    
    # Success rate
    total_attempts = ConvertedFile.objects.count()
    successful_conversions = ConvertedFile.objects.filter(status='completed').count()
    success_rate = (successful_conversions / total_attempts * 100) if total_attempts > 0 else 0
    
    # Average revenue per conversion
    avg_revenue = (total_revenue / total_payments) if total_payments > 0 else 0
    
    # User statistics
    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    staff_users = User.objects.filter(is_staff=True).count()
    recent_users = User.objects.all().order_by('-date_joined')[:5]
    
    # School subscription statistics
    total_schools = SchoolProfile.objects.count()
    active_subscriptions = SchoolSubscription.objects.filter(status='active').count()
    expired_subscriptions = SchoolSubscription.objects.filter(status='expired').count()
    recent_schools = SchoolProfile.objects.all().order_by('-registered_at')[:5]
    
    # System health metrics
    processing_conversions = ConvertedFile.objects.filter(status='processing').count()
    pending_payments_count = Payment.objects.filter(status='pending').count()
    system_health_score = 100 - (failed_conversions.count() * 2) - (pending_payments_count * 1)
    system_health_score = max(0, min(100, system_health_score))
    
    context = {
        'total_conversions': total_conversions,
        'total_payments': total_payments,
        'total_revenue': total_revenue,
        'recent_conversions': recent_conversions,
        'recent_payments': recent_payments,
        'daily_stats': daily_stats,
        'payment_status_counts': payment_status_counts,
        'conversion_status_counts': conversion_status_counts,
        'top_customers': top_customers,
        'pending_payments': pending_payments,
        'failed_conversions': failed_conversions,
        # Revision materials stats
        'total_subjects': total_subjects,
        'total_materials': total_materials,
        'total_downloads': total_downloads,
        'free_materials': free_materials,
        'paid_materials': paid_materials,
        'cbe_subjects': cbe_subjects,
        'eight_four_subjects': eight_four_subjects,
        'top_materials': top_materials,
        'recent_materials': recent_materials,
        # Additional stats
        'format_distribution': format_distribution,
        'avg_pages': avg_pages,
        'total_file_size': total_file_size,
        'success_rate': success_rate,
        # User stats
        'total_users': total_users,
        'active_users': active_users,
        'staff_users': staff_users,
        'recent_users': recent_users,
        # School subscription stats
        'total_schools': total_schools,
        'active_subscriptions': active_subscriptions,
        'expired_subscriptions': expired_subscriptions,
        'recent_schools': recent_schools,
        # System health
        'processing_conversions': processing_conversions,
        'pending_payments_count': pending_payments_count,
        'system_health_score': system_health_score,
        # Payment settings
        'payment_settings': get_payment_settings(),
        'is_free_period': is_free_period(),
    }
    
    return render(request, 'admin/dashboard.html', context)


# ---------------------------------------------------------------------------
# SUBSCRIPTION PLAN MANAGEMENT (Admin)
# ---------------------------------------------------------------------------
@staff_login_required
def admin_plans_list(request):
    """List all subscription plans."""
    plans = SubscriptionPlan.objects.all().order_by('amount')
    return render(request, 'admin/plans/list.html', {'plans': plans})


@staff_login_required
def admin_plan_add(request):
    """Add a new subscription plan."""
    if request.method == 'POST':
        form = SubscriptionPlanForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Subscription plan created successfully!')
            return redirect('admin_plans_list')
    else:
        form = SubscriptionPlanForm()
    return render(request, 'admin/plans/form.html', {'form': form, 'title': 'Add Subscription Plan'})


@staff_login_required
def admin_plan_edit(request, plan_id):
    """Edit an existing subscription plan."""
    plan = get_object_or_404(SubscriptionPlan, id=plan_id)
    if request.method == 'POST':
        form = SubscriptionPlanForm(request.POST, instance=plan)
        if form.is_valid():
            form.save()
            messages.success(request, f'Plan "{plan.name}" updated successfully!')
            return redirect('admin_plans_list')
    else:
        form = SubscriptionPlanForm(instance=plan)
    return render(request, 'admin/plans/form.html', {'form': form, 'plan': plan, 'title': f'Edit Plan: {plan.name}'})


@staff_login_required
def admin_plan_delete(request, plan_id):
    """Delete a subscription plan."""
    plan = get_object_or_404(SubscriptionPlan, id=plan_id)
    if request.method == 'POST':
        name = plan.name
        plan.delete()
        messages.success(request, f'Plan "{name}" deleted successfully!')
        return redirect('admin_plans_list')
    return render(request, 'admin/plans/delete.html', {'plan': plan})


@staff_login_required
def admin_plan_toggle(request, plan_id):
    """Toggle plan active/inactive status."""
    plan = get_object_or_404(SubscriptionPlan, id=plan_id)
    plan.is_active = not plan.is_active
    plan.save()
    status = "activated" if plan.is_active else "deactivated"
    messages.success(request, f'Plan "{plan.name}" {status} successfully!')
    return redirect('admin_plans_list')


@staff_login_required
def toggle_free_period(request):
    """Toggle the global free period on/off."""
    if request.method != 'POST':
        return redirect('admin_dashboard')
    
    settings_obj = get_payment_settings()
    settings_obj.is_free_period = not settings_obj.is_free_period
    settings_obj.save()
    
    status = "enabled" if settings_obj.is_free_period else "disabled"
    messages.success(request, f'Free period has been {status}. All conversions and revision materials are now {"free" if settings_obj.is_free_period else "paid"}.')
    return redirect('admin_dashboard')


@staff_login_required
def admin_payment_settings(request):
    """Admin payment settings page integrated into Django admin area."""
    settings_obj = get_payment_settings()
    
    if request.method == 'POST':
        settings_obj.conversion_cost_per_page = request.POST.get('conversion_cost_per_page', settings_obj.conversion_cost_per_page)
        settings_obj.global_revision_price = request.POST.get('global_revision_price', settings_obj.global_revision_price)
        
        free_period = request.POST.get('is_free_period')
        settings_obj.is_free_period = free_period == 'on'
        
        free_start = request.POST.get('free_period_start')
        free_end = request.POST.get('free_period_end')
        settings_obj.free_period_start = free_start if free_start else None
        settings_obj.free_period_end = free_end if free_end else None
        
        settings_obj.save()
        messages.success(request, 'Payment settings updated successfully!')
        return redirect('admin_payment_settings')
    
    return render(request, 'admin/payment_settings.html', {
        'payment_settings': settings_obj,
        'is_free_period': settings_obj.is_free_period,
    })
