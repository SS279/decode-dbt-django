import duckdb
import pandas as pd
import os


class MotherDuckStorage:
    """MotherDuck storage interface"""
    
    def __init__(self):
        self.token = os.environ.get('MOTHERDUCK_TOKEN')
        self.share = os.environ.get('MOTHERDUCK_SHARE', 'decode_dbt')
    
    def _get_connection(self):
        """Create MotherDuck connection"""
        if not self.token:
            raise ValueError("MOTHERDUCK_TOKEN environment variable not set")
        return duckdb.connect(f"md:{self.share}?motherduck_token={self.token}")
    
    def execute_query(self, schema, query):
        """Execute SQL query and return results"""
        conn = self._get_connection()
        try:
            conn.execute(f"USE {self.share}")
            conn.execute(f"SET SCHEMA '{schema}'")
            
            df = conn.execute(query).fetchdf()
            
            # Convert to dict for JSON serialization
            return {
                'columns': df.columns.tolist(),
                'data': df.values.tolist(),
                'dtypes': {col: str(dtype) for col, dtype in df.dtypes.items()},
                'shape': df.shape
            }
        finally:
            conn.close()
    
    def list_tables(self, schema):
        """List tables in schema"""
        conn = self._get_connection()
        try:
            query = f"""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = '{schema}'
            ORDER BY table_name
            """
            df = conn.execute(query).fetchdf()
            return df['table_name'].tolist()
        finally:
            conn.close()
    
    def validate_output(self, schema, validation):
        """Validate lesson completion"""
        try:
            conn = self._get_connection()
            conn.execute(f"USE {self.share}")
            conn.execute(f"SET SCHEMA '{schema}'")
            
            result = conn.execute(validation['sql']).fetchdf()
            conn.close()
            
            models_built = result.iloc[0]['models_built']
            success = models_built >= validation['expected_min']
            
            return {
                'success': success,
                'models_built': int(models_built),
                'expected_min': validation['expected_min']
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }