from datetime import datetime
import pandas as pd
from typing import Union

from src.helpers.utils import clean_dataframe
from src.db.connection import DatabaseConnection
from src.db.query_executor import QueryExecutor
from src.helpers.logger_manager import LoggerManager

class EQAccountant(DatabaseConnection):
    def __init__(self, db_config: dict, log_enabled: bool = True) -> None:

        super().__init__(db_config['server'], db_config['database'], db_config['username'], db_config['password'])
        self.logger_manager = LoggerManager(log_enabled)
        self.query_executor = QueryExecutor(self.connection)
        self._log('info', "EQAccountant initialized with logging enabled: %s", log_enabled)

        # ✅ Ensures a completely new, independent DataFrame reference
        self.accountant_transactions = pd.DataFrame().copy(deep=True)

    def _log(self, level, message, *args, **kwargs):

        self.logger_manager.log(level, message, *args, **kwargs)      
    
    def get_accountant_transactions(self, account_number: str, year: str, max_attempts: int = 1) -> pd.DataFrame:
        self._log('info', "Starting to retrieve accountant's transactions for account: %s, year: %s", account_number, year)

        self.accountant_transactions = pd.DataFrame().copy(deep=True)

        df = pd.DataFrame()  # ✅ Ensure df is always a fresh DataFrame

        try:
            self.connect()  # Ensure database connection

            table_name = (
                f"[MISDW].[HIST].[EQA_POSTINGS_{year}]"
            )
            self._log('debug', "Determined table name: %s", table_name)

            table_name_cours_de_change = (
                f"[MISDW].[HIST].[EQA_CURRENCIES_{year}]"
            )

            query = f"""
            SELECT
                'EQ' AS ACCOUNTANT_SOURCE,
                EQ_ACCOUNTANT.SAPBR AS APP_SOURCE_CODE,
                TRIM(EQ_T24.GLOBUS_ACCT_NUMBER) AS T24_ACCOUNT,
                TRIM(EQ_T24.ALTERNATIVE_NUMBER) AS EQ_ACCOUNT,
                TRIM(EQ_ORACLE.NEEAN) AS ORACLE_ACCOUNT,
                TRIM(CAST(EQ_ACCOUNTANT.SADRF AS VARCHAR)) AS TRANSACTION_REF,
                EQ_ACCOUNTANT.SAPSQ AS TRANSACTION_SEQ,
                TRIM(CAST(EQ_ACCOUNTANT.SAPOD AS VARCHAR)) AS TRANSACTION_DATE,
                FORMAT(EQ_ACCOUNTANT.SATSTP, 'yyyy-MM-dd HH.mm') AS TRANSACTION_DATE_TS,
                EQ_ACCOUNTANT.SACCY AS TRANSACTION_CURRENCY,
                --EQ_ACCOUNTANT.SAAMA / POWER(10, CURRENCY.NO_OF_DECIMALS) AS TRANSACTION_AMOUNT,          
                ROUND((EQ_ACCOUNTANT.SAAMA * CURRENCIES.C8SPT) ,3) / CURRENCIES.C8PWD AS TRANSACTION_AMOUNT_LCY,
                EQ_ACCOUNTANT.SAAMA / POWER(10, CURRENCIES.C8CED) AS TRANSACTION_AMOUNT,
                --'NA' AS TRANSACTION_AMOUNT_FCY,
                EQ_ACCOUNTANT.SATCD AS TRANSACTION_CODE_ATB,
                EQA_TRANSACTION_CODE.CTTCN AS TRANSACTION_DESC_ATB
            FROM {table_name} AS EQ_ACCOUNTANT
            LEFT JOIN [MISDW].[TRG].[EQA_TRANSACTION_CODE] AS EQA_TRANSACTION_CODE ON EQA_TRANSACTION_CODE.CTTCD = EQ_ACCOUNTANT.SATCD
            LEFT JOIN [MISDW].[TRG].[T24_FATB_ALTERNATE_ACCO000] AS EQ_T24 ON EQ_T24.ALTERNATIVE_NUMBER = EQ_ACCOUNTANT.SAAB + EQ_ACCOUNTANT.SAAN + EQ_ACCOUNTANT.SAAS
            LEFT JOIN [MISDW].[TRG].[EQA_ACC_EXTERNAL_ACCOUNT_NUMBER] AS EQ_ORACLE ON EQ_ORACLE.NEAB + EQ_ORACLE.NEAN + EQ_ORACLE.NEAS = EQ_T24.ALTERNATIVE_NUMBER
            -- cours de change
            --LEFT JOIN [MISDW].[TRG].[T24_FBNK_CURRENCY] AS CURRENCY ON CURRENCY.CURRENCY_CODE = EQ_ACCOUNTANT.SACCY
            LEFT JOIN {table_name_cours_de_change} AS CURRENCIES ON CURRENCIES.C8CCY = EQ_ACCOUNTANT.SACCY
            WHERE
                EQ_T24.ALTERNATIVE_NUMBER = '{account_number}'
                AND '20' + SUBSTRING(CONVERT(VARCHAR, EQ_ACCOUNTANT.SAPOD), 2, 2) = '{year}'
            """

            self._log('debug', "Constructed SQL query: %s", query)

            result_df = self.query_executor.retry_query_execution(query, self.connection, max_attempts=max_attempts)

            # ✅ Assign only if the query returns valid data
            if result_df is not None and not result_df.empty:
                self._log('info', "Query executed successfully. Accountant's transactions retrieved for the account.")
                df = result_df.copy(deep=True)  # ✅ Ensure fresh reference
            else:
                self._log('warning', "No accountant's transactions data found for account: %s in year: %s", account_number, year)

        except Exception as e:
            self._log('error', "Error retrieving accountant's transactions for account: %s, year: %s. Error: %s", account_number, year, e)
            raise

        finally:
            self._log('info', "Closing database connection.")
            self.disconnect()

        # ✅ Ensure `self.accountant_transactions` is always a fresh reference
        self._log('info', "Returning cleaned DataFrame.")
        self.accountant_transactions = clean_dataframe(df).copy(deep=True)
