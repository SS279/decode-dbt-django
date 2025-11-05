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
            profiles_content = f"""decode_dbt:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: md:{os.environ.get('MOTHERDUCK_SHARE', 'decode_dbt')}
      schema: {self.user.schema_name}
      threads: 4
      motherduck_token: {os.environ.get('MOTHERDUCK_TOKEN')}
"""
            profiles_path = self.workspace_path / 'profiles.yml'
            profiles_path.write_text(profiles_content)
            logger.info(f"Created profiles.yml at: {profiles_path}")
            logger.info(f"Schema configured as: {self.user.schema_name}")
            
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
    
    def _verify_table_created(self, model_name):
        """Verify table actually exists in MotherDuck after dbt run"""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            from learning.storage import MotherDuckStorage
            storage = MotherDuckStorage()
            
            conn = storage._get_connection()
            conn.execute(f"USE {storage.share}")
            conn.execute(f"SET SCHEMA '{self.user.schema_name}'")
            
            # Check if table/view exists
            result = conn.execute(f"""
                SELECT table_name, table_type
                FROM information_schema.tables
                WHERE table_schema = '{self.user.schema_name}'
                AND table_name = '{model_name}'
            """).fetchdf()
            
            if len(result) == 0:
                logger.error(f"❌ VERIFICATION FAILED: '{model_name}' NOT FOUND in schema '{self.user.schema_name}'")
                
                # Show what IS in the schema for debugging
                all_tables = conn.execute(f"""
                    SELECT table_name, table_type
                    FROM information_schema.tables
                    WHERE table_schema = '{self.user.schema_name}'
                """).fetchdf()
                
                if len(all_tables) > 0:
                    logger.error(f"Tables/views that DO exist in schema: {all_tables['table_name'].tolist()}")
                else:
                    logger.error(f"Schema '{self.user.schema_name}' exists but contains NO tables or views")
                
                conn.close()
                return False, f"Table '{model_name}' not found in schema after dbt run"
            else:
                table_type = result.iloc[0]['table_type']
                logger.info(f"✅ VERIFICATION SUCCESS: '{model_name}' exists as {table_type} in schema '{self.user.schema_name}'")
                
                if table_type == 'VIEW':
                    logger.warning(f"⚠️  Note: '{model_name}' was created as a VIEW, not a TABLE")
                
                conn.close()
                return True, f"Verified: {model_name} created as {table_type}"
            
        except Exception as e:
            logger.error(f"❌ Verification error: {e}")
            return False, f"Verification failed: {str(e)}"
    
    def execute_models(self, model_names, include_children=False, full_refresh=False):
        """Execute DBT models"""
        import logging
        logger = logging.getLogger(__name__)
        
        if not self.is_initialized():
            return False, 'Workspace not initialized'
        
        try:
            results = []
            for model_name in model_names:
                # Try different selector formats
                # Option 1: With lesson prefix (original)
                selector = f"{self.lesson['id']}.{model_name}"
                if include_children:
                    selector += "+"
                
                cmd = ['dbt', 'run', '--select', selector, '--profiles-dir', str(self.workspace_path)]
                if full_refresh:
                    cmd.append('--full-refresh')
                
                logger.info(f"Executing dbt command: {' '.join(cmd)}")
                logger.info(f"Working directory: {self.workspace_path}")
                logger.info(f"User schema: {self.user.schema_name}")
                logger.info(f"Model selector: {selector}")
                
                result = subprocess.run(
                    cmd,
                    cwd=self.workspace_path,
                    capture_output=True,
                    text=True,
                    env={**os.environ, 'MOTHERDUCK_TOKEN': os.environ.get('MOTHERDUCK_TOKEN', '')}
                )
                
                output = result.stdout + result.stderr
                
                logger.info(f"dbt return code: {result.returncode}")
                logger.info(f"dbt stdout: {result.stdout}")
                if result.stderr:
                    logger.error(f"dbt stderr: {result.stderr}")
                
                # Parse output for detailed status
                if "OK created table" in output:
                    logger.info(f"✅ dbt reports: Table '{model_name}' created")
                elif "OK created view" in output:
                    logger.warning(f"⚠️  dbt reports: View '{model_name}' created (not table!)")
                elif "ERROR" in output or "FAIL" in output:
                    logger.error(f"❌ dbt reports: Model '{model_name}' failed")
                
                # NEW: Verify table actually exists in MotherDuck
                verification_success = False
                verification_message = ""
                
                if result.returncode == 0:
                    verification_success, verification_message = self._verify_table_created(model_name)
                    
                    if not verification_success:
                        # dbt said success but table doesn't exist!
                        logger.error(f"⚠️  CRITICAL: dbt reported success but verification failed!")
                        logger.error(f"   This means dbt thinks it created '{model_name}' but it's not in MotherDuck")
                
                results.append({
                    'model': model_name,
                    'success': result.returncode == 0,
                    'verified': verification_success,
                    'verification_message': verification_message,
                    'output': output
                })
            
            return True, results
        except Exception as e:
            logger.error(f"Error executing models: {str(e)}")
            return False, str(e)
    
    def run_seeds(self):
        """Run DBT seeds"""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            seed_dir = self.workspace_path / 'seeds' / self.lesson['id']
            if not seed_dir.exists():
                logger.info(f"No seeds directory found at: {seed_dir}")
                return True, 'No seeds found for this lesson'
            
            cmd = ['dbt', 'seed', '--profiles-dir', str(self.workspace_path)]
            
            logger.info(f"Running dbt seed: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                cwd=self.workspace_path,
                capture_output=True,
                text=True,
                env={**os.environ, 'MOTHERDUCK_TOKEN': os.environ.get('MOTHERDUCK_TOKEN', '')}
            )
            
            logger.info(f"dbt seed stdout: {result.stdout}")
            if result.stderr:
                logger.error(f"dbt seed stderr: {result.stderr}")
            
            # Verify seeds were loaded
            if result.returncode == 0:
                from learning.storage import MotherDuckStorage
                storage = MotherDuckStorage()
                try:
                    tables = storage.list_tables(self.user.schema_name)
                    logger.info(f"Tables in schema after seeding: {tables}")
                except Exception as e:
                    logger.warning(f"Could not list tables after seeding: {e}")
            
            return result.returncode == 0, result.stdout + result.stderr
        except Exception as e:
            logger.error(f"Error running seeds: {str(e)}")
            return False, str(e)