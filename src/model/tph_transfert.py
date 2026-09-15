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


class tph_Transfert(DatabaseConnection):
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

        self._log('info', "Starting tph_transfert's transactions retrieval for account: %s, year: %s", account, year)
        self.connect()

        df = pd.DataFrame()

        try:
            query = f"""

           -- Transfert RECU
            WITH RankedOrderEntries AS (
                SELECT
                    pp.TransactionReferenceNumber,
                    pp.CreditAccountNumber,
                    PP.CreditValueDate,
                    PP.Creditaccountcurrency,
                    pp.TransactionAmount,
                    pp.TransactionCurrency,
                    pp.DebitValueDate,
                    pp.OrderingName,
                    pp.Orderingaccount,
                    pp.OrderingCountry,
                    pp.DebitAccountNumber,
                    pp.debitaccountcurrency,
                    pp.debitamount,
                    pp.CreditAmount,
                    pp.BeneficiaryAccount,
                    pp.BeneficiaryName,
                    pp.BeneficiaryCountry,
                    pp.status,
                    ROW_NUMBER() OVER (
                        PARTITION BY pp.TransactionReferenceNumber
                        ORDER BY pp.DATE_TIME DESC
                    ) AS rn
                FROM [MISDW].[TRG].[T24_F_PP_ORDER_ENTRY] pp
                WHERE pp.Direction = 'I'
               
            )
            SELECT
                'Y' AS PART_1_IS_MY_CLIENT,
                'I' AS PART_1_ROLE,
                --map.cpteq AS EQ_ACCOUNT,
                pp.CreditAccountNumber AS T24_ACCOUNT,
                PP.transactionreferencenumber AS TRANSACTION_REF,
                PP.CreditValueDate AS TRANSACTION_DATE,
                    
                'A' AS FUND_CODE_1,
                Creditaccountcurrency AS CURRENCY_CODE_1,
                'TN' AS COUNTRY_1,
                PP.Creditamount AS FOREIGN_AMOUNT_1,
                    
                'N' AS PART_2_IS_MY_CLIENT,
                '' AS PART_2_TYPE,
                'B' AS PART_2_ROLE,
                '' AS PART_2_ACCOUNT,
                '<IB_account>' +
                    '<institution_name>' +
                    CASE
                        WHEN TRIM(ISNULL(PP.OrderingName, '')) = '' THEN 'N.A'
                        ELSE PP.OrderingName 
                    END +
                    '</institution_name>' +
                    '<swift>'+ 
                    CASE
                        WHEN TRIM(ISNULL(tfdih.from_address, '')) = '' THEN 'N.A'
                        ELSE tfdih.from_address 
                    END +
                    '</swift>' +
                    '<institution_country>' +
                    CASE
                        WHEN TRIM(ISNULL(PP.Orderingcountry, '')) = '' THEN 'N.A'
                        ELSE PP.Orderingcountry
                    END + 
                    '</institution_country>' +
                    '<account>' + 
                    CASE
                        WHEN TRIM(ISNULL(Orderingaccount, '')) = '' THEN 'N.A' -- RIB
                        ELSE Orderingaccount
                    END + 
                    '</account>' +
                '</IB_account>' AS PART_2_DETAILS,
                
                'A' AS FUND_CODE_2,
                debitaccountcurrency AS CURRENCY_CODE_2,
                CASE
                    WHEN TRIM(ISNULL(PP.Orderingcountry, '')) = '' THEN 'N.A'
                    ELSE PP.Orderingcountry
                END AS COUNTRY_2,
                debitamount AS FOREIGN_AMOUNT_2,
                
                'TN' AS TRANSACTION_LOCATION, 
                CASE
                    WHEN PP.DebitValueDate = 0 OR TRY_CONVERT(INT, PP.DebitValueDate) IS NULL THEN
                        '30/0000/00 00 0000'  -- Default value for invalid or zero TRANSACTION_DATE
                    WHEN ISDATE(CONVERT(VARCHAR, TRY_CONVERT(INT, PP.DebitValueDate) )) = 1 THEN
                        '30/' + PP.transactionreferencenumber + '/' +
                        SUBSTRING(pp.DebitValueDate,7,2) + ' ' +
                        SUBSTRING(pp.DebitValueDate,5,2) + ' ' +
                        SUBSTRING(pp.DebitValueDate,1,4)
                    ELSE
                        NULL  -- or any other default value/message you want to return
                END AS TRANSACTION_NUMBER,
                CASE
                    WHEN PP.DebitValueDate = 0 THEN '0000-00-00T00:00:00'
                    WHEN ISDATE(CONVERT(VARCHAR, TRY_CONVERT(INT, PP.DebitValueDate))) = 1 THEN
                        CONVERT(VARCHAR, CONVERT(DATE, CONVERT(VARCHAR, TRY_CONVERT(INT, PP.DebitValueDate)))) + 'T00:00:00'
                    ELSE NULL  -- or any other default value/message you want to return
                END AS DATE_TRANSACTION,
                tr.narrative AS TRANS_CODE_DESC_ATB,
                stmt.TRANSACTION_CODE AS TRANSMODE_CODE_ATB,
                'B397' AS TRANSACTION_CODE_GOAML,
                debitamount AS AMOUNT_LOCAL,
                CASE
                    WHEN STATUS in ('600','993','999')  THEN 'C' 
                    WHEN STATUS = '997' THEN 'S'
                    ELSE '-' 
                END AS TRANSACTION_STATUS_CODE,
                'TRF_RECUS' AS SOURCE
                    
            FROM [MISDW].[TRG].[T24_F_POR_TRANSACTION] po
            INNER JOIN RankedOrderEntries pp
                ON po.RECID = pp.TransactionReferenceNumber
                AND pp.rn   = 1
            --left join  [MISDW].master_data.T24_MAPPING_ACC map on map.CPT24 = PP.CreditAccountNumber
            left join [MISDW].[TRG].T24_FATB_STMT_ENTRY_2024 stmt on stmt.account_number=PP.CreditAccountNumber and PP.creditamount=abs(stmt.amount_lcy)
            left join trg.T24_FBNK_TRANSACTION tr on tr.TRANSACTION_CODE= stmt.TRANSACTION_CODE 
            left join [MISDW].[TRG].[T24_F_DE_I_HEADER] tfdih on PP.transactionreferencenumber = tfdih.TRANSACTION_REF 
            WHERE
                pp.CreditAccountNumber = '{account}'
                AND CASE
                        WHEN pp.DebitValueDate = 0 OR TRY_CONVERT(INT, pp.DebitValueDate) IS NULL THEN 0
                        ELSE YEAR(CONVERT(DATE, CONVERT(VARCHAR, TRY_CONVERT(INT, pp.DebitValueDate))))
                    END = '{year}'
     
            UNION

-- Transfert - Emis
            SELECT
                'Y' AS PART_1_IS_MY_CLIENT,
                'I' AS PART_1_ROLE,
                --map.cpteq AS EQ_ACCOUNT,
                debitaccountnumber AS T24_ACCOUNT,
                PP.transactionreferencenumber AS TRANSACTION_REF,
                PP.DebitValueDate AS TRANSACTION_DATE,
                    
                'A' AS FUND_CODE_1,
                Debitaccountcurrency AS CURRENCY_CODE_1,
                'TN' AS COUNTRY_1,
                debitamount AS FOREIGN_AMOUNT_1,
                    
                'N' AS PART_2_IS_MY_CLIENT,
                '' AS PART_2_TYPE,
                'B' AS PART_2_ROLE,
                '' AS PART_2_ACCOUNT,
                '<IB_account>' +
                    '<institution_name>' +
                    CASE
                        WHEN TRIM(ISNULL(BeneficiaryName, '')) = '' THEN 'N.A'
                        ELSE BeneficiaryName 
                    END +
                    '</institution_name>' +
                    '<swift>'+ 
                    CASE
                        WHEN TRIM(ISNULL(tfdih.from_address, '')) = '' THEN 'N.A'
                        ELSE tfdih.from_address 
                    END +
                    '</swift>' +
                    '<institution_country>' +
                    CASE
                        WHEN TRIM(ISNULL(Beneficiarycountry, '')) = '' THEN 'N.A'
                        ELSE Beneficiarycountry
                    END + 
                    '</institution_country>' +
                    '<account>' + 
                    CASE
                        WHEN TRIM(ISNULL(Beneficiaryaccount, '')) = '' THEN 'N.A' -- RIB
                        ELSE Beneficiaryaccount
                    END + 
                    '</account>' +
                '</IB_account>' AS PART_2_DETAILS,
                
                'A' AS FUND_CODE_2,
                creditaccountcurrency AS CURRENCY_CODE_2,
                CASE
                    WHEN TRIM(ISNULL(BeneficiaryCountry, '')) = '' THEN 'N.A'
                    ELSE BeneficiaryCountry
                END AS COUNTRY_2,
                creditamount AS FOREIGN_AMOUNT_2,
                
                'TN' AS TRANSACTION_LOCATION, 
                CASE
                    WHEN pp.DebitValueDate = 0 OR TRY_CONVERT(INT, pp.DebitValueDate) IS NULL THEN
                        '30/0000/00 00 0000'  -- Default value for invalid or zero TRANSACTION_DATE
                    WHEN ISDATE(CONVERT(VARCHAR, TRY_CONVERT(INT, pp.DebitValueDate) )) = 1 THEN
                        '30/' + transactionreferencenumber + '/' +
                        SUBSTRING(pp.DebitValueDate,7,2) + ' ' +
                        SUBSTRING(pp.DebitValueDate,5,2) + ' ' +
                        SUBSTRING(pp.DebitValueDate,1,4)
                    ELSE
                        NULL  -- or any other default value/message you want to return
                END AS TRANSACTION_NUMBER,
                CASE
                    WHEN pp.DebitValueDate = 0 THEN '0000-00-00T00:00:00'
                    WHEN ISDATE(CONVERT(VARCHAR, TRY_CONVERT(INT, pp.DebitValueDate))) = 1 THEN
                        CONVERT(VARCHAR, CONVERT(DATE, CONVERT(VARCHAR, TRY_CONVERT(INT, pp.DebitValueDate)))) + 'T00:00:00'
                    ELSE NULL  -- or any other default value/message you want to return
                END AS DATE_TRANSACTION,
                tr.narrative AS TRANS_CODE_DESC_ATB,
                stmt.TRANSACTION_CODE AS TRANSMODE_CODE_ATB,
                'B397' AS TRANSACTION_CODE_GOAML,
                creditamount AS AMOUNT_LOCAL,
                CASE
                    WHEN STATUS in ('600','993','999')  THEN 'C'
                    WHEN STATUS = '997' THEN 'S' 
                    ELSE '-' 
                END AS TRANSACTION_STATUS_CODE,

                'TRF_EMIS' AS SOURCE
                    
            FROM
                [MISDW].[TRG].[T24_F_PP_ORDER_ENTRY] PP
                --left join [MISDW].[TRG].[T24_F_POR_TRANSACTION] PT on PT.ftnumber = pp.transactionreferencenumber
                --left join  [MISDW].master_data.T24_MAPPING_ACC map on map.CPT24 = pp.orderingaccount
                left join [MISDW].[TRG].T24_FATB_STMT_ENTRY_2024 stmt on stmt.account_number=pp.orderingaccount and pp.creditamount=abs(stmt.amount_lcy)
                left join trg.T24_FBNK_TRANSACTION tr on tr.TRANSACTION_CODE= stmt.TRANSACTION_CODE
                left join [MISDW].[TRG].[T24_F_DE_I_HEADER] tfdih on pp.transactionreferencenumber = tfdih.TRANSACTION_REF 
            -- Filter by year, handling zero or invalid TRANSACTION_DATE values
            WHERE
           		PP.Direction='O' AND
                CASE
                    WHEN pp.DebitValueDate = 0 OR TRY_CONVERT(INT, pp.DebitValueDate) IS NULL THEN
                        0 
                    ELSE
                        SUBSTRING(pp.DebitValueDate,1 ,4) 
                END = '{year}'
                AND debitaccountnumber = '{account}'        
            """

            # Retry logic for query execution
            self._log('info', "Executing query with max_attempts: %d", max_attempts)
            df = self.query_executor.retry_query_execution(query, self.connection, max_attempts=max_attempts)

            print (df.info)

            if df.empty:
                self._log('warning', "No tph_transfert's transactions data found for the account: %s, year: %s", account, year)
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


        print(self.transfert_transactions_to_process.info())
        print("écriture fichier transactions_to_process")
        try:
            self.transfert_transactions_to_process.to_csv("C:\GOAML\procopr.csv", index=False) 
            print("DataFrame saved to procopr.csv successfully.")
        except OSError as e:
            print(f"File error: {e}")
        
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