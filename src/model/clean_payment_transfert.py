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


class Transfert(DatabaseConnection):
    def __init__(self, db_config: dict, log_enabled: bool = True) -> None:

        super().__init__(db_config['server'], db_config['database'], db_config['username'], db_config['password'])

        self.db_config = db_config

        self.logger_manager = LoggerManager(log_enabled)
        self.query_executor = QueryExecutor(self.connection)

        self.transfert_transactions = pd.DataFrame()
        self.transfert_transactions_to_process = pd.DataFrame()
        self.transfert_transactions_processed = pd.DataFrame()


    def _log(self, level, message, *args, **kwargs):
        """Log a message if logging is enabled using the logger manager."""
        self.logger_manager.log(level, message, *args, **kwargs)

    def get_transfert(self, account: str, year: str, max_attempts: int = 3) -> pd.DataFrame:

        self._log('info', "Starting transfert's transactions retrieval for account: %s, year: %s", account, year)
        self.connect()

        # Splitting into BR, BN, SFX
        BR = account[0:4]
        BN = account[4:10]
        SFX = account[10:13]

        df = pd.DataFrame()

        try:
            query = f"""
            -- Transfert - Emis/Recus
            -- Transfert - Emis
            SELECT
                'Y' AS PART_1_IS_MY_CLIENT,
                'I' AS PART_1_ROLE,
                BRN_ACC AS PART_1_BR,
                ACCOUNT_ID AS PART_1_BN,
                SFX_ACC AS PART_1_SFX,
                BRN_ACC + ACCOUNT_ID + SFX_ACC AS EQ_ACCOUNT,
                TRANSACTION_NUMBER AS TRANSACTION_REF,
                TRANSACTION_DATE,
                    
                'A' AS FUND_CODE_1,
                F_CCY_CODE AS CURRENCY_CODE_1,
                'TN' AS COUNTRY_1,
                FOREIGN_AMNT_CCY AS FOREIGN_AMOUNT_1,
                    
                'N' AS PART_2_IS_MY_CLIENT,
                '' AS PART_2_TYPE,
                'B' AS PART_2_ROLE,
                '' AS PART_2_ACCOUNT,
                '<IB_account>' +
                    '<institution_name>' +
                    CASE
                        WHEN TRIM(ISNULL(R_SWIFT_ID, '')) = '' THEN 'N.A'
                        ELSE R_SWIFT_ID 
                    END +
                    '</institution_name>' +
                    '<swift>' +
                    CASE
                        WHEN TRIM(ISNULL(BENF_SWIFT_BANk_ID, '')) = '' THEN 'N.A'
                        WHEN LEN(BENF_SWIFT_BANk_ID) > 11 THEN 'N.A'
                        ELSE BENF_SWIFT_BANk_ID
                    END + 
                    '</swift>' +
                    '<institution_country>' +
                    CASE
                        WHEN TRIM(ISNULL(R_SWIFT_COUNTRY_CoDE, '')) = '' THEN 'N.A'
                        ELSE R_SWIFT_COUNTRY_CoDE
                    END + 
                    '</institution_country>' +
                    '<account>' + 
                    CASE
                        WHEN TRIM(ISNULL(ORDERING_CUST_ACC, '')) = '' THEN 'N.A' -- RIB
                        ELSE ORDERING_CUST_ACC
                    END + 
                    '</account>' +
                '</IB_account>' AS PART_2_DETAILS,
                
                'A' AS FUND_CODE_2,
                L_CCY_CODE AS CURRENCY_CODE_2,
                CASE
                    WHEN TRIM(ISNULL(R_SWIFT_COUNTRY_CoDE, '')) = '' THEN 'N.A'
                    ELSE R_SWIFT_COUNTRY_CoDE
                END AS COUNTRY_2,
                LOCAL_AMNT_CCY AS FOREIGN_AMOUNT_2,

                
                'TN' AS TRANSACTION_LOCATION, 
                CASE
                    WHEN TRANSACTION_DATE = 0 OR TRY_CONVERT(INT, TRANSACTION_DATE) IS NULL THEN
                        '30/0000/00 00 0000'  -- Default value for invalid or zero TRANSACTION_DATE
                    WHEN ISDATE(CONVERT(VARCHAR, TRY_CONVERT(INT, TRANSACTION_DATE) + 19000000)) = 1 THEN
                        '30/' + TRANSACTION_NUMBER + '/' +
                        RIGHT('0' + CONVERT(VARCHAR(2), DAY(CONVERT(VARCHAR, CONVERT(DATE, CONVERT(VARCHAR, TRY_CONVERT(INT, TRANSACTION_DATE) + 19000000)), 23))), 2) + ' ' +
                        RIGHT('0' + CONVERT(VARCHAR(2), MONTH(CONVERT(VARCHAR, CONVERT(DATE, CONVERT(VARCHAR, TRY_CONVERT(INT, TRANSACTION_DATE) + 19000000)), 23))), 2) + ' ' +
                        CONVERT(VARCHAR(4), YEAR(CONVERT(VARCHAR, CONVERT(DATE, CONVERT(VARCHAR, TRY_CONVERT(INT, TRANSACTION_DATE) + 19000000)), 23))) 
                    ELSE
                        NULL  -- or any other default value/message you want to return
                END AS TRANSACTION_NUMBER,
                CASE
                    WHEN TRANSACTION_DATE = 0 THEN '0000-00-00T00:00:00'
                    WHEN ISDATE(CONVERT(VARCHAR, TRY_CONVERT(INT, TRANSACTION_DATE) + 19000000)) = 1 THEN
                        CONVERT(VARCHAR, CONVERT(DATE, CONVERT(VARCHAR, TRY_CONVERT(INT, TRANSACTION_DATE) + 19000000)), 23) + 'T00:00:00'
                    ELSE NULL  -- or any other default value/message you want to return
                END AS DATE_TRANSACTION,
                TRANS_CODE_DESC AS TRANS_CODE_DESC_ATB,
                TRANS_CODE AS TRANSMODE_CODE_ATB,
                'B397' AS TRANSACTION_CODE_GOAML,
                FOREIGN_AMNT_CCY AS AMOUNT_LOCAL,
                CASE
                    WHEN TRANSACTION_STATUS = 'A' THEN 'C' 
                    ELSE '-' 
                END AS TRANSACTION_STATUS_CODE,

                'TRF_EMIS' AS SOURCE
                    
            FROM
                [MISDW].[GO_AML].[EQA_CP_TRF_EMIS]
            -- Filter by year, handling zero or invalid TRANSACTION_DATE values
            WHERE
                CASE
                    WHEN TRANSACTION_DATE = 0 OR TRY_CONVERT(INT, TRANSACTION_DATE) IS NULL THEN
                        0  -- or any placeholder value to indicate an invalid date
                    ELSE
                        YEAR(CONVERT(DATE, CONVERT(VARCHAR, TRY_CONVERT(INT, TRANSACTION_DATE) + 19000000)))
                END = '{year}' AND
                BRN_ACC = '{BR}' AND
                ACCOUNT_ID = '{BN}' AND
                SFX_ACC = '{SFX}'

                
                
            UNION


            -- Transfert - Recus
            SELECT
                'Y' AS PART_1_IS_MY_CLIENT,
                'B' AS PART_1_ROLE,
                BRN_ACC AS PART_1_BR,
                ACCOUNT_ID AS PART_1_BN,
                SFX_ACC AS PART_1_SFX,
                BRN_ACC + ACCOUNT_ID + SFX_ACC AS EQ_ACCOUNT,
                TRANSACTION_NUMBER AS TRANSACTION_REF,
                TRANSACTION_DATE,
                    
                'A' AS FUND_CODE_1,
                F_CCY_CODE AS CURRENCY_CODE_1,
                'TN' AS COUNTRY_1,
                FOREIGN_AMNT_CCY AS FOREIGN_AMOUNT_1,
                    
                'N' AS PART_2_IS_MY_CLIENT,
                '' AS PART_2_TYPE,
                'I' AS PART_2_ROLE,
                '' AS PART_2_ACCOUNT,
                '<IB_account>' +
                    '<institution_name>' +
                    CASE
                        WHEN TRIM(ISNULL(R_SWIFT_ID, '')) = '' THEN 'N.A'
                        ELSE R_SWIFT_ID 
                    END +
                    '</institution_name>' +
                    '<swift>' +
                    CASE
                        WHEN TRIM(ISNULL(BENF_SWIFT_BANk_ID, '')) = '' THEN 'N.A'
                        WHEN LEN(BENF_SWIFT_BANk_ID) > 11 THEN 'N.A'
                        ELSE BENF_SWIFT_BANk_ID
                    END + 
                    '</swift>' +
                    '<institution_country>' +
                    CASE
                        WHEN TRIM(ISNULL(R_SWIFT_COUNTRY_CoDE, '')) = '' THEN 'N.A'
                        ELSE R_SWIFT_COUNTRY_CoDE
                    END + 
                    '</institution_country>' +
                    '<account>' + 
                    CASE
                        WHEN TRIM(ISNULL(ORDERING_CUST_ACC, '')) = '' THEN 'N.A' -- RIB
                        ELSE ORDERING_CUST_ACC
                    END + 
                    '</account>' +
                '</IB_account>' AS PART_2_DETAILS,
                
                'A' AS FUND_CODE_2,
                L_CCY_CODE AS CURRENCY_CODE_2,
                CASE
                    WHEN TRIM(ISNULL(R_SWIFT_COUNTRY_CoDE, '')) = '' THEN 'N.A'
                    ELSE R_SWIFT_COUNTRY_CoDE
                END AS COUNTRY_2,
                LOCAL_AMNT_CCY AS FOREIGN_AMOUNT_2,
                
                
                'TN' AS TRANSACTION_LOCATION,
                CASE
                    WHEN TRANSACTION_DATE = 0 OR TRY_CONVERT(INT, TRANSACTION_DATE) IS NULL THEN
                        '30/0000/00 00 0000'  -- Default value for invalid or zero TRANSACTION_DATE
                    WHEN ISDATE(CONVERT(VARCHAR, TRY_CONVERT(INT, TRANSACTION_DATE) + 19000000)) = 1 THEN
                        '30/' + TRANSACTION_NUMBER + '/' +
                        RIGHT('0' + CONVERT(VARCHAR(2), DAY(CONVERT(VARCHAR, CONVERT(DATE, CONVERT(VARCHAR, TRY_CONVERT(INT, TRANSACTION_DATE) + 19000000)), 23))), 2) + ' ' +
                        RIGHT('0' + CONVERT(VARCHAR(2), MONTH(CONVERT(VARCHAR, CONVERT(DATE, CONVERT(VARCHAR, TRY_CONVERT(INT, TRANSACTION_DATE) + 19000000)), 23))), 2) + ' ' +
                        CONVERT(VARCHAR(4), YEAR(CONVERT(VARCHAR, CONVERT(DATE, CONVERT(VARCHAR, TRY_CONVERT(INT, TRANSACTION_DATE) + 19000000)), 23))) 
                    ELSE
                        NULL  -- or any other default value/message you want to return
                END AS TRANSACTION_NUMBER,
                CASE
                    WHEN TRANSACTION_DATE = 0 THEN '0000-00-00T00:00:00'
                    WHEN ISDATE(CONVERT(VARCHAR, TRY_CONVERT(INT, TRANSACTION_DATE) + 19000000)) = 1 THEN
                        CONVERT(VARCHAR, CONVERT(DATE, CONVERT(VARCHAR, TRY_CONVERT(INT, TRANSACTION_DATE) + 19000000)), 23) + 'T00:00:00'
                    ELSE NULL  -- or any other default value/message you want to return
                END AS DATE_TRANSACTION,
                TRANS_CODE_DESC AS TRANS_CODE_DESC_ATB,
                TRANS_CODE AS TRANSMODE_CODE_ATB,
                'B397' AS TRANSACTION_CODE_GOAML,
                FOREIGN_AMNT_CCY AS AMOUNT_LOCAL,
                CASE
                    WHEN TRANSACTION_STATUS = 'A' THEN 'C' 
                    ELSE '-' 
                END AS TRANSACTION_STATUS_CODE,

                'TRF_RECUS' AS SOURCE
                    
            FROM
                [MISDW].[GO_AML].[EQA_CP_TRF_RECUS]
            -- Filter by year, handling zero or invalid TRANSACTION_DATE values
            WHERE
                CASE
                    WHEN TRANSACTION_DATE = 0 OR TRY_CONVERT(INT, TRANSACTION_DATE) IS NULL THEN
                        0  -- or any placeholder value to indicate an invalid date
                    ELSE
                        YEAR(CONVERT(DATE, CONVERT(VARCHAR, TRY_CONVERT(INT, TRANSACTION_DATE) + 19000000)))
                END = '{year}' AND
                BRN_ACC = '{BR}' AND
                ACCOUNT_ID = '{BN}' AND
                SFX_ACC = '{SFX}'
            """

            # Retry logic for query execution
            self._log('info', "Executing query with max_attempts: %d", max_attempts)
            df = self.query_executor.retry_query_execution(query, self.connection, max_attempts=max_attempts)

            if df.empty:
                self._log('warning', "No transfert's transactions data found for the account: %s, year: %s", account, year)
            else:
                self.transfert_transactions = pd.concat(
                    [self.transfert_transactions.copy(), clean_dataframe(df)], 
                    ignore_index=True
                )

                self._log('info', "Query executed successfully; transfert's transactions data retrieved for the account.")
        except Exception as e:
            self._log('error', "Error retrieving transfert's transactions data for the account: %s, year: %s, error: %s", account, year, e)
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

        xml = XML()

        df_result = pd.DataFrame(columns=['transaction_date', 'transaction_detail'])
        data_list = []
        p_2_dict = dict()

        if party_type != 'PM':
            conductor_xml = [xml.create_xml_conductor(row) for idx, row in party_related_person.iterrows()][0]

        elif party_type == 'PM':
            if not party_related_person.empty:
                #person_list = [row for _, row in party_related_person.iterrows() if row.ROLE_RE in ['signatory', 'RL']]
                person_list = [row for _, row in party_related_person.iterrows() if row.RELATED_PERSON_ROLE_CODE_ATB == 'SIGNATAIRE']
                conductor_xml = xml.create_xml_conductor(person_list[0], comments='Un tiers (appartenant au groupe des signataires (T24_EB_MANDATE) ou EQ_TIERS - TYPE_TIERS = REPRES-LEGAL) a ete designe') if person_list else f"Aucun signataire n a ete trouve pour : {party_customer_id}"
            else:
                conductor_xml = 'Aucun tiers associe n a ete trouve'
        
        for index, row in tqdm(self.transfert_transactions_to_process.iterrows(), total=len(self.transfert_transactions_to_process)):

            comment = (
                f"Op : {row['SOURCE']} - {row['TRANS_CODE_DESC_ATB']} - {row['TRANSMODE_CODE_ATB']}"
            )

            trx = xml.create_transaction_xml(row, comment)
            if(row.PART_1_ROLE == 'I'): # partie = conductor + PPH # Emis
                obj_1 = ''
                p_1 = conductor_xml + party # already gotten
                obj_1 = xml.create_xml_OBJ(row, 1)
                obj_1 = obj_1.replace('PL3', p_1)
                obj_1 = obj_1.replace('PL1', 'from_my_client')
                obj_1 = obj_1.replace('PL2', 'from')
                obj_1 = obj_1.replace('IB_', 'from_')
                
                trx = trx.replace('PL_FROM', obj_1)
                
                if(row.PART_2_IS_MY_CLIENT == 'N'):
                    obj_2 = ''
                    p_2 = row.PART_2_DETAILS
                    obj_2 = xml.create_xml_OBJ(row, 2)
                    obj_2 = obj_2.replace('PL3', p_2)
                    obj_2 = obj_2.replace('PL1', 'to')
                    obj_2 = obj_2.replace('PL2', 'to')
                    obj_2 = obj_2.replace('IB_', 'to_')
                
                    trx = trx.replace('PL_TO', obj_2)
                
        
            if(row.PART_1_ROLE == 'B'): # partie = PPH # Recue
                obj_1 = ''
                p_1 = party # already gotten
                obj_1 = xml.create_xml_OBJ(row, 1)
                obj_1 = obj_1.replace('PL3', p_1)
                obj_1 = obj_1.replace('PL1', 'to_my_client')
                obj_1 = obj_1.replace('PL2', 'to')
                obj_1 = obj_1.replace('IB_', 'to_')

                trx = trx.replace('PL_TO', obj_1)
                
                if(row.PART_2_IS_MY_CLIENT == 'N'):
                    obj_2 = ''
                    p_2 = row.PART_2_DETAILS
                    obj_2 = xml.create_xml_OBJ(row, 2)
                    obj_2 = obj_2.replace('PL3', p_2)
                    obj_2 = obj_2.replace('PL1', 'from')
                    obj_2 = obj_2.replace('PL2', 'from')
                    obj_2 = obj_2.replace('IB_', 'from_')

                    trx = trx.replace('PL_FROM', obj_2)
                
        
            transaction_date = pd.to_datetime(row.DATE_TRANSACTION[:-9]).strftime('%Y-%m-%d')
            # Append row data as a dictionary to the list
            data_list.append({'transaction_date': transaction_date, 'transaction_detail': trx})
        

        df_result = pd.DataFrame(data_list)

        self.transfert_transactions_processed = df_result.copy(deep=True)

    def clear_cache(self):
        self.transfert_transactions = pd.DataFrame()
        self.transfert_transactions_to_process = pd.DataFrame()
        self.transfert_transactions_processed = pd.DataFrame()