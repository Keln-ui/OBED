"""
URL configuration for word_converter project.
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
import pdf_converter.views
from pdf_converter.views import subscription_required, custom_password_reset, password_reset_done, password_reset_confirm, password_reset_complete
from pdf_converter import admin_views

urlpatterns = [
    # Custom admin routes MUST come before the admin catch-all
    path('admin/plans/', admin_views.admin_plans_list, name='admin_plans_list'),
    path('admin/plans/add/', admin_views.admin_plan_add, name='admin_plan_add'),
    path('admin/plans/edit/<int:plan_id>/', admin_views.admin_plan_edit, name='admin_plan_edit'),
    path('admin/plans/delete/<int:plan_id>/', admin_views.admin_plan_delete, name='admin_plan_delete'),
    path('admin/plans/toggle/<int:plan_id>/', admin_views.admin_plan_toggle, name='admin_plan_toggle'),
    path('admin/payment-settings/', admin_views.admin_payment_settings, name='admin_payment_settings'),
    path('admin/dashboard/', admin_views.admin_dashboard, name='admin_dashboard_custom'),
    path('admin/', admin.site.urls),
    # Django Allauth URLs (social authentication) - must come before custom login
    path('accounts/', include('allauth.urls')),
    # Custom password reset override
    path('accounts/password_reset/', custom_password_reset, name='password_reset'),
    path('accounts/password_reset/done/', password_reset_done, name='password_reset_done'),
    path('accounts/reset/<uidb64>/<token>/', password_reset_confirm, name='password_reset_confirm'),
    path('accounts/reset/done/', password_reset_complete, name='password_reset_complete'),
    # Custom login view override
    path('accounts/login/', pdf_converter.views.login_view, name='account_login'),
    path('', include('pdf_converter.urls')),
    path('payment/', include('pdf_converter.payment_urls')),
    path('revision/', include('revision.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)