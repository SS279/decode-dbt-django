from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from learning.models import LearnerProgress, ModelEdit

User = get_user_model()


class AuthenticationTests(TestCase):
    """Test user authentication functionality"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_login_page_loads(self):
        """Test that login page loads successfully"""
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sign In')
    
    def test_register_page_loads(self):
        """Test that registration page loads successfully"""
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Create Account')
    
    def test_user_can_login(self):
        """Test that user can login with correct credentials"""
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'testpass123'
        })
        self.assertEqual(response.status_code, 302)  # Redirect after login
        self.assertRedirects(response, reverse('dashboard'))
    
    def test_user_cannot_login_with_wrong_password(self):
        """Test that user cannot login with incorrect password"""
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid username or password')
    
    def test_user_registration(self):
        """Test that new user can register"""
        response = self.client.post(reverse('register'), {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password1': 'complexpass123',
            'password2': 'complexpass123'
        })
        self.assertEqual(response.status_code, 302)  # Redirect after registration
        self.assertTrue(User.objects.filter(username='newuser').exists())
    
    def test_dashboard_requires_login(self):
        """Test that dashboard redirects to login if not authenticated"""
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/auth/login/', response.url)
    
    def test_logout(self):
        """Test that user can logout"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('logout'))
        self.assertEqual(response.status_code, 302)


class UserModelTests(TestCase):
    """Test User model functionality"""
    
    def test_user_creation(self):
        """Test that user is created with all required fields"""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.assertEqual(user.username, 'testuser')
        self.assertEqual(user.email, 'test@example.com')
        self.assertTrue(user.schema_name)  # Schema name auto-generated
        self.assertTrue(user.schema_name.startswith('learner_'))
    
    def test_schema_name_auto_generation(self):
        """Test that schema name is automatically generated"""
        user = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123'
        )
        self.assertIsNotNone(user.schema_name)
        self.assertTrue(len(user.schema_name) > 8)


class LearnerProgressTests(TestCase):
    """Test LearnerProgress model and tracking"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_progress_creation(self):
        """Test creating learner progress"""
        progress = LearnerProgress.objects.create(
            user=self.user,
            lesson_id='hello_dbt',
            lesson_progress=50
        )
        self.assertEqual(progress.lesson_progress, 50)
        self.assertEqual(progress.lesson_id, 'hello_dbt')
    
    def test_unique_constraint(self):
        """Test that user can't have duplicate progress for same lesson"""
        LearnerProgress.objects.create(
            user=self.user,
            lesson_id='hello_dbt',
            lesson_progress=50
        )
        
        # Try to create duplicate - should fail or update existing
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            LearnerProgress.objects.create(
                user=self.user,
                lesson_id='hello_dbt',
                lesson_progress=75
            )


class DashboardTests(TestCase):
    """Test dashboard functionality"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
    
    def test_dashboard_loads(self):
        """Test that dashboard loads for authenticated user"""
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Choose Your Learning Path')
    
    def test_dashboard_shows_lessons(self):
        """Test that dashboard displays available lessons"""
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'Hello dbt')
        self.assertContains(response, 'Café Chain Analytics')


class LessonTests(TestCase):
    """Test lesson functionality"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
    
    def test_lesson_detail_loads(self):
        """Test that lesson detail page loads"""
        response = self.client.get(reverse('lesson_detail', args=['hello_dbt']))
        self.assertEqual(response.status_code, 200)
    
    def test_invalid_lesson_redirects(self):
        """Test that invalid lesson ID redirects to dashboard"""
        response = self.client.get(reverse('lesson_detail', args=['invalid_lesson']))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('dashboard'))
    
    def test_lesson_creates_progress(self):
        """Test that accessing lesson creates progress entry"""
        self.client.get(reverse('lesson_detail', args=['hello_dbt']))
        progress_exists = LearnerProgress.objects.filter(
            user=self.user,
            lesson_id='hello_dbt'
        ).exists()
        self.assertTrue(progress_exists)


class ModelBuilderTests(TestCase):
    """Test model builder functionality"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
    
    def test_model_builder_loads(self):
        """Test that model builder page loads"""
        response = self.client.get(reverse('model_builder', args=['hello_dbt']))
        self.assertEqual(response.status_code, 200)
    
    def test_workspace_not_initialized_shows_setup(self):
        """Test that uninitialized workspace shows setup button"""
        response = self.client.get(reverse('model_builder', args=['hello_dbt']))
        self.assertContains(response, 'Initialize Sandbox')


class APITests(TestCase):
    """Test API endpoints"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
    
    def test_get_model_api(self):
        """Test get model content API"""
        response = self.client.post(reverse('api_get_model'), {
            'model_name': 'test_model',
            'lesson_id': 'hello_dbt'
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('success', data)
    
    def test_validate_api(self):
        """Test validation API"""
        response = self.client.post(reverse('api_validate'), {
            'lesson_id': 'hello_dbt'
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('success', data)


# Run tests with: python manage.py test
# Run specific test: python manage.py test learning.tests.AuthenticationTests
# Run with coverage: coverage run --source='.' manage.py test && coverage report