from django.urls import path
from learning import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('lesson/<str:lesson_id>/', views.lesson_detail, name='lesson_detail'),
    path('lesson/<str:lesson_id>/builder/', views.model_builder, name='model_builder'),
    path('lesson/<str:lesson_id>/query/', views.query_visualize, name='query_visualize'),
    path('lesson/<str:lesson_id>/progress/', views.progress_dashboard, name='progress_dashboard'),
    
    # API endpoints
    path('api/get-model/', views.api_get_model_content, name='api_get_model'),
    path('api/validate/', views.api_validate_lesson, name='api_validate'),
]