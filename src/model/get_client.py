from src.model.get_client_T24 import GetClientT24
from src.model.get_client_EQ import GetClientEQ
from src.db.connection import DatabaseConnection
import pandas as pd

class GetClient(DatabaseConnection):
    """
    Class to retrieve client details from different systems (T24 or EQ).
    Inherits from DatabaseConnection to share database connectivity.

    Attributes:
        getClientEQ (GetClientEQ): Instance of GetClientEQ for EQ system.
        getClientT24 (GetClientT24): Instance of GetClientT24 for T24 system.
    """

    def __init__(self, db_config: dict):
        """
        Initialize the GetClient class with database credentials and 
        create instances for T24 and EQ client retrieval.

        Args:
            server (str): Database server address.
            database (str): Database name.
            username (str): Username for authentication.
            password (str): Password for authentication.
        """
        #super().__init__(db_config)
        self.getClientEQ = GetClientEQ(db_config)
        self.getClientT24 = GetClientT24(db_config, log_enabled=True)

    def get_client_details(self, account: str) -> tuple:
        """
        Retrieve client details for the given account number. Checks the T24 system first.
        If not found, retrieves from the EQ system.

        Args:
            account (str): The account number to retrieve details for.

        Returns:
            tuple: A tuple containing account details, customer ID, account type, and account-related persons.
        """
        try:
            # Check if account exists in T24
            if self.getClientT24.account_status_lookup(account):
                account_data_t24: pd.DataFrame = self.getClientT24.get_account(account) # Active
            else:
                account_data_t24: pd.DataFrame = self.getClientT24.get_account_closed(account) # Closed
            if not account_data_t24.empty:
                return self.getClientT24.get_client(account)

            # Fall back to EQ system
            account_data_eq: pd.DataFrame = self.getClientEQ.get_account(account)
            if not account_data_eq.empty:
                return self.getClientEQ.get_client(account)

            # Handle case where account is not found in either system
            raise ValueError(f"Account {account} not found in T24 or EQ systems.")

        except Exception as e:
            # Log and propagate exceptions (or handle as needed)
            raise RuntimeError(f"Failed to retrieve client details for account {account}: {e}")
