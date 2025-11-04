# Django Decode Data - Complete Setup Guide

## 📁 Project Structure

```
decode_data_project/
├── manage.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── SETUP.md
├── decode_data/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── learning/
│   ├── __init__.py
│   ├── models.py
│   ├── views.py
│   ├── forms.py
│   ├── admin.py
│   ├── dbt_manager.py
│   ├── storage.py
│   ├── apps.py
│   ├── urls/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   └── main.py
│   ├── migrations/
│   │   └── __init__.py
│   ├── templates/
│   │   ├── base.html
│   │   ├── auth/
│   │   │   ├── login.html
│   │   │   └── register.html
│   │   └── learning/
│   │       ├── dashboard.html
│   │       ├── lesson_detail.html
│   │       ├── model_builder.html
│   │       ├── query_visualize.html
│   │       └── progress.html
│   └── static/
│       ├── css/
│       │   └── styles.css
│       ├── js/
│       │   └── main.js
│       └── images/
└── dbt_project/
    └── (your existing dbt project files)
```

## 🚀 Quick Start

### Step 1: Create Project Directory
```bash
mkdir decode_data_project
cd decode_data_project
```

### Step 2: Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Step 3: Download All Files
Download all the artifact files I've created and place them in the correct locations according to the structure above.

### Step 4: Create Required Directories
```bash
# Main directories
mkdir -p decode_data learning/urls learning/migrations
mkdir -p learning/templates/auth learning/templates/learning
mkdir -p learning/static/css learning/static/js learning/static/images

# Create __init__.py files
touch decode_data/__init__.py
touch learning/__init__.py
touch learning/urls/__init__.py
touch learning/migrations/__init__.py
```

### Step 5: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 6: Configure Environment
```bash
# Copy the example env file
cp .env.example .env

# Edit .env with your values
nano .env  # or use your preferred editor
```

Required environment variables:
- `DJANGO_SECRET_KEY`: Generate with `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`
- `MOTHERDUCK_TOKEN`: Your MotherDuck token
- `DEBUG`: Set to `True` for development

### Step 7: Create learning/apps.py
```bash
cat > learning/apps.py << 'EOF'
from django.apps import AppConfig


class LearningConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'learning'
EOF
```

### Step 8: Run Migrations
```bash
# Create migrations
python manage.py makemigrations learning

# Apply migrations
python manage.py migrate

# Create superuser (optional)
python manage.py createsuperuser
```

### Step 9: Collect Static Files
```bash
python manage.py collectstatic --noinput
```

### Step 10: Run Development Server
```bash
python manage.py runserver
```

Visit: http://127.0.0.1:8000/

## 📝 Creating Missing Template Files

Since I couldn't include all templates in separate artifacts, you'll need to copy them from the original document. Here's what you need:

### Templates to Create:

1. **learning/templates/base.html** - Base template with navbar
2. **learning/templates/auth/login.html** - Login page
3. **learning/templates/auth/register.html** - Registration page
4. **learning/templates/learning/dashboard.html** - Main dashboard
5. **learning/templates/learning/lesson_detail.html** - Lesson overview
6. **learning/templates/learning/model_builder.html** - Model builder interface
7. **learning/templates/learning/query_visualize.html** - Query interface
8. **learning/templates/learning/progress.html** - Progress tracking

### Static Files to Create:

1. **learning/static/css/styles.css** - Custom styles
2. **learning/static/js/main.js** - JavaScript utilities

## 🐳 Docker Setup (Optional)

Create `Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python manage.py collectstatic --noinput

CMD ["gunicorn", "decode_data.wsgi:application", "--bind", "0.0.0.0:8000"]
```

Create `docker-compose.yml`:
```yaml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - .:/app
    command: python manage.py runserver 0.0.0.0:8000
```

## 🚢 Deployment Options

### Railway
```bash
railway login
railway init
railway up
```

### Heroku
```bash
heroku create your-app-name
git push heroku main
heroku run python manage.py migrate
```

### Render
Add `render.yaml`:
```yaml
services:
  - type: web
    name: decode-data
    env: python
    buildCommand: pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate
    startCommand: gunicorn decode_data.wsgi:application
```

## 🔧 Common Issues & Solutions

### Issue: "No module named 'learning'"
**Solution**: Ensure `learning` is in `INSTALLED_APPS` in settings.py

### Issue: "AUTH_USER_MODEL" error
**Solution**: Set `AUTH_USER_MODEL = 'learning.User'` BEFORE first migration

### Issue: Static files not loading
**Solution**: Run `python manage.py collectstatic` and check `STATIC_ROOT`

### Issue: MotherDuck connection fails
**Solution**: Verify `MOTHERDUCK_TOKEN` is set correctly in `.env`

### Issue: Templates not found
**Solution**: Ensure templates are in `learning/templates/` and `DIRS` is set in settings.py

## 🧪 Testing

```bash
# Run tests
python manage.py test

# Check for issues
python manage.py check

# Create test user
python manage.py shell
>>> from learning.models import User
>>> user = User.objects.create_user(username='testuser', email='test@example.com', password='testpass123')
>>> user.save()
```

## 📊 Database Management

```bash
# Create new migration after model changes
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Rollback migration
python manage.py migrate learning 0001

# Show migrations
python manage.py showmigrations

# SQL for migration
python manage.py sqlmigrate learning 0001
```

## 🎯 Next Steps

1. ✅ Complete setup following this guide
2. ✅ Test authentication (login/register)
3. ✅ Test lesson flow
4. ✅ Verify MotherDuck connection
5. ✅ Test model building and execution
6. ✅ Deploy to production
7. ✅ Set up monitoring and logging

## 📚 Additional Resources

- [Django Documentation](https://docs.djangoproject.com/)
- [Django Best Practices](https://django-best-practices.readthedocs.io/)
- [MotherDuck Documentation](https://motherduck.com/docs/)
- [dbt Documentation](https://docs.getdbt.com/)

## 💡 Tips

1. Always use virtual environments
2. Never commit `.env` files
3. Use strong secret keys in production
4. Set `DEBUG=False` in production
5. Use PostgreSQL for production
6. Enable HTTPS in production
7. Set up proper logging
8. Monitor application performance
9. Regular database backups
10. Keep dependencies updated

Good luck! 🎉