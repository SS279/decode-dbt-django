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
        # Use /app/dbt_workspaces for Railway persistence
        # Falls back to tempdir for local development
        if os.environ.get('RAILWAY_ENVIRONMENT'):
            base_dir = Path('/app/dbt_workspaces')
        else:
            base_dir = Path(tempfile.gettempdir()) / 'dbt_workspaces'
        
        workspace = base_dir / f"user_{self.user.id}" / self.lesson['id']
        return workspace
    
    def is_initialized(self):
        """Check if workspace is initialized"""
        return self.workspace_path.exists() and (self.workspace_path / 'dbt_project.yml').exists()
    
    def initialize_workspace(self):
        """Initialize DBT workspace"""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Create workspace directory
            self.workspace_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created workspace at: {self.workspace_path}")
            
            # Copy dbt project
            source_dir = Path('dbt_project')
            if not source_dir.exists():
                # Try alternate paths
                source_dir = Path.cwd() / 'dbt_project'
                if not source_dir.exists():
                    source_dir = Path(__file__).parent.parent / 'dbt_project'
                    if not source_dir.exists():
                        return False, f'dbt_project directory not found. Searched in: {Path("dbt_project").absolute()}, {Path.cwd() / "dbt_project"}, {Path(__file__).parent.parent / "dbt_project"}'
            
            logger.info(f"Copying dbt project from: {source_dir}")
            shutil.copytree(source_dir, self.workspace_path, dirs_exist_ok=True)
            
            # Create schema in MotherDuck
            from learning.storage import MotherDuckStorage
            storage = MotherDuckStorage()
            
            try:
                conn = storage._get_connection()
                conn.execute(f"USE {storage.share}")
                conn.execute(f"CREATE SCHEMA IF NOT EXISTS {self.user.schema_name}")
                logger.info(f"Created schema in MotherDuck: {self.user.schema_name}")
                
                # Copy seed data to user schema if it exists
                try:
                    conn.execute(f"SET SCHEMA '{self.user.schema_name}'")
                    
                    # Check if shared schema has seed data
                    conn.execute(f"CREATE TABLE IF NOT EXISTS raw_customers AS SELECT * FROM shared.raw_customers WHERE 1=0")
                    logger.info("Initialized raw tables in user schema")
                except Exception as e:
                    logger.warning(f"Could not copy seed data (this is ok if no seed data exists): {e}")
                
                conn.close()
            except Exception as e:
                logger.error(f"Failed to create schema in MotherDuck: {e}")
                # Don't fail initialization if schema creation fails
            
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
            logger.info(f"Created profiles.yml at: {profiles_path}")
            
            return True, 'Workspace initialized successfully'
        except Exception as e:
            logger.error(f"Error initializing workspace: {str(e)}")
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
        import logging
        logger = logging.getLogger(__name__)
        
        if not self.is_initialized():
            return False, 'Workspace not initialized'
        
        # Check if dbt is available
        try:
            dbt_check = subprocess.run(['which', 'dbt'], capture_output=True, text=True)
            logger.info(f"dbt location: {dbt_check.stdout}")
        except:
            pass
        
        try:
            results = []
            for model_name in model_names:
                # Build the selector - use just the model name, not lesson prefix
                selector = model_name
                if include_children:
                    selector += "+"
                
                # Build command - use profiles-dir to point to workspace
                cmd = [
                    'dbt', 'run',
                    '--select', selector,
                    '--profiles-dir', str(self.workspace_path),
                    '--project-dir', str(self.workspace_path)
                ]
                if full_refresh:
                    cmd.append('--full-refresh')
                
                logger.info(f"Executing dbt command: {' '.join(cmd)}")
                logger.info(f"Working directory: {self.workspace_path}")
                logger.info(f"User schema: {self.user.schema_name}")
                
                # Check if profiles.yml exists
                profiles_path = self.workspace_path / 'profiles.yml'
                if profiles_path.exists():
                    logger.info(f"profiles.yml exists: {profiles_path}")
                    logger.info(f"profiles.yml content:\n{profiles_path.read_text()}")
                else:
                    logger.error(f"profiles.yml NOT FOUND at {profiles_path}")
                
                # Check if dbt_project.yml exists
                dbt_project_path = self.workspace_path / 'dbt_project.yml'
                if dbt_project_path.exists():
                    logger.info(f"dbt_project.yml exists")
                else:
                    logger.error(f"dbt_project.yml NOT FOUND at {dbt_project_path}")
                
                # Check if model file exists
                model_path = self.workspace_path / self.lesson['model_dir'] / f'{model_name}.sql'
                if model_path.exists():
                    logger.info(f"Model file exists: {model_path}")
                else:
                    logger.error(f"Model file NOT FOUND: {model_path}")
                
                result = subprocess.run(
                    cmd,
                    cwd=self.workspace_path,
                    capture_output=True,
                    text=True,
                    env={
                        **os.environ,
                        'MOTHERDUCK_TOKEN': os.environ.get('MOTHERDUCK_TOKEN', ''),
                        'DBT_PROFILES_DIR': str(self.workspace_path)
                    }
                )
                
                logger.info(f"dbt return code: {result.returncode}")
                logger.info(f"dbt stdout:\n{result.stdout}")
                if result.stderr:
                    logger.error(f"dbt stderr:\n{result.stderr}")
                
                results.append({
                    'model': model_name,
                    'success': result.returncode == 0,
                    'output': result.stdout + '\n' + result.stderr,
                    'returncode': result.returncode
                })
            
            return True, results
        except Exception as e:
            logger.error(f"Error executing models: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False, str(e)
    
    def run_seeds(self):
        """Run DBT seeds for specific lesson"""
        import logging
        logger = logging.getLogger(__name__)
        
        if not self.is_initialized():
            return False, 'Workspace not initialized'
        
        try:
            # Check for lesson-specific seeds directory
            lesson_seed_dir = self.workspace_path / 'seeds' / self.lesson['id']
            
            if not lesson_seed_dir.exists():
                logger.info(f"No seeds directory found at {lesson_seed_dir}")
                # Also check if there's a generic seeds directory
                generic_seed_dir = self.workspace_path / 'seeds'
                if generic_seed_dir.exists():
                    logger.info(f"Found generic seeds directory at {generic_seed_dir}")
                    seed_dir = generic_seed_dir
                else:
                    return True, 'No seed data available for this lesson'
            else:
                seed_dir = lesson_seed_dir
                logger.info(f"Using lesson-specific seeds from {lesson_seed_dir}")
            
            # List seed files in the directory
            seed_files = list(seed_dir.glob('**/*.csv'))
            if not seed_files:
                logger.info(f"No CSV files found in {seed_dir}")
                return True, 'No seed files found for this lesson'
            
            logger.info(f"Found {len(seed_files)} seed files: {[f.name for f in seed_files]}")
            
            # Run dbt seed command
            # If using lesson-specific seeds, we can use --select to target specific seeds
            cmd = [
                'dbt', 'seed',
                '--profiles-dir', str(self.workspace_path),
                '--project-dir', str(self.workspace_path)
            ]
            
            # If seeds are in a lesson subdirectory, dbt will still find them
            # dbt looks in seeds/ directory recursively
            
            logger.info(f"Running dbt seed command: {' '.join(cmd)}")
            logger.info(f"Working directory: {self.workspace_path}")
            logger.info(f"User schema: {self.user.schema_name}")
            
            result = subprocess.run(
                cmd,
                cwd=self.workspace_path,
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    'MOTHERDUCK_TOKEN': os.environ.get('MOTHERDUCK_TOKEN', ''),
                    'DBT_PROFILES_DIR': str(self.workspace_path)
                }
            )
            
            logger.info(f"dbt seed return code: {result.returncode}")
            logger.info(f"dbt seed stdout:\n{result.stdout}")
            if result.stderr:
                logger.error(f"dbt seed stderr:\n{result.stderr}")
            
            output = result.stdout + '\n' + result.stderr
            
            if result.returncode == 0:
                # Parse output to see which seeds were loaded
                seed_names = [f.stem for f in seed_files]
                return True, f'Successfully loaded {len(seed_files)} seed file(s): {", ".join(seed_names)}\n\n{output}'
            else:
                return False, f'Seed loading failed:\n{output}'
                
        except Exception as e:
            logger.error(f"Error running seeds: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False, str(e)