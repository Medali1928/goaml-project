from datetime import datetime
import pandas as pd
from typing import Union

from src.helpers.utils import clean_dataframe
from src.db.connection import DatabaseConnection
from src.db.query_executor import QueryExecutor
from src.helpers.logger_manager import LoggerManager

class T24Accountant(DatabaseConnection):
    def __init__(self, db_config: dict, log_enabled: bool = True) -> None:
        super().__init__(db_config['server'], db_config['database'], db_config['username'], db_config['password'])
        self.logger_manager = LoggerManager(log_enabled)
        self.query_executor = QueryExecutor(self.connection)
        self._log('info', "T24Accountant initialized with logging enabled: %s", log_enabled)
        
        # Initialize with a fresh DataFrame
        self.accountant_transactions = pd.DataFrame().copy(deep=True)

    def _log(self, level, message, *args, **kwargs):
        self.logger_manager.log(level, message, *args, **kwargs)      
    
    def get_accountant_transactions(self, account_number: str, year: str, max_attempts: int = 1) -> pd.DataFrame:
        self._log('info', "Starting to retrieve T24 accountant's transactions for account: %s, year: %s", account_number, year)

        self.accountant_transactions = pd.DataFrame().copy(deep=True)
        df = pd.DataFrame()  # Fresh DataFrame for results

        try:
            self.connect()  # Ensure database connection

            # Currently using the same table for all years as per requirements
            table_name = "[MISDW].[TRG].[T24_FATB_STMT_ENTRY_2024]"
            self._log('debug', "Using table: %s", table_name)

            query = f"""
            SELECT
                'T24' AS ACCOUNTANT_SOURCE,
                T24_ACCOUNTANT.SYSTEM_ID AS APP_SOURCE_CODE,
                T24_ACCOUNTANT.ACCOUNT_NUMBER AS T24_ACCOUNT,
                --EQ_T24.ALTERNATIVE_NUMBER AS EQ_ACCOUNT,
                'NA' AS EQ_ACCOUNT,
                --EQ_ORACLE.NEEAN AS ORACLE_ACCOUNT,
                'NA' AS ORACLE_ACCOUNT,
                T24_ACCOUNTANT.TRANS_REFERENCE AS TRANSACTION_REF,
                'NA' AS TRANSACTION_SEQ,
                T24_ACCOUNTANT.VALUE_DATE AS TRANSACTION_DATE,
                T24_ACCOUNTANT.SYSTEM_DATE_TIME AS TRANSACTION_DATE_TS,
                T24_ACCOUNTANT.CURRENCY AS TRANSACTION_CURRENCY,
                --'NA' AS TRANSACTION_AMOUNT,
                T24_ACCOUNTANT.AMOUNT_LCY AS TRANSACTION_AMOUNT_LCY,
                T24_ACCOUNTANT.AMOUNT_FCY AS TRANSACTION_AMOUNT,
                T24_ACCOUNTANT.TRANSACTION_CODE AS TRANSACTION_CODE_ATB,
                'NA' AS TRANSACTION_DESC_ATB
            FROM {table_name} AS T24_ACCOUNTANT
            --INNER JOIN [MISDW].[TRG].[T24_FATB_ALTERNATE_ACCO000] AS EQ_T24 ON EQ_T24.GLOBUS_ACCT_NUMBER = T24_ACCOUNTANT.ACCOUNT_NUMBER
            --INNER JOIN [MISDW].[TRG].[EQA_ACC_EXTERNAL_ACCOUNT_NUMBER] AS EQ_ORACLE ON EQ_ORACLE.NEAB + EQ_ORACLE.NEAN + EQ_ORACLE.NEAS = EQ_T24.ALTERNATIVE_NUMBER
            WHERE
                T24_ACCOUNTANT.ACCOUNT_NUMBER = '{account_number}'
                AND SUBSTRING(T24_ACCOUNTANT.VALUE_DATE, 1, 4) = '{year}'
            """

            self._log('debug', "Constructed SQL query: %s", query)

            result_df = self.query_executor.retry_query_execution(query, self.connection, max_attempts=max_attempts)

            if result_df is not None and not result_df.empty:
                self._log('info', "Query executed successfully. T24 accountant's transactions retrieved for the account.")
                df = result_df.copy(deep=True)
            else:
                self._log('warning', "No T24 accountant's transactions data found for account: %s in year: %s", account_number, year)

        except Exception as e:
            self._log('error', "Error retrieving T24 accountant's transactions for account: %s, year: %s. Error: %s", account_number, year, e)
            raise

        finally:
            self._log('info', "Closing database connection.")
            self.disconnect()

        self._log('info', "Returning cleaned DataFrame.")
        self.accountant_transactions = clean_dataframe(df).copy(deep=True)
        #return self.accountant_transactions