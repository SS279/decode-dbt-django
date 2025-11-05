from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .models import User, LearnerProgress, ModelEdit
from .forms import LoginForm, RegisterForm, SQLQueryForm
from .dbt_manager import DBTManager
from .storage import MotherDuckStorage

# Lesson configuration
LESSONS = [
    {
        "id": "hello_dbt",
        "title": "🧱 Hello dbt",
        "description": "From Raw to Refined - Introductory hands-on dbt exercise",
        "model_dir": "models/hello_dbt",  # Make sure this exists!
        "validation": {
            "sql": "SELECT COUNT(*) AS models_built FROM information_schema.tables WHERE table_schema=current_schema()",
            "expected_min": 2
        },
    },
    {
        "id": "cafe_chain",
        "title": "☕ Café Chain Analytics",
        "description": "Analyze coffee shop sales, customer loyalty, and business performance metrics.",
        "model_dir": "models/cafe_chain",  # Make sure this exists!
        "validation": {
            "sql": "SELECT COUNT(*) AS models_built FROM information_schema.tables WHERE table_schema=current_schema()",
            "expected_min": 2
        },
    },
    {
        "id": "energy_smart",
        "title": "⚡ Energy Startup: Smart Meter Data",
        "description": "Model IoT sensor readings and calculate energy consumption KPIs.",
        "model_dir": "models/energy_smart",  # Make sure this exists!
        "validation": {
            "sql": "SELECT COUNT(*) AS models_built FROM information_schema.tables WHERE table_schema=current_schema()",
            "expected_min": 2
        },
    }
]


def login_view(request):
    """User login"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            
            if user:
                login(request, user)
                messages.success(request, f'Welcome back, {username}!')
                return redirect('dashboard')
            else:
                messages.error(request, 'Invalid username or password')
    else:
        form = LoginForm()
    
    return render(request, 'auth/login.html', {'form': form})


def register_view(request):
    """User registration"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, 'Account created successfully! Please login.')
            return redirect('login')
    else:
        form = RegisterForm()
    
    return render(request, 'auth/register.html', {'form': form})


def logout_view(request):
    """User logout"""
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('login')


@login_required
def dashboard(request):
    """Main dashboard showing all lessons"""
    user = request.user
    all_progress = LearnerProgress.objects.filter(user=user)
    
    # Build progress dict
    progress_dict = {p.lesson_id: p for p in all_progress}
    
    # Add progress info to lessons
    lessons_with_progress = []
    for lesson in LESSONS:
        lesson_copy = lesson.copy()
        progress = progress_dict.get(lesson['id'])
        lesson_copy['progress'] = progress.lesson_progress if progress else 0
        lessons_with_progress.append(lesson_copy)
    
    context = {
        'lessons': lessons_with_progress,
        'user': user,
    }
    return render(request, 'learning/dashboard.html', context)


@login_required
def lesson_detail(request, lesson_id):
    """Lesson detail view"""
    lesson = next((l for l in LESSONS if l['id'] == lesson_id), None)
    if not lesson:
        messages.error(request, 'Lesson not found')
        return redirect('dashboard')
    
    # Get or create progress
    progress, created = LearnerProgress.objects.get_or_create(
        user=request.user,
        lesson_id=lesson_id,
        defaults={'lesson_progress': 0}
    )
    
    context = {
        'lesson': lesson,
        'progress': progress,
        'user': request.user,
    }
    return render(request, 'learning/lesson_detail.html', context)


@login_required
def model_builder(request, lesson_id):
    lesson = next((l for l in LESSONS if l['id'] == lesson_id), None)
    if not lesson:
        messages.error(request, 'Lesson not found')
        return redirect('dashboard')
    
    # Initialize DBT manager
    try:
        dbt_manager = DBTManager(request.user, lesson)
    except Exception as e:
        import logging
        logging.error(f"Error initializing DBT manager: {str(e)}")
        messages.error(request, f'Error initializing workspace: {str(e)}')
        return redirect('lesson_detail', lesson_id=lesson_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'initialize':
            success, message = dbt_manager.initialize_workspace()
        if success:
            messages.success(request, message)
            # Update progress
            progress, _ = LearnerProgress.objects.get_or_create(
                user=request.user, lesson_id=lesson_id
            )
            progress.lesson_progress = min(100, progress.lesson_progress + 20)
            progress.completed_steps = progress.completed_steps or []
            if 'sandbox_initialized' not in progress.completed_steps:
                progress.completed_steps.append('sandbox_initialized')
            progress.save()
        else:
            messages.error(request, message)
    
    elif action == 'save_model':
        model_name = request.POST.get('model_name')
        model_sql = request.POST.get('model_sql')
        success, message = dbt_manager.save_model(model_name, model_sql)
        if success:
            messages.success(request, message)
            # Save to database
            ModelEdit.objects.update_or_create(
                user=request.user,
                lesson_id=lesson_id,
                model_name=model_name,
                defaults={'model_sql': model_sql}
            )
        else:
            messages.error(request, message)
            
    elif action == 'execute_models':
        selected_models = request.POST.getlist('selected_models')
        include_children = request.POST.get('include_children') == 'on'
        full_refresh = request.POST.get('full_refresh') == 'on'
        
        if not selected_models:
            messages.error(request, 'Please select at least one model to execute')
            return redirect('model_builder', lesson_id=lesson_id)
        
        success, results = dbt_manager.execute_models(
            selected_models, include_children, full_refresh
        )
        
        if success:
            # Show detailed results for each model
            for result in results:
                if result['success']:
                    messages.success(request, f"✅ Model '{result['model']}' executed successfully")
                else:
                    messages.error(request, f"❌ Model '{result['model']}' failed")
                
                # Show output (for debugging)
                if result.get('output'):
                    # Truncate if too long
                    output = result['output'][:500]
                    messages.info(request, f"Output: {output}")
            
            # Update progress
            progress, _ = LearnerProgress.objects.get_or_create(
                user=request.user, lesson_id=lesson_id
            )
            progress.lesson_progress = min(100, progress.lesson_progress + 30)
            progress.models_executed = progress.models_executed or []
            progress.models_executed.extend(
                [m for m in selected_models if m not in progress.models_executed]
            )
            progress.save()
        else:
            messages.error(request, f'Execution failed: {results}')
            # Log the full error
            import logging
            logging.error(f"dbt execution failed for user {request.user.username}: {results}")
        
    # GET request - show models
    try:
        models = dbt_manager.get_model_files()
    except Exception as e:
        import logging
        logging.error(f"Error getting model files: {str(e)}")
        messages.error(request, f'Error loading models: {str(e)}')
        models = []
    
    try:
        saved_edits = {
            me.model_name: me.model_sql 
            for me in ModelEdit.objects.filter(user=request.user, lesson_id=lesson_id)
        }
    except Exception as e:
        import logging
        logging.error(f"Error loading saved edits: {str(e)}")
        saved_edits = {}
    
    context = {
        'lesson': lesson,
        'models': models,
        'saved_edits': saved_edits,
        'workspace_initialized': dbt_manager.is_initialized(),
    }
    return render(request, 'learning/model_builder.html', context)


@login_required
def query_visualize(request, lesson_id):
    """SQL query and visualization interface"""
    lesson = next((l for l in LESSONS if l['id'] == lesson_id), None)
    if not lesson:
        messages.error(request, 'Lesson not found')
        return redirect('dashboard')
    
    result_data = None
    query = ""
    
    if request.method == 'POST':
        form = SQLQueryForm(request.POST)
        if form.is_valid():
            query = form.cleaned_data['query']
            storage = MotherDuckStorage()
            
            try:
                result_data = storage.execute_query(
                    request.user.schema_name, 
                    query
                )
                messages.success(request, 'Query executed successfully')
                
                # Update progress
                progress, _ = LearnerProgress.objects.get_or_create(
                    user=request.user, lesson_id=lesson_id
                )
                progress.queries_run += 1
                progress.lesson_progress = min(100, progress.lesson_progress + 10)
                progress.save()
                
            except Exception as e:
                messages.error(request, f'Query error: {str(e)}')
    else:
        form = SQLQueryForm()
    
    context = {
        'lesson': lesson,
        'form': form,
        'result_data': result_data,
        'query': query,
    }
    return render(request, 'learning/query_visualize.html', context)


@login_required
def progress_dashboard(request, lesson_id):
    """Progress tracking dashboard"""
    lesson = next((l for l in LESSONS if l['id'] == lesson_id), None)
    if not lesson:
        messages.error(request, 'Lesson not found')
        return redirect('dashboard')
    
    progress = get_object_or_404(LearnerProgress, user=request.user, lesson_id=lesson_id)
    all_progress = LearnerProgress.objects.filter(user=request.user)
    
    # Serialize progress data for JavaScript
    import json
    all_progress_data = [
        {
            'lesson_id': p.lesson_id,
            'lesson_progress': p.lesson_progress
        }
        for p in all_progress
    ]
    
    context = {
        'lesson': lesson,
        'progress': progress,
        'all_progress': json.dumps(all_progress_data),
        'lessons': json.dumps(LESSONS),
    }
    return render(request, 'learning/progress.html', context)


# API endpoints for AJAX requests
@login_required
@require_http_methods(["POST"])
def api_get_model_content(request):
    """API: Get model SQL content"""
    model_name = request.POST.get('model_name')
    lesson_id = request.POST.get('lesson_id')
    
    try:
        model_edit = ModelEdit.objects.get(
            user=request.user,
            lesson_id=lesson_id,
            model_name=model_name
        )
        return JsonResponse({'success': True, 'sql': model_edit.model_sql})
    except ModelEdit.DoesNotExist:
        # Return original from file
        lesson = next((l for l in LESSONS if l['id'] == lesson_id), None)
        if lesson:
            dbt_manager = DBTManager(request.user, lesson)
            sql = dbt_manager.load_original_model(model_name)
            return JsonResponse({'success': True, 'sql': sql})
        return JsonResponse({'success': False, 'message': 'Model not found'})


@login_required
@require_http_methods(["POST"])
def api_validate_lesson(request):
    """API: Validate lesson completion"""
    lesson_id = request.POST.get('lesson_id')
    lesson = next((l for l in LESSONS if l['id'] == lesson_id), None)
    
    if not lesson:
        return JsonResponse({'success': False, 'message': 'Lesson not found'})
    
    storage = MotherDuckStorage()
    try:
        result = storage.validate_output(
            request.user.schema_name,
            lesson['validation']
        )
        
        if result['success']:
            progress, _ = LearnerProgress.objects.get_or_create(
                user=request.user, lesson_id=lesson_id
            )
            progress.lesson_progress = 100
            progress.completed_steps = progress.completed_steps or []
            if 'lesson_completed' not in progress.completed_steps:
                progress.completed_steps.append('lesson_completed')
            progress.save()
        
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
@require_http_methods(["POST"])
def api_test_dbt(request):
    """API: Test dbt execution with debug info"""
    import subprocess
    import traceback
    
    try:
        lesson_id = request.POST.get('lesson_id', 'hello_dbt')
        lesson = next((l for l in LESSONS if l['id'] == lesson_id), None)
        
        if not lesson:
            return JsonResponse({'success': False, 'message': 'Lesson not found'})
        
        dbt_manager = DBTManager(request.user, lesson)
        
        debug_info = {
            'workspace_initialized': dbt_manager.is_initialized(),
            'workspace_path': str(dbt_manager.workspace_path),
            'user_schema': request.user.schema_name,
            'lesson_id': lesson_id,
            'model_dir': lesson.get('model_dir', 'N/A'),
        }
        
        if dbt_manager.is_initialized():
            # Check dbt installation
            try:
                dbt_version = subprocess.run(['dbt', '--version'], capture_output=True, text=True, timeout=10)
                debug_info['dbt_version'] = dbt_version.stdout
                debug_info['dbt_installed'] = True
            except Exception as e:
                debug_info['dbt_version'] = f'Error: {str(e)}'
                debug_info['dbt_installed'] = False
            
            # Check workspace files
            try:
                workspace_files = list(dbt_manager.workspace_path.glob('*'))
                debug_info['workspace_files'] = [str(f.name) for f in workspace_files]
            except Exception as e:
                debug_info['workspace_files'] = f'Error: {str(e)}'
            
            # Check model directory
            try:
                model_dir = dbt_manager.workspace_path / lesson['model_dir']
                debug_info['model_dir_exists'] = model_dir.exists()
                if model_dir.exists():
                    model_files = list(model_dir.glob('*.sql'))
                    debug_info['model_files'] = [f.name for f in model_files]
                else:
                    debug_info['model_files'] = 'Model directory does not exist'
            except Exception as e:
                debug_info['model_files'] = f'Error: {str(e)}'
            
            # Check profiles.yml
            try:
                profiles_path = dbt_manager.workspace_path / 'profiles.yml'
                if profiles_path.exists():
                    debug_info['profiles_yml_exists'] = True
                    debug_info['profiles_yml_content'] = profiles_path.read_text()
                else:
                    debug_info['profiles_yml_exists'] = False
            except Exception as e:
                debug_info['profiles_yml_error'] = str(e)
            
            # Check dbt_project.yml
            try:
                dbt_project_path = dbt_manager.workspace_path / 'dbt_project.yml'
                debug_info['dbt_project_yml_exists'] = dbt_project_path.exists()
            except Exception as e:
                debug_info['dbt_project_yml_error'] = str(e)
            
            # Try running dbt debug
            try:
                dbt_debug = subprocess.run(
                    ['dbt', 'debug', '--profiles-dir', str(dbt_manager.workspace_path)],
                    cwd=dbt_manager.workspace_path,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    env={**os.environ, 'MOTHERDUCK_TOKEN': os.environ.get('MOTHERDUCK_TOKEN', '')}
                )
                debug_info['dbt_debug_output'] = dbt_debug.stdout + '\n' + dbt_debug.stderr
                debug_info['dbt_debug_success'] = dbt_debug.returncode == 0
            except Exception as e:
                debug_info['dbt_debug_output'] = f'Error: {str(e)}'
        
        return JsonResponse(debug_info)
        
    except Exception as e:
        import logging
        logging.error(f"Error in api_test_dbt: {str(e)}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return JsonResponse({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        })