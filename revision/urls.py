from django.urls import path
from . import views

urlpatterns = [
    path('', views.revision_home, name='revision_home'),
    path('browse/', views.browse_materials, name='browse_materials'),
    path('browse-subjects/', views.browse_by_subject, name='browse_by_subject'),
    path('class/<int:class_id>/', views.class_subjects, name='class_subjects'),
    path('subject/<int:subject_id>/', views.subject_materials, name='subject_materials'),
    path('material/<int:material_id>/', views.material_detail, name='material_detail'),
    path('download/<int:material_id>/', views.download_material, name='download_material'),
    path('preview/<int:material_id>/', views.preview_material, name='preview_material'),
    path('generate-sow/', views.generate_scheme_of_work, name='generate_scheme_of_work'),
    path('link-material/', views.link_material, name='link_material'),
    path('schemes/', views.browse_schemes, name='browse_schemes'),
    path('scheme/<int:scheme_id>/download/', views.download_scheme, name='download_scheme'),
]