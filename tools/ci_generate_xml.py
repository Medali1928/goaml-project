"""
Script utilise par la pipeline CI/CD pour generer un XML de test
sans passer par l'interface Streamlit (non interactive).
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.config import DB_CONFIG, TREANSACTION_CODE
from src.model.get_client import GetClient
from src.controller.transaction_router import TransactionRouter
from src.helpers.utils import write_transaction_details_to_xml
from src.helpers.balance_calculator import update_balances
import pandas as pd

ACCOUNT_NUMBER = "5009000004100"
YEAR = 2024
START_BALANCE = 1000.0

get_client = GetClient(DB_CONFIG)
transaction_router = TransactionRouter(TREANSACTION_CODE, DB_CONFIG)

account_correspondences, account_details, customer_id, account_type, account_rp = \
    get_client.get_client_details(ACCOUNT_NUMBER)

account = {
    'account_correspondences': account_correspondences,
    'account_detail': account_details,
    'customer_id': customer_id,
    'account_type': account_type,
    'account_rp': account_rp
}

transaction_router.clear_cache()
transaction_router.get_transactions(account, YEAR, START_BALANCE)

transaction_router.stacked_df['transaction_date'] = pd.to_datetime(
    transaction_router.stacked_df['transaction_date']
)
transaction_router.stacked_df = transaction_router.stacked_df.sort_values(
    by='transaction_date', ascending=False
)

file_name = f"{ACCOUNT_NUMBER}_{YEAR}.xml"
output_path = f"output/{ACCOUNT_NUMBER}"

write_transaction_details_to_xml(
    transaction_router.stacked_df, output_path, file_name, "zaeazeazeaz", "fgfgfgfgfgfgf"
)
update_balances(file_name, output_path, START_BALANCE)

print(f"XML genere : {output_path}/{file_name}")