import time
from tqdm import tqdm
from typing import List
import pandas as pd
from typing import Dict

from src.helpers.xmlStructure import XML
from src.helpers.utils import clean_dataframe
from src.db.connection import DatabaseConnection
from src.db.query_executor import QueryExecutor
from src.model.get_client import GetClient
from src.helpers.logger_manager import LoggerManager


class Cheque(DatabaseConnection):
    def __init__(self, db_config: dict, log_enabled: bool = True) -> None:

        super().__init__(db_config['server'], db_config['database'], db_config['username'], db_config['password'])

        self.db_config = db_config

        self.logger_manager = LoggerManager(log_enabled)
        self.query_executor = QueryExecutor(self.connection)

        self.cheque_transactions = pd.DataFrame()
        self.cheque_transactions_to_process = pd.DataFrame()
        self.cheque_transactions_processed = pd.DataFrame()

    def _log(self, level, message, *args, **kwargs):
        """Log a message if logging is enabled using the logger manager."""
        self.logger_manager.log(level, message, *args, **kwargs)

    def get_cheque_cc(self, account: str, year: str, max_attempts: int = 3) -> pd.DataFrame:

        self._log('info', "Starting cheque_cc's transactions retrieval for account: %s, year: %s", account, year)
        self.connect()

        # Splitting into BR, BN, SFX
        BR = account[0:4]
        BN = account[4:10]
        SFX = account[10:13]

        df = pd.DataFrame()

        try:
            query = f"""
            -- Cheque
            -- ATB -> ATB
            -- Emis
            SELECT
                'IBANK_Cheque' AS TYPE_OP,
                'Y' AS PART_1_IS_MY_CLIENT,
                'ACCOUNT' AS PART_1_TYPE,
                'I' AS PART_1_ROLE,
                EA1.NEAB AS PART_1_BR,
                EA1.NEAN AS PART_1_BN,
                EA1.NEAS AS PART_1_SFX,
                
                'A' AS FUND_CODE_1,
                COD_DEV AS CURRENCY_CODE_1,
                'TN' AS COUNTRY_1,
                LOCAL_AMOUNT AS FORRIGNN_AMOUNT_1,
                
                'Y' AS PART_2_IS_MY_CLIENT,
                'ACCOUNT' AS PART_2_TYPE,
                'B' AS PART_2_ROLE,
                EA2.NEAB + EA2.NEAN + EA2.NEAS AS PART_2_ACCOUNT,
                '' AS PART_2_DETAILS,
                
                'A' AS FUND_CODE_2,
                COD_DEV AS CURRENCY_CODE_2,
                'TN' AS COUNTRY_2,
                LOCAL_AMOUNT AS FORRIGNN_AMOUNT_2,
                
                '30' + '/' + TRIM(TRANSACTION_NUMBER) + '/' + FORMAT(TRANSACTION_DATE, 'dd MM yyyy') AS TRANSACTIONNUMBER,
                'TN' AS TRANSACTIONLOCATION,
                CONVERT(VARCHAR, TRANSACTION_DATE, 23) + 'T00:00:00' AS DATE_TRANSACTION,
                TRANS_CODE_DESC AS TRANS_CODE_DESC_ATB,
                TRANS_CODE AS TRANSMODE_CODE_ATB,
                'B126' AS TRANSMODE_CODE_GOAML,
                LOCAL_AMOUNT AS AMOUNT_LOCAL,
                'C' AS TRANSACTION_STATUS_CODE
                
            FROM
                [MISDW].[GO_AML].[IBANK_CHQ_EMIS]
            LEFT JOIN
                [MISDW].[GO_AML].[EQA_EXTERNAL_ACCOUNT_NUMBER] AS EA1 ON EA1.NEEAN = NUM_CPT
            LEFT JOIN
                [MISDW].[GO_AML].[EQA_EXTERNAL_ACCOUNT_NUMBER] AS EA2 ON EA2.NEEAN = BENIF_CPT
            WHERE
                YEAR(TRANSACTION_DATE) = '{year}' AND
                EA1.NEAB = '{BR}' AND
                EA1.NEAN = '{BN}' AND
                EA1.NEAS = '{SFX}'
                
            UNION

            -- Recu
            SELECT
                'IBANK_Cheque' AS TYPE_OP,
                'Y' AS PART_1_IS_MY_CLIENT,
                'ACCOUNT' AS PART_1_TYPE,
                'B' AS PART_1_ROLE,
                EA1.NEAB AS PART_1_BR,
                EA1.NEAN AS PART_1_BN,
                EA1.NEAS AS PART_1_SFX,
                
                'A' AS FUND_CODE_1,
                COD_DEV AS CURRENCY_CODE_1,
                'TN' AS COUNTRY_1,
                LOCAL_AMOUNT AS FORRIGNN_AMOUNT_1,
                
                'Y' AS PART_2_IS_MY_CLIENT,
                'ACCOUNT' AS PART_2_TYPE,
                'I' AS PART_2_ROLE,
                EA2.NEAB + EA2.NEAN + EA2.NEAS AS PART_2_ACCOUNT,
                '' AS PART_2_DETAILS,
                
                'A' AS FUND_CODE_2,
                COD_DEV AS CURRENCY_CODE_2,
                'TN' AS COUNTRY_2,
                LOCAL_AMOUNT AS FORRIGNN_AMOUNT_2,
                
                '30' + '/' + TRIM(TRANSACTION_NUMBER) + '/' + FORMAT(TRANSACTION_DATE, 'dd MM yyyy') AS TRANSACTIONNUMBER,
                'TN' AS TRANSACTIONLOCATION,
                CONVERT(VARCHAR, TRANSACTION_DATE, 23) + 'T00:00:00' AS DATE_TRANSACTION,
                TRANS_CODE_DESC AS TRANS_CODE_DESC_ATB,
                TRANS_CODE AS TRANSMODE_CODE_ATB,
                'B126' AS TRANSMODE_CODE_GOAML,
                LOCAL_AMOUNT AS AMOUNT_LOCAL,
                'C' AS TRANSACTION_STATUS_CODE
                
            FROM
                [MISDW].[GO_AML].[IBANK_CHQ_RECU]
            LEFT JOIN
                [MISDW].[GO_AML].[EQA_EXTERNAL_ACCOUNT_NUMBER] AS EA1 ON EA1.NEEAN = NUM_CPT
            LEFT JOIN
                [MISDW].[GO_AML].[EQA_EXTERNAL_ACCOUNT_NUMBER] AS EA2 ON EA2.NEEAN = BENIF_CPT
            WHERE
                YEAR(TRANSACTION_DATE) = '{year}' AND
                EA1.NEAB = '{BR}' AND
                EA1.NEAN = '{BN}' AND
                EA1.NEAS = '{SFX}'            
            """

            # Retry logic for query execution
            self._log('info', "Executing query with max_attempts: %d", max_attempts)
            df = self.query_executor.retry_query_execution(query, self.connection, max_attempts=max_attempts)

            if df.empty:
                self._log('warning', "No cheque_cc's transactions data found for the account: %s, year: %s", account, year)
            else:
                if self.cheque_transactions.empty:
                    self.cheque_transactions = clean_dataframe(df)
                else:
                    self.cheque_transactions = pd.concat([self.cheque_transactions, clean_dataframe(df)], ignore_index=True)

                self._log('info', "Query executed successfully; cheque_cc's transactions data retrieved for the account.")
        except Exception as e:
            self._log('error', "Error retrieving cheque_cc's transactions data for the account: %s, year: %s, error: %s", account, year, e)
            raise
        finally:
            self._log('info', "Closing database connection.")
            self.disconnect()

        self._log('info', "Returning cleaned DataFrame.")

    def get_cheque_ca(self, account: str, year: str, max_attempts: int = 3) -> pd.DataFrame:

        self._log('info', "Starting cheque_ca's transactions retrieval for account: %s, year: %s", account, year)
        self.connect()

        # Splitting into BR, BN, SFX
        BR = account[0:4]
        BN = account[4:10]
        SFX = account[10:13]

        df = pd.DataFrame()

        try:
            query = f"""
            -- Cheque
            -- ATB -> AB
            -- Emis
            SELECT
                'IBANK_Cheque' AS TYPE_OP,
                'Y' AS PART_1_IS_MY_CLIENT,
                'ACCOUNT' AS PART_1_TYPE,
                'I' AS PART_1_ROLE,
                EA1.NEAB AS PART_1_BR,
                EA1.NEAN AS PART_1_BN,
                EA1.NEAS AS PART_1_SFX,
                
                'A' AS FUND_CODE_1,
                COD_DEV AS CURRENCY_CODE_1,
                'TN' AS COUNTRY_1,
                LOCAL_AMOUNT AS FORRIGNN_AMOUNT_1,
                
                'N' AS PART_2_IS_MY_CLIENT,
                'ACCOUNT' AS PART_2_TYPE,
                'B' AS PART_2_ROLE,
                '' AS PART_2_ACCOUNT,
                '<IB_account>' +
                    '<institution_name>' + ISNULL(LIBBQE, 'N.A') + '</institution_name>' +
                    '<swift>' + ISNULL(ADRSWIFT, 'N.A') + '</swift>' +
                    '<institution_country>TN</institution_country>' +
                    '<account>' + ISNULL(BENIF_RIB, 'N.A') + '</account>' +
                '</IB_account>' AS PART_2_DETAILS,
                
                'A' AS FUND_CODE_2,
                COD_DEV AS CURRENCY_CODE_2,
                'TN' AS COUNTRY_2,
                LOCAL_AMOUNT AS FORRIGNN_AMOUNT_2,
                
                '30' + '/' + TRIM(TRANSACTION_NUMBER) + '/' + FORMAT(TRANSACTION_DATE, 'dd MM yyyy') AS TRANSACTIONNUMBER,
                'TN' AS TRANSACTIONLOCATION,
                CONVERT(VARCHAR, TRANSACTION_DATE, 23) + 'T00:00:00' AS DATE_TRANSACTION,
                TRANS_CODE_DESC AS TRANS_CODE_DESC_ATB,
                TRANS_CODE AS TRANSMODE_CODE_ATB,
                'B126' AS TRANSMODE_CODE_GOAML,
                LOCAL_AMOUNT AS AMOUNT_LOCAL,
                'C' AS TRANSACTION_STATUS_CODE
                
                
            FROM
                [MISDW].[GO_AML].[IBANK_CHQ_EMIS_TELECOMP]
            LEFT JOIN
                [MISDW].[GO_AML].[EQA_EXTERNAL_ACCOUNT_NUMBER] AS EA1 ON EA1.NEEAN = NUM_CPT
            LEFT JOIN
                [MISDW].[GO_AML].[BANQUE TN DETAILS] ON RIGHT('00' + CODBQE, 2) = RIGHT('00' + BENIF_CODE_BQE, 2)
            WHERE
                YEAR(TRANSACTION_DATE) = '{year}' AND
                EA1.NEAB = '{BR}' AND
                EA1.NEAN = '{BN}' AND
                EA1.NEAS = '{SFX}'
                

            UNION


            SELECT
                'IBANK_Cheque' AS TYPE_OP,
                'Y' AS PART_1_IS_MY_CLIENT,
                'ACCOUNT' AS PART_1_TYPE,
                'B' AS PART_1_ROLE,
                EA1.NEAB AS PART_1_BR,
                EA1.NEAN AS PART_1_BN,
                EA1.NEAS AS PART_1_SFX,
                
                'A' AS FUND_CODE_1,
                COD_DEV AS CURRENCY_CODE_1,
                'TN' AS COUNTRY_1,
                LOCAL_AMOUNT AS FORRIGNN_AMOUNT_1,
                
                'N' AS PART_2_IS_MY_CLIENT,
                'ACCOUNT' AS PART_2_TYPE,
                'I' AS PART_2_ROLE,
                '' AS PART_2_ACCOUNT,
                '<IB_account>' +
                    '<institution_name>' + ISNULL(LIBBQE, 'N.A') + '</institution_name>' +
                    '<swift>' + ISNULL(ADRSWIFT, 'N.A') + '</swift>' +
                    '<institution_country>TN</institution_country>' +
                    '<account>' + ISNULL(BENIF_RIB, 'N.A') + '</account>' +
                '</IB_account>' AS PART_2_DETAILS,
                
                'A' AS FUND_CODE_2,
                COD_DEV AS CURRENCY_CODE_2,
                'TN' AS COUNTRY_2,
                LOCAL_AMOUNT AS FORRIGNN_AMOUNT_2,
                
                '30' + '/' + TRIM(TRANSACTION_NUMBER) + '/' + FORMAT(TRANSACTION_DATE, 'dd MM yyyy') AS TRANSACTIONNUMBER,
                'TN' AS TRANSACTIONLOCATION,
                CONVERT(VARCHAR, TRANSACTION_DATE, 23) + 'T00:00:00' AS DATE_TRANSACTION,
                TRANS_CODE_DESC AS TRANS_CODE_DESC_ATB,
                TRANS_CODE AS TRANSMODE_CODE_ATB,
                'B126' AS TRANSMODE_CODE_GOAML,
                LOCAL_AMOUNT AS AMOUNT_LOCAL,
                'C' AS TRANSACTION_STATUS_CODE
                
                
            FROM
                [MISDW].[GO_AML].[IBANK_CHQ_RECU_TELECOMP]
            LEFT JOIN
                [MISDW].[GO_AML].[EQA_EXTERNAL_ACCOUNT_NUMBER] AS EA1 ON EA1.NEEAN = NUM_CPT
            LEFT JOIN
                [MISDW].[GO_AML].[BANQUE TN DETAILS] ON RIGHT('00' + CODBQE, 2) = RIGHT('00' + BENIF_CODE_BQE, 2)
            WHERE
                YEAR(TRANSACTION_DATE) = '{year}' AND
                EA1.NEAB = '{BR}' AND
                EA1.NEAN = '{BN}' AND
                EA1.NEAS = '{SFX}'
            """

            # Retry logic for query execution
            self._log('info', "Executing query with max_attempts: %d", max_attempts)
            df = self.query_executor.retry_query_execution(query, self.connection, max_attempts=max_attempts)

            if df.empty:
                self._log('warning', "No cheque_ca's transactions data found for the account: %s, year: %s", account, year)
            else:
                if self.cheque_transactions.empty:
                    self.cheque_transactions = clean_dataframe(df)
                else:
                    self.cheque_transactions = pd.concat([self.cheque_transactions, clean_dataframe(df)], ignore_index=True)
                    

                self._log('info', "Query executed successfully; cheque_ca's transactions data retrieved for the account.")
        except Exception as e:
            self._log('error', "Error retrieving cheque_ca's transactions data for the account: %s, year: %s, error: %s", account, year, e)
            raise
        finally:
            self._log('info', "Closing database connection.")
            self.disconnect()

        self._log('info', "Returning cleaned DataFrame.")
    # OK
    def get_cheque_cc_ce(self, account: str, year: str, max_attempts: int = 1) -> pd.DataFrame:

        #self.virement_transactions = pd.DataFrame()
        self._log('info', "Starting Cheque_cc emis' transactions retrieval for account: %s, year: %s", account, year)
        self.connect()

        df = pd.DataFrame()

        try:
            query = f"""
            SELECT
                'Y' AS PART_1_IS_MY_CLIENT,
                'I' AS PART_1_ROLE,
                CHEQUE_EMIS_MEME_BQE.BRN_ACC + CHEQUE_EMIS_MEME_BQE.ACCOUNT_ID + CHEQUE_EMIS_MEME_BQE.SFX_ACC AS EQ_ACCOUNT,
                CHEQUE_EMIS_MEME_BQE.POSTING_REF AS TRANSACTION_REF,
                CHEQUE_EMIS_MEME_BQE.POSTING_DATE AS TRANSACTION_DATE,
                
                'A' AS FUND_CODE_1,
                CHEQUE_EMIS_MEME_BQE.COD_DEV AS CURRENCY_CODE_1,
                'TN' AS COUNTRY_1,
                CHEQUE_EMIS_MEME_BQE.MNT_OPE AS FOREIGN_AMOUNT_1,
                            
                'Y' AS PART_2_IS_MY_CLIENT,
                'ACCOUNT' AS PART_2_TYPE,
                'B' AS PART_2_ROLE,
                EQ_ORACLE.NEAB + EQ_ORACLE.NEAN + EQ_ORACLE.NEAS AS PART_2_ACCOUNT,
                '' AS PART_2_DETAILS,
                
                'A' AS FUND_CODE_2,
                CHEQUE_EMIS_MEME_BQE.COD_DEV AS CURRENCY_CODE_2,
                'TN' AS COUNTRY_2,
                CHEQUE_EMIS_MEME_BQE.MNT_OPE AS FOREIGN_AMOUNT_2,
                
                '30' + '/' + CHEQUE_EMIS_MEME_BQE.TRANSACTION_NUMBER + '/' +
                    CAST(YEAR(CHEQUE_EMIS_MEME_BQE.POSTING_DATE) AS NVARCHAR(4)) + ' ' +
                    RIGHT('0' + CAST(MONTH(CHEQUE_EMIS_MEME_BQE.POSTING_DATE) AS NVARCHAR(2)), 2) + ' ' +
                    RIGHT('0' + CAST(DAY(CHEQUE_EMIS_MEME_BQE.POSTING_DATE) AS NVARCHAR(2)), 2) AS TRANSACTION_NUMBER,
                'TN' AS TRANSACTION_LOCATION,
                CAST(YEAR(CHEQUE_EMIS_MEME_BQE.POSTING_DATE) AS NVARCHAR(4)) + '-' +
                    RIGHT('0' + CAST(MONTH(CHEQUE_EMIS_MEME_BQE.POSTING_DATE) AS NVARCHAR(2)), 2) + '-' +
                    RIGHT('0' + CAST(DAY(CHEQUE_EMIS_MEME_BQE.POSTING_DATE) AS NVARCHAR(2)), 2) + 'T00:00:00' AS DATE_TRANSACTION,
                CHEQUE_EMIS_MEME_BQE.TRANS_CODE_DESC AS TRANS_CODE_DESC_ATB,
                CHEQUE_EMIS_MEME_BQE.TRANS_CODE AS TRANSMODE_CODE_ATB,
                'B117' AS TRANSACTION_CODE_GOAML,
                CHEQUE_EMIS_MEME_BQE.MNT_OPE AS AMOUNT_LOCAL,
                'C' AS TRANSACTION_STATUS_CODE,

                ' CHEQUE_EMIS_MEME_BQE ' + CHEQUE_EMIS_MEME_BQE.BEN_OPE AS NAR,

                'CHEQUE_EMIS_MEME_BQE' AS SOURCE
                
            FROM [MISDW].[GO_AML].[IBANK_CHEQUE_EMIS_MEME_BQE] AS CHEQUE_EMIS_MEME_BQE
            LEFT JOIN [MISDW].[TRG].[EQA_ACC_EXTERNAL_ACCOUNT_NUMBER] AS EQ_ORACLE ON EQ_ORACLE.NEEAN = CHEQUE_EMIS_MEME_BQE.BENIF_NUMCPT
				WHERE
					YEAR(CHEQUE_EMIS_MEME_BQE.POSTING_DATE) = '{year}'
					AND CHEQUE_EMIS_MEME_BQE.BRN_ACC + CHEQUE_EMIS_MEME_BQE.ACCOUNT_ID + CHEQUE_EMIS_MEME_BQE.SFX_ACC = '{account}'
            """

            # Retry logic for query execution
            self._log('info', "Executing query with max_attempts: %d", max_attempts)
            df = self.query_executor.retry_query_execution(query, self.connection, max_attempts=max_attempts)

            if df.empty:
                self._log('warning', "No Cheque_cc emis' transactions data found for the account: %s, year: %s", account, year)
            else:
                print('-------------------------------------------------------')
                print(len(df))
                print('-------------------------------------------------------')
                self.cheque_transactions = pd.concat(
                    [self.cheque_transactions.copy(), clean_dataframe(df)], 
                    ignore_index=True
                ).copy()
              

                self._log('info', "Query executed successfully; Cheque_cc emis' transactions data retrieved for the account.")
        except Exception as e:
            self._log('error', "Error retrieving Cheque_cc emis' transactions data for the account: %s, year: %s, error: %s", account, year, e)
            raise
        finally:
            self._log('info', "Closing database connection.")
            self.disconnect()

        self._log('info', "Returning cleaned DataFrame.")
    # ok
    def get_cheque_cc_cr(self, account: str, year: str, max_attempts: int = 1) -> pd.DataFrame:

        #self.virement_transactions = pd.DataFrame()
        self._log('info', "Starting Cheque_cc recu's transactions retrieval for account: %s, year: %s", account, year)
        self.connect()

        df = pd.DataFrame()

        try:
            query = f"""
            SELECT
                'Y' AS PART_1_IS_MY_CLIENT,
                'B' AS PART_1_ROLE,
                CHEQUE_RECU_MEME_BQE.BRN_ACC + CHEQUE_RECU_MEME_BQE.ACCOUNT_ID + CHEQUE_RECU_MEME_BQE.SFX_ACC AS EQ_ACCOUNT,
                CHEQUE_RECU_MEME_BQE.POSTING_REF AS TRANSACTION_REF,
                CHEQUE_RECU_MEME_BQE.POSTING_DATE AS TRANSACTION_DATE,
                
                'A' AS FUND_CODE_1,
                CHEQUE_RECU_MEME_BQE.COD_DEV AS CURRENCY_CODE_1,
                'TN' AS COUNTRY_1,
                CHEQUE_RECU_MEME_BQE.MNT_OPE AS FOREIGN_AMOUNT_1,
                            
                'Y' AS PART_2_IS_MY_CLIENT,
                'ACCOUNT' AS PART_2_TYPE,
                'I' AS PART_2_ROLE,
                EQ_ORACLE.NEAB + EQ_ORACLE.NEAN + EQ_ORACLE.NEAS AS PART_2_ACCOUNT,
                '' AS PART_2_DETAILS,
                
                'A' AS FUND_CODE_2,
                CHEQUE_RECU_MEME_BQE.COD_DEV AS CURRENCY_CODE_2,
                'TN' AS COUNTRY_2,
                CHEQUE_RECU_MEME_BQE.MNT_OPE AS FOREIGN_AMOUNT_2,
                
                '30' + '/' + CHEQUE_RECU_MEME_BQE.TRANSACTION_NUMBER + '/' +
                    CAST(YEAR(CHEQUE_RECU_MEME_BQE.POSTING_DATE) AS NVARCHAR(4)) + ' ' +
                    RIGHT('0' + CAST(MONTH(CHEQUE_RECU_MEME_BQE.POSTING_DATE) AS NVARCHAR(2)), 2) + ' ' +
                    RIGHT('0' + CAST(DAY(CHEQUE_RECU_MEME_BQE.POSTING_DATE) AS NVARCHAR(2)), 2) AS TRANSACTION_NUMBER,
                'TN' AS TRANSACTION_LOCATION,
                CAST(YEAR(CHEQUE_RECU_MEME_BQE.POSTING_DATE) AS NVARCHAR(4)) + '-' +
                    RIGHT('0' + CAST(MONTH(CHEQUE_RECU_MEME_BQE.POSTING_DATE) AS NVARCHAR(2)), 2) + '-' +
                    RIGHT('0' + CAST(DAY(CHEQUE_RECU_MEME_BQE.POSTING_DATE) AS NVARCHAR(2)), 2) + 'T00:00:00' AS DATE_TRANSACTION,
                CHEQUE_RECU_MEME_BQE.TRANS_CODE_DESC AS TRANS_CODE_DESC_ATB,
                CHEQUE_RECU_MEME_BQE.TRANS_CODE AS TRANSMODE_CODE_ATB,
                'B117' AS TRANSACTION_CODE_GOAML,
                CHEQUE_RECU_MEME_BQE.MNT_OPE AS AMOUNT_LOCAL,
                'C' AS TRANSACTION_STATUS_CODE,

                'CHEQUE_RECU_MEME_BQE - INITIATEUR_OPE' + CHEQUE_RECU_MEME_BQE.INITIATEUR_OPE AS NAR,

                'CHEQUE_RECU_MEME_BQE' AS SOURCE
                
            FROM [MISDW].[GO_AML].[IBANK_CHEQUE_RECU_MEME_BQE] AS CHEQUE_RECU_MEME_BQE
            LEFT JOIN [MISDW].[TRG].[EQA_ACC_EXTERNAL_ACCOUNT_NUMBER] AS EQ_ORACLE ON EQ_ORACLE.NEEAN = CHEQUE_RECU_MEME_BQE.INITIATEUR_NYMCPT
				WHERE
					YEAR(CHEQUE_RECU_MEME_BQE.POSTING_DATE) = '{year}'
					AND CHEQUE_RECU_MEME_BQE.BRN_ACC + CHEQUE_RECU_MEME_BQE.ACCOUNT_ID + CHEQUE_RECU_MEME_BQE.SFX_ACC = '{account}'
            """

            # Retry logic for query execution
            self._log('info', "Executing query with max_attempts: %d", max_attempts)
            df = self.query_executor.retry_query_execution(query, self.connection, max_attempts=max_attempts)

            if df.empty:
                self._log('warning', "No Cheque_cc recu's transactions data found for the account: %s, year: %s", account, year)
            else:
                print('-------------------------------------------------------')
                print(len(df))
                print('-------------------------------------------------------')
                self.cheque_transactions = pd.concat(
                    [self.cheque_transactions.copy(), clean_dataframe(df)], 
                    ignore_index=True
                ).copy()
                

                self._log('info', "Query executed successfully; Cheque_cc recu' transactions data retrieved for the account.")
        except Exception as e:
            self._log('error', "Error retrieving Cheque_cc recu' transactions data for the account: %s, year: %s, error: %s", account, year, e)
            raise
        finally:
            self._log('info', "Closing database connection.")
            self.disconnect()

        self._log('info', "Returning cleaned DataFrame.")


    # ok
    def get_cheque_ca_ce(self, account: str, year: str, max_attempts: int = 1) -> pd.DataFrame:

        #self.virement_transactions = pd.DataFrame()
        self._log('info', "Starting Cheque_ca emis' transactions retrieval for account: %s, year: %s", account, year)
        self.connect()

        df = pd.DataFrame()

        try:
            query = f"""
            SELECT
                'Y' AS PART_1_IS_MY_CLIENT,
                'I' PART_1_ROLE,
                'ACCOUNT' AS PART_1_TYPE,
                CHEQUE_EMIS.BRN_ACC + CHEQUE_EMIS.ACCOUNT_ID + CHEQUE_EMIS.SFX_ACC AS EQ_ACCOUNT,
                CHEQUE_EMIS.POSTING_REF AS TRANSACTION_REF,
                CHEQUE_EMIS.POSTING_DATE AS TRANSACTION_DATE,
                
                'A' AS FUND_CODE_1,
                CHEQUE_EMIS.COD_DEV AS CURRENCY_CODE_1,
                'TN' AS COUNTRY_1,
                CHEQUE_EMIS.MNT_OPE AS FOREIGN_AMOUNT_1,
                
                'N' AS PART_2_IS_MY_CLIENT,
                'ACCOUNT' AS PART_2_TYPE,
                'B' AS PART_2_ROLE,
                '' AS PART_2_ACCOUNT,
                '<IB_account>' +
                    '<institution_name>' + ISNULL(BANQUE_TN_DETAILS.LIBBQE, 'N.A') + '</institution_name>' +
                    '<swift>' + ISNULL(BANQUE_TN_DETAILS.ADRSWIFT, 'N.A') + '</swift>' +
                    '<institution_country>TN</institution_country>' +
                    '<account>' + ISNULL(CHEQUE_EMIS.BENIF_RIB, 'N.A') + '</account>' +
                '</IB_account>' AS PART_2_DETAILS,
                
                'A' AS FUND_CODE_2,
                CHEQUE_EMIS.COD_DEV AS CURRENCY_CODE_2,
                'TN' AS COUNTRY_2,
                CHEQUE_EMIS.MNT_OPE AS FOREIGN_AMOUNT_2,
                
                '30' + '/' + CHEQUE_EMIS.TRANSACTION_NUMBER + '/' +
				CAST(YEAR(CHEQUE_EMIS.POSTING_DATE) AS NVARCHAR(4)) + ' ' +
				RIGHT('0' + CAST(MONTH(CHEQUE_EMIS.POSTING_DATE) AS NVARCHAR(2)), 2) + ' ' +
				RIGHT('0' + CAST(DAY(CHEQUE_EMIS.POSTING_DATE) AS NVARCHAR(2)), 2) AS TRANSACTION_NUMBER,
                'TN' AS TRANSACTION_LOCATION,
                CAST(YEAR(CHEQUE_EMIS.POSTING_DATE) AS NVARCHAR(4)) + '-' +
				RIGHT('0' + CAST(MONTH(CHEQUE_EMIS.POSTING_DATE) AS NVARCHAR(2)), 2) + '-' +
				RIGHT('0' + CAST(DAY(CHEQUE_EMIS.POSTING_DATE) AS NVARCHAR(2)), 2) + 'T00:00:00' AS DATE_TRANSACTION,
                CHEQUE_EMIS.TRANS_CODE_DESC AS TRANS_CODE_DESC_ATB,
                CHEQUE_EMIS.TRANS_CODE AS TRANSMODE_CODE_ATB,
                'B126' AS TRANSACTION_CODE_GOAML,
                CHEQUE_EMIS.MNT_OPE AS AMOUNT_LOCAL,
                'C' AS TRANSACTION_STATUS_CODE,

                ' CHEQUE_EMIS BENIF_NUMCPT ' + CHEQUE_EMIS.BENIF_NUMCPT AS NAR,

                'CHEQUE_EMIS' AS SOURCE
                
                
            FROM [MISDW].[GO_AML].[IBANK_CHEQUE_EMIS] AS CHEQUE_EMIS
            LEFT JOIN [MISDW].[GO_AML].[BANQUE TN DETAILS] AS BANQUE_TN_DETAILS ON RIGHT('00' + BANQUE_TN_DETAILS.CODBQE, 2) = RIGHT('00' + CHEQUE_EMIS.BENIF_CODE_BQE, 2)
            WHERE
				YEAR(CHEQUE_EMIS.POSTING_DATE) = {year}--'2024'
				AND CHEQUE_EMIS.BRN_ACC + CHEQUE_EMIS.ACCOUNT_ID + CHEQUE_EMIS.SFX_ACC = '{account}'--'5864062220500'
            """

            # Retry logic for query execution
            self._log('info', "Executing query with max_attempts: %d", max_attempts)
            df = self.query_executor.retry_query_execution(query, self.connection, max_attempts=max_attempts)

            if df.empty:
                self._log('warning', "No Cheque_ca emis' transactions data found for the account: %s, year: %s", account, year)
            else:
                print('-------------------------------------------------------')
                print(len(df))
                print('-------------------------------------------------------')
                #self.cheque_transactions = pd.concat([self.cheque_transactions, clean_dataframe(df)], ignore_index=True)
                self.cheque_transactions = pd.concat(
                    [self.cheque_transactions.copy(), clean_dataframe(df)], 
                    ignore_index=True
                ).copy()
                

                self._log('info', "Query executed successfully; Cheque_ca emis' transactions data retrieved for the account.")
        except Exception as e:
            self._log('error', "Error retrieving Cheque_ca emis' transactions data for the account: %s, year: %s, error: %s", account, year, e)
            raise
        finally:
            self._log('info', "Closing database connection.")
            self.disconnect()

        self._log('info', "Returning cleaned DataFrame.")
    # ok
    def get_cheque_ca_cr(self, account: str, year: str, max_attempts: int = 1) -> pd.DataFrame:

        #self.virement_transactions = pd.DataFrame()
        self._log('info', "Starting Cheque_ca recu' transactions retrieval for account: %s, year: %s", account, year)
        self.connect()

        df = pd.DataFrame()

        try:
            query = f"""
            SELECT
                'Y' AS PART_1_IS_MY_CLIENT,
                'B' PART_1_ROLE,
                'ACCOUNT' AS PART_1_TYPE,
                CHEQUE_RECU.BRN_ACC + CHEQUE_RECU.ACCOUNT_ID + CHEQUE_RECU.SFX_ACC AS EQ_ACCOUNT,
                CHEQUE_RECU.POSTING_REF AS TRANSACTION_REF,
                CHEQUE_RECU.POSTING_DATE AS TRANSACTION_DATE,
                
                'A' AS FUND_CODE_1,
                CHEQUE_RECU.COD_DEV AS CURRENCY_CODE_1,
                'TN' AS COUNTRY_1,
                CHEQUE_RECU.MNT_OPE AS FOREIGN_AMOUNT_1,
                
                'N' AS PART_2_IS_MY_CLIENT,
                'ACCOUNT' AS PART_2_TYPE,
                'I' AS PART_2_ROLE,
                '' AS PART_2_ACCOUNT,
                '<IB_account>' +
                    '<institution_name>' + ISNULL(BANQUE_TN_DETAILS.LIBBQE, 'N.A') + '</institution_name>' +
                    '<swift>' + ISNULL(BANQUE_TN_DETAILS.ADRSWIFT, 'N.A') + '</swift>' +
                    '<institution_country>TN</institution_country>' +
                    '<account>' + ISNULL(CHEQUE_RECU.INITIATEUR_RIB, 'N.A') + '</account>' +
                '</IB_account>' AS PART_2_DETAILS,
                
                'A' AS FUND_CODE_2,
                CHEQUE_RECU.COD_DEV AS CURRENCY_CODE_2,
                'TN' AS COUNTRY_2,
                CHEQUE_RECU.MNT_OPE AS FOREIGN_AMOUNT_2,
                
                '30' + '/' + CHEQUE_RECU.TRANSACTION_NUMBER + '/' +
				CAST(YEAR(CHEQUE_RECU.POSTING_DATE) AS NVARCHAR(4)) + ' ' +
				RIGHT('0' + CAST(MONTH(CHEQUE_RECU.POSTING_DATE) AS NVARCHAR(2)), 2) + ' ' +
				RIGHT('0' + CAST(DAY(CHEQUE_RECU.POSTING_DATE) AS NVARCHAR(2)), 2) AS TRANSACTION_NUMBER,
                'TN' AS TRANSACTION_LOCATION,
                CAST(YEAR(CHEQUE_RECU.POSTING_DATE) AS NVARCHAR(4)) + '-' +
				RIGHT('0' + CAST(MONTH(CHEQUE_RECU.POSTING_DATE) AS NVARCHAR(2)), 2) + '-' +
				RIGHT('0' + CAST(DAY(CHEQUE_RECU.POSTING_DATE) AS NVARCHAR(2)), 2) + 'T00:00:00' AS DATE_TRANSACTION,
                CHEQUE_RECU.TRANS_CODE_DESC AS TRANS_CODE_DESC_ATB,
                CHEQUE_RECU.TRANS_CODE AS TRANSMODE_CODE_ATB,
                'B126' AS TRANSACTION_CODE_GOAML,
                CHEQUE_RECU.MNT_OPE AS AMOUNT_LOCAL,
                'C' AS TRANSACTION_STATUS_CODE,

                ' CHEQUE_RECU INITIATEUR_OPE ' + CHEQUE_RECU.INITIATEUR_OPE AS NAR,

                'CHEQUE_RECU' AS SOURCE
                
                
            FROM [MISDW].[GO_AML].[IBANK_CHEQUE_RECU] AS CHEQUE_RECU
            LEFT JOIN [MISDW].[GO_AML].[BANQUE TN DETAILS] AS BANQUE_TN_DETAILS ON RIGHT('00' + BANQUE_TN_DETAILS.CODBQE, 2) = RIGHT('00' + CHEQUE_RECU.INITIATEUR_CODE_BQE, 2)
            WHERE
				YEAR(POSTING_DATE) = '{year}'--2024
				AND CHEQUE_RECU.BRN_ACC + CHEQUE_RECU.ACCOUNT_ID + CHEQUE_RECU.SFX_ACC = '{account}'--5848519069500
            """

            # Retry logic for query execution
            self._log('info', "Executing query with max_attempts: %d", max_attempts)
            df = self.query_executor.retry_query_execution(query, self.connection, max_attempts=max_attempts)

            if df.empty:
                self._log('warning', "No Cheque_ca recu' transactions data found for the account: %s, year: %s", account, year)
            else:
                print('-------------------------------------------------------')
                print(len(df))
                print('-------------------------------------------------------')
                #self.cheque_transactions = pd.concat([self.cheque_transactions, clean_dataframe(df)], ignore_index=True)
                self.cheque_transactions = pd.concat(
                    [self.cheque_transactions.copy(), clean_dataframe(df)], 
                    ignore_index=True
                ).copy()
                

                self._log('info', "Query executed successfully; Cheque_ca recu' transactions data retrieved for the account.")
        except Exception as e:
            self._log('error', "Error retrieving Cheque_ca recu' transactions data for the account: %s, year: %s, error: %s", account, year, e)
            raise
        finally:
            self._log('info', "Closing database connection.")
            self.disconnect()

        self._log('info', "Returning cleaned DataFrame.")

    def process_transaction(
        self,
        party: str,
        party_customer_id: str,
        party_type: str,
        party_related_person: pd.DataFrame
        ) -> pd.DataFrame:

        get_client = GetClient(self.db_config)

        xml = XML()
    
        df_result = pd.DataFrame(columns=['transaction_date', 'transaction_detail'])
        data_list = []
        initiator_dict = dict()
        conductor_xml_1 = ''

        # Bloc IB_account minimal pour une contrepartie externe non identifiee
        UNKNOWN_ACCOUNT_XML = """
        <IB_account>
            <institution_name>UNKNOWN</institution_name>
            <swift>UNKNOWNXX</swift>
            <institution_country>TN</institution_country>
            <account>UNKNOWN</account>
        </IB_account>
        """

        if party_type != 'PM':
            # Correctif : party_related_person peut etre vide si les tables
            # GO_AML.EQ_PPH / GO_AML.EQ_TIERS ne renvoient rien pour ce client
            # (donnee manquante). On evite un IndexError sur une liste vide.
            if not party_related_person.empty:
                conductor_xml_1 = [xml.create_xml_conductor(row) for idx, row in party_related_person.iterrows()][0]
            else:
                conductor_xml_1 = 'Aucun titulaire associe n a ete trouve (donnee manquante)'

        elif party_type == 'PM':
            if not party_related_person.empty:
                #person_list = [row for _, row in party_related_person.iterrows() if row.ROLE_RE in ['signatory', 'RL']]
                person_list = [row for _, row in party_related_person.iterrows() if row.RELATED_PERSON_ROLE_CODE_ATB == 'SIGNATAIRE']
                conductor_xml_1 = xml.create_xml_conductor(person_list[0], comments='Un tiers (appartenant au groupe des signataires (T24_EB_MANDATE) ou EQ_TIERS - TYPE_TIERS = REPRES-LEGAL) a ete designe') if person_list else f"Aucun signataire n a ete trouve pour : {party_customer_id}"
            else:
                conductor_xml_1 = 'Aucun tiers associe n a ete trouve'


        # Filter out NaN and empty string values
        valid_accounts = self.cheque_transactions_to_process['PART_2_ACCOUNT']
        valid_accounts = valid_accounts[valid_accounts.ne('')].dropna().unique()  # Remove '' and NaN

        for p_acc in tqdm(valid_accounts, total=len(valid_accounts), desc="Retrieve account details (PART_2)"):
            try:
                account_correspondences, account_details, customer_id, account_type, account_rp = get_client.get_client_details(p_acc)
                account = {
                    'account_correspondences': account_correspondences,
                    'account_detail': account_details,
                    'customer_id': customer_id,
                    'account_type': account_type,
                    'account_rp': account_rp
                }
                initiator_dict[p_acc] = account
            except Exception as e:
                print(f"Contrepartie Cheque {p_acc} introuvable (donnee manquante), ignoree : {e}")
                continue



        for index, row in tqdm(self.cheque_transactions_to_process.iterrows(), total=len(self.cheque_transactions_to_process)):

            account = ''
            person_list = []
            conductor_xml_2 = ''

            comment = (
                f"Op IBANK: {row['SOURCE']} - {row['TRANSACTION_DESC_ATB_ACC']} - {row['TRANSACTION_CODE_ATB']} - Narrative : {row['NAR']}"
            )

            trx = xml.create_transaction_xml(row, comment)
            if(row.PART_1_ROLE == 'I'): # partie = conductor + PPH # Emis
                obj_1 = ''
                p_1 = conductor_xml_1 + party # already gotten
                obj_1 = xml.create_xml_OBJ(row, 1)
                obj_1 = obj_1.replace('PL3', p_1)
                obj_1 = obj_1.replace('PL_CONDUCTOR', '')
                obj_1 = obj_1.replace('PL1', 'from_my_client')
                obj_1 = obj_1.replace('PL2', 'from')
                obj_1 = obj_1.replace('IB_', 'from_')

                trx = trx.replace('PL_FROM', obj_1)
                

                if(row.PART_2_IS_MY_CLIENT == 'Y'):
                    try:
                        account = initiator_dict[row.PART_2_ACCOUNT]

                        obj_2 = ''
                        p_2 = account['account_detail']
                        obj_2 = xml.create_xml_OBJ(row, 2)
                        obj_2 = obj_2.replace('PL3', p_2)
                        obj_2 = obj_2.replace('PL_CONDUCTOR', '')
                        obj_2 = obj_2.replace('PL1', 'to_my_client')
                        obj_2 = obj_2.replace('PL2', 'to')
                        obj_2 = obj_2.replace('IB_', 'to_')

                        trx = trx.replace('PL_TO', obj_2)
                    except KeyError:
                        print(f"Contrepartie Cheque {row.PART_2_ACCOUNT} introuvable (donnee manquante), bloc t_to generique utilise")
                        obj_2 = xml.create_xml_OBJ(row, 2)
                        obj_2 = obj_2.replace('PL3', UNKNOWN_ACCOUNT_XML)
                        obj_2 = obj_2.replace('PL_CONDUCTOR', '')
                        obj_2 = obj_2.replace('PL1', 'to')
                        obj_2 = obj_2.replace('PL2', 'to')
                        obj_2 = obj_2.replace('IB_', 'to_')
                        trx = trx.replace('PL_TO', obj_2)
                    

                if(row.PART_2_IS_MY_CLIENT == 'N'):
                    obj_2 = ''
                    p_2 = row.PART_2_DETAILS
                    obj_2 = xml.create_xml_OBJ(row, 2)
                    obj_2 = obj_2.replace('PL3', p_2)
                    obj_2 = obj_2.replace('PL_CONDUCTOR', '')
                    obj_2 = obj_2.replace('PL1', 'to')
                    obj_2 = obj_2.replace('PL2', 'to')
                    obj_2 = obj_2.replace('IB_', 'to_')
                    trx = trx.replace('PL_TO', obj_2)
                    
            
            if(row.PART_1_ROLE == 'B'): # partie = PPH # Recue
                obj_1 = ''
                p_1 = party # already gotten
                obj_1 = xml.create_xml_OBJ(row, 1)
                obj_1 = obj_1.replace('PL3', p_1)
                obj_1 = obj_1.replace('PL_CONDUCTOR', '')
                obj_1 = obj_1.replace('PL1', 'to_my_client')
                obj_1 = obj_1.replace('PL2', 'to')
                obj_1 = obj_1.replace('IB_', 'to_')
                trx = trx.replace('PL_TO', obj_1)

                
                if(row.PART_2_IS_MY_CLIENT == 'Y'):
                    try:
                        account = initiator_dict[row.PART_2_ACCOUNT]
                        if account['account_type'] != 'PM':
                            conductor_xml_2 = [xml.create_xml_conductor(row, comments='Le titulaire du compte ou l un des cotitulaires (pour un compte joint) a ete designe') for idx, row in account['account_rp'].iterrows()][0]
                        elif account['account_type'] == 'PM':
                            #person_list = [row for _, row in account['account_rp'].iterrows() if row.ROLE_RE in ['signatory', 'RL']]
                            person_list = [row for _, row in account['account_rp'].iterrows() if row.RELATED_PERSON_ROLE_CODE_ATB == 'SIGNATAIRE']
                            conductor_xml_2 = xml.create_xml_conductor(person_list[0], comments='Un tiers (appartenant au groupe des signataires (T24_EB_MANDATE) ou EQ_TIERS - TYPE_TIERS = REPRES-LEGAL) a ete designe') if person_list else f"Aucun signataire n a ete trouve pour : {account['customer_id']}"
                        obj_2 = ''
                        p_2 = conductor_xml_2 + account['account_detail']
                        obj_2 = xml.create_xml_OBJ(row, 2)
                        obj_2 = obj_2.replace('PL3', p_2)
                        obj_2 = obj_2.replace('PL_CONDUCTOR', '')
                        obj_2 = obj_2.replace('PL1', 'from_my_client')
                        obj_2 = obj_2.replace('PL2', 'from')
                        obj_2 = obj_2.replace('IB_', 'from_')
                        trx = trx.replace('PL_FROM', obj_2)
                    except KeyError:
                        print(f"Contrepartie Cheque {row.PART_2_ACCOUNT} introuvable (donnee manquante), bloc t_from generique utilise")
                        obj_2 = xml.create_xml_OBJ(row, 2)
                        obj_2 = obj_2.replace('PL3', UNKNOWN_ACCOUNT_XML)
                        obj_2 = obj_2.replace('PL_CONDUCTOR', '')
                        obj_2 = obj_2.replace('PL1', 'from')
                        obj_2 = obj_2.replace('PL2', 'from')
                        obj_2 = obj_2.replace('IB_', 'from_')
                        trx = trx.replace('PL_FROM', obj_2)
                    

                if(row.PART_2_IS_MY_CLIENT == 'N'):
                    obj_2 = ''
                    p_2 = row.PART_2_DETAILS
                    obj_2 = xml.create_xml_OBJ(row, 2)
                    obj_2 = obj_2.replace('PL3', p_2)
                    obj_2 = obj_2.replace('PL_CONDUCTOR', '')
                    obj_2 = obj_2.replace('PL1', 'from')
                    obj_2 = obj_2.replace('PL2', 'from')
                    obj_2 = obj_2.replace('IB_', 'from_')
                    trx = trx.replace('PL_FROM', obj_2)
                    
            
            transaction_date = pd.to_datetime(row.DATE_TRANSACTION[:-9]).strftime('%Y-%m-%d')
            data_list.append({'transaction_date': transaction_date, 'transaction_detail': trx})
            

        df_result = pd.DataFrame(data_list)

        self.cheque_transactions_processed = df_result.copy(deep=True)


    def clear_cache(self):
        self.cheque_transactions = pd.DataFrame()
        self.cheque_transactions_to_process = pd.DataFrame()
        self.cheque_transactions_processed = pd.DataFrame()