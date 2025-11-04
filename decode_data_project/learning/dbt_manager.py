import os
import tempfile
import shutil
import subprocess
from pathlib import Path


class DBTManager:
    """Manage DBT workspace and operations"""
    
    def __init__(self, user, lesson):
        self.user = user
        self.lesson = lesson
        self.workspace_path = self._get_workspace_path()
    
    def _get_workspace_path(self):
        """Get or create workspace path for user"""
        base_dir = Path(tempfile.gettempdir()) / 'dbt_workspaces'
        workspace = base_dir / f"user_{self.user.id}" / self.lesson['id']
        return workspace
    
    def is_initialized(self):
        """Check if workspace is initialized"""
        return self.workspace_path.exists() and (self.workspace_path / 'dbt_project.yml').exists()
    
    def initialize_workspace(self):
        """Initialize DBT workspace"""
        try:
            # Create workspace directory
            self.workspace_path.mkdir(parents=True, exist_ok=True)
            
            # Copy dbt project
            source_dir = Path('dbt_project')
            if not source_dir.exists():
                return False, 'dbt_project directory not found. Please ensure it exists in the project root.'
            
            shutil.copytree(source_dir, self.workspace_path, dirs_exist_ok=True)
            
            # Create profiles.yml
            profiles_content = f"""
decode_dbt:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: "md:{os.environ.get('MOTHERDUCK_SHARE', 'decode_dbt')}"
      schema: {self.user.schema_name}
      threads: 4
      motherduck_token: {os.environ.get('MOTHERDUCK_TOKEN')}
"""
            profiles_path = self.workspace_path / 'profiles.yml'
            profiles_path.write_text(profiles_content)
            
            return True, 'Workspace initialized successfully'
        except Exception as e:
            return False, f'Error initializing workspace: {str(e)}'
    
    def get_model_files(self):
        """Get list of model files"""
        if not self.is_initialized():
            return []
        
        model_dir = self.workspace_path / self.lesson['model_dir']
        if not model_dir.exists():
            return []
        
        return sorted([f.stem for f in model_dir.glob('*.sql')])
    
    def load_model(self, model_name):
        """Load model SQL content"""
        model_path = self.workspace_path / self.lesson['model_dir'] / f'{model_name}.sql'
        if model_path.exists():
            return model_path.read_text()
        return ""
    
    def load_original_model(self, model_name):
        """Load original model from source"""
        source_path = Path('dbt_project') / self.lesson['model_dir'] / f'{model_name}.sql'
        if source_path.exists():
            return source_path.read_text()
        return ""
    
    def save_model(self, model_name, sql_content):
        """Save model SQL"""
        try:
            model_path = self.workspace_path / self.lesson['model_dir'] / f'{model_name}.sql'
            model_path.parent.mkdir(parents=True, exist_ok=True)
            model_path.write_text(sql_content)
            return True, 'Model saved successfully'
        except Exception as e:
            return False, f'Error saving model: {str(e)}'
    
    def execute_models(self, model_names, include_children=False, full_refresh=False):
        """Execute DBT models"""
        if not self.is_initialized():
            return False, 'Workspace not initialized'
        
        try:
            results = []
            for model_name in model_names:
                selector = f"{self.lesson['id']}.{model_name}"
                if include_children:
                    selector += "+"
                
                cmd = ['dbt', 'run', '--select', selector, '--profiles-dir', str(self.workspace_path)]
                if full_refresh:
                    cmd.append('--full-refresh')
                
                result = subprocess.run(
                    cmd,
                    cwd=self.workspace_path,
                    capture_output=True,
                    text=True,
                    env={**os.environ, 'MOTHERDUCK_TOKEN': os.environ.get('MOTHERDUCK_TOKEN', '')}
                )
                
                results.append({
                    'model': model_name,
                    'success': result.returncode == 0,
                    'output': result.stdout + result.stderr
                })
            
            return True, results
        except Exception as e:
            return False, str(e)
    
    def run_seeds(self):
        """Run DBT seeds"""
        try:
            seed_dir = self.workspace_path / 'seeds' / self.lesson['id']
            if not seed_dir.exists():
                return True, 'No seeds found for this lesson'
            
            cmd = ['dbt', 'seed', '--profiles-dir', str(self.workspace_path)]
            
            result = subprocess.run(
                cmd,
                cwd=self.workspace_path,
                capture_output=True,
                text=True,
                env={**os.environ, 'MOTHERDUCK_TOKEN': os.environ.get('MOTHERDUCK_TOKEN', '')}
            )
            
            return result.returncode == 0, result.stdout + result.stderr
        except Exception as e:
            return False, str(e)