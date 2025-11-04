from django.db import models
from django.contrib.auth.models import AbstractUser
import hashlib


class User(AbstractUser):
    """Extended user model with learner-specific fields"""
    email = models.EmailField(unique=True)
    schema_name = models.CharField(max_length=100, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        if not self.schema_name:
            self.schema_name = f"learner_{hashlib.sha256(self.username.encode()).hexdigest()[:8]}"
        super().save(*args, **kwargs)
    
    class Meta:
        db_table = 'users'


class LearnerProgress(models.Model):
    """Track learner progress for each lesson"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='progress')
    lesson_id = models.CharField(max_length=100)
    lesson_progress = models.IntegerField(default=0)
    completed_steps = models.JSONField(default=list)
    models_executed = models.JSONField(default=list)
    queries_run = models.IntegerField(default=0)
    quiz_answers = models.JSONField(default=dict)
    quiz_score = models.IntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'learner_progress'
        unique_together = ('user', 'lesson_id')
        indexes = [
            models.Index(fields=['user', 'lesson_id']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.lesson_id} ({self.lesson_progress}%)"


class ModelEdit(models.Model):
    """Store user's model edits for persistence"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='model_edits')
    lesson_id = models.CharField(max_length=100)
    model_name = models.CharField(max_length=100)
    model_sql = models.TextField()
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'model_edits'
        unique_together = ('user', 'lesson_id', 'model_name')
        indexes = [
            models.Index(fields=['user', 'lesson_id']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.lesson_id}/{self.model_name}"


class UserSession(models.Model):
    """Track user sessions and DBT workspace"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    session_key = models.CharField(max_length=255, unique=True)
    dbt_workspace_path = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_sessions'
        indexes = [
            models.Index(fields=['user', 'is_active']),
        ]