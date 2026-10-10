from django.urls import path
from . import views
from . import admin_views

urlpatterns = [
    path('', views.index, name='index'),
    path('upload/', views.upload_pdf, name='upload_pdf'),
    path('pdf-tools/merge/', views.pdf_tool_merge, name='pdf_tool_merge'),
    path('pdf-tools/split/', views.pdf_tool_split, name='pdf_tool_split'),
    path('pdf-tools/compress/', views.pdf_tool_compress, name='pdf_tool_compress'),
    path('pdf-tools/rotate/', views.pdf_tool_rotate, name='pdf_tool_rotate'),
    path('pdf-tools/watermark/', views.pdf_tool_watermark, name='pdf_tool_watermark'),
    path('upload-docx-to-pdf/', views.upload_docx_to_pdf, name='upload_docx_to_pdf'),
    path('upload-image-to-pdf/', views.upload_image_to_pdf, name='upload_image_to_pdf'),
    path('download/<str:filename>/', views.download_file, name='download_file'),
    path('history/', views.conversion_history, name='conversion_history'),
    path('search/', views.search_materials, name='search_materials'),
    path('admin-dashboard/', admin_views.admin_dashboard, name='admin_dashboard'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Scheme of Work Generator (standalone, not tied to revision)
    path('sow-generator/', views.sow_generator, name='sow_generator'),
    path('sow-preview/', views.sow_preview, name='sow_preview'),
    path('generate-sow/', views.generate_sow_download, name='generate_sow_download'),

    # PDF Tools
    path('pdf-tools/flatten/', views.pdf_tool_flatten, name='pdf_tool_flatten'),
    path('pdf-tools/resize/', views.pdf_tool_resize, name='pdf_tool_resize'),
    path('pdf-tools/unlock/', views.pdf_tool_unlock, name='pdf_tool_unlock'),
    path('pdf-tools/protect/', views.pdf_tool_protect, name='pdf_tool_protect'),
    path('pdf-tools/crop/', views.pdf_tool_crop, name='pdf_tool_crop'),
    path('pdf-tools/organize/', views.pdf_tool_organize, name='pdf_tool_organize'),
    path('pdf-tools/extract_image/', views.pdf_tool_extract_image, name='pdf_tool_extract_image'),
    path('pdf-tools/page-remover/', views.pdf_tool_page_remover, name='pdf_tool_page_remover'),
    path('pdf-tools/extract-pages/', views.pdf_tool_extract_pages, name='pdf_tool_extract_pages'),

    # School Registration & Subscription
    path('register/', views.school_register, name='school_register'),
    path('register/user/', views.user_register, name='user_register'),
    path('subscription/plans/', views.subscription_plans, name='subscription_plans'),
    
    # Job Listings
    path('jobs/bom/', views.bom_jobs, name='bom_jobs'),
    path('jobs/homeschooling/', views.homeschooling_jobs, name='homeschooling_jobs'),
    path('jobs/post/', views.post_job, name='post_job'),
    path('manage-jobs/', views.admin_job_approvals, name='admin_job_approvals'),
    
    path('subscription/subscribe/<int:plan_id>/', views.subscribe_plan, name='subscribe_plan'),
    path('profile/', views.user_profile, name='user_profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('dashboard/', views.user_dashboard, name='user_dashboard'),

    # Admin Plan Management (NOT under admin/ to avoid Django admin catch-all conflict)
    path('manage-plans/', admin_views.admin_plans_list, name='admin_plans_list'),
    path('manage-plans/add/', admin_views.admin_plan_add, name='admin_plan_add'),
    path('manage-plans/edit/<int:plan_id>/', admin_views.admin_plan_edit, name='admin_plan_edit'),
    path('manage-plans/delete/<int:plan_id>/', admin_views.admin_plan_delete, name='admin_plan_delete'),
    path('manage-plans/toggle/<int:plan_id>/', admin_views.admin_plan_toggle, name='admin_plan_toggle'),
    path('payment/toggle-free-period/', admin_views.toggle_free_period, name='toggle_free_period'),
]