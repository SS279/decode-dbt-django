from django.contrib import admin
from .models import User, LearnerProgress, ModelEdit, UserSession


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['username', 'email', 'schema_name', 'created_at', 'is_active']
    search_fields = ['username', 'email', 'schema_name']
    list_filter = ['is_active', 'created_at']
    readonly_fields = ['created_at', 'last_login']


@admin.register(LearnerProgress)
class LearnerProgressAdmin(admin.ModelAdmin):
    list_display = ['user', 'lesson_id', 'lesson_progress', 'queries_run', 'last_updated']
    list_filter = ['lesson_id', 'last_updated']
    search_fields = ['user__username', 'lesson_id']
    readonly_fields = ['last_updated']


@admin.register(ModelEdit)
class ModelEditAdmin(admin.ModelAdmin):
    list_display = ['user', 'lesson_id', 'model_name', 'last_updated']
    list_filter = ['lesson_id', 'last_updated']
    search_fields = ['user__username', 'model_name', 'lesson_id']
    readonly_fields = ['last_updated']


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ['user', 'is_active', 'created_at', 'last_activity']
    list_filter = ['is_active', 'created_at']
    search_fields = ['user__username', 'session_key']
    readonly_fields = ['created_at', 'last_activity']