# config.py
import os

# Database connection parameters
DB_CONFIG = {
    'server': os.environ.get('DB_SERVER', 'localhost'),
    'database': os.environ.get('DB_DATABASE', 'MISDW'),
    'username': os.environ.get('DB_USERNAME', 'mis_amrihani'),
    'password': os.environ.get('DB_PASSWORD', 'mis_amrihani')
}
TREANSACTION_CODE = {
    'file_path': './param_file/accountant_trx.xlsx',
    'sheet_name': 'Sheet1'
}