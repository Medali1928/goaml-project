import time
from tqdm import tqdm
from typing import List
import pandas as pd
from typing import Dict

from src.helpers.xmlStructure import XML
from src.helpers.utils import clean_dataframe,aggregate_legal_id_section
from src.db.connection import DatabaseConnection
from src.db.query_executor import QueryExecutor
from src.model.get_client_T24 import GetClientT24
from src.helpers.logger_manager import LoggerManager

class Teller(DatabaseConnection):
    def __init__(self, db_config: dict, log_enabled: bool = True) -> None:

        super().__init__(db_config['server'], db_config['database'], db_config['username'], db_config['password'])

        self.db_config = db_config

        self.logger_manager = LoggerManager(log_enabled)
        self.query_executor = QueryExecutor(self.connection)

        self.teller_transactions = pd.DataFrame()
        self.teller_transactions_to_process = pd.DataFrame()
        self.teller_transactions_processed = pd.DataFrame()


    def _log(self, level, message, *args, **kwargs):
        """Log a message if logging is enabled using the logger manager."""
        self.logger_manager.log(level, message, *args, **kwargs)

    def get_teller_transactions(self, account: str, year: str, max_attempts: int = 1) -> pd.DataFrame:
        """
        Retrieves operation details for a given account and year with retry logic.

        Args:
            account (str): The account number in the format BR+BN+SFX.
            year (str): The year for which the data is required.
            max_attempts (int, optional): Maximum number of retry attempts. Defaults to 3.

        Returns:
            pd.DataFrame: A cleaned DataFrame containing the operation details.
        """
        self.teller_transactions = pd.DataFrame()
        self._log('info', "Starting Teller's transactions retrieval for account: %s, year: %s", account, year)
        self.connect()

        df = pd.DataFrame()

        try:
            # SQL query to fetch transaction data
            query = f"""
            SELECT
                TELLER_HIS.ACCOUNT_2 AS T24_ACCOUNT,
                TELLER_HIS.HISTORY_ID AS TRANSACTION_REF,
                SUBSTRING(TELLER_HIS.VALUE_DATE_1, 3, LEN(TELLER_HIS.VALUE_DATE_1) - 2) AS TRANSACTION_DATE,

                -- Account (currency, amount)
                CASE
                    WHEN TELLER_HIS.CURRENCY_2 = 'TND' OR TELLER_HIS.CURRENCY_2 = 'TDC' THEN 'TND'
                    ELSE TELLER_HIS.CURRENCY_2
                END AS CURRENCY_CODE_1,
                'TN' AS COUNTRY_1,
                CASE
                    WHEN TELLER_HIS.CURRENCY_2 = 'TND' THEN TELLER_HIS.AMOUNT_LOCAL_2
                    WHEN TELLER_HIS.CURRENCY_2 <> 'TND' THEN TELLER_HIS.AMOUNT_FCY_2 --TDC
                END AS FOREIGN_AMOUNT_1,

                TELLER_HIS.CURRENCY_1 AS CURRENCY_CODE_2,
                'TN' AS COUNTRY_2,
                CASE
                    WHEN TELLER_HIS.CURRENCY_1 = 'TND' THEN TELLER_HIS.AMOUNT_LOCAL_1
                    WHEN TELLER_HIS.CURRENCY_1 <> 'TND' THEN TELLER_HIS.AMOUNT_FCY_1
                END AS FOREIGN_AMOUNT_2,
                
                TELLER_HIS.L_ORDONATEUR,
				TELLER_HIS.L_BENEFICIAIRE,
				--TELLER_HIS.L_DONNEUR_ORDRE,
                CASE TELLER_HIS.L_DONNEUR_ORDRE
			        WHEN 'TITULAIRE' THEN '1'
			        WHEN 'SIGNATAIRE' THEN '2'
			        WHEN 'TIERS' THEN '3'
			    END AS L_DONNEUR_ORDRE,
				
                TELLER_HIS.ACCOUNT_2,
				TELLER_HIS.CUSTOMER_2,
				TELLER_HIS.SIGNATORY,
				TELLER_HIS.L_TIERS_NOM,
				TELLER_HIS.L_TIERS_NUMID,

                BRANCH.NAME AS TRANSACTION_LOCATION,
                CASE
                    WHEN TELLER_HIS.VALUE_DATE_1 = 0 OR TRY_CONVERT(INT, TELLER_HIS.VALUE_DATE_1) IS NULL THEN '30/0000/00 00 0000'
                    WHEN ISDATE(CONVERT(VARCHAR, TRY_CONVERT(INT, TELLER_HIS.VALUE_DATE_1))) = 1 THEN
                        '30/' + TELLER_HIS.TRANSACTION_NUMBER + '/' +
                        RIGHT('0' + CONVERT(VARCHAR(2), DAY(CONVERT(VARCHAR, CONVERT(DATE, CONVERT(VARCHAR, TRY_CONVERT(INT, TELLER_HIS.VALUE_DATE_1))), 23))), 2) + ' ' +
                        RIGHT('0' + CONVERT(VARCHAR(2), MONTH(CONVERT(VARCHAR, CONVERT(DATE, CONVERT(VARCHAR, TRY_CONVERT(INT, TELLER_HIS.VALUE_DATE_1))), 23))), 2) + ' ' +
                        CONVERT(VARCHAR(4), YEAR(CONVERT(VARCHAR, CONVERT(DATE, CONVERT(VARCHAR, TRY_CONVERT(INT, TELLER_HIS.VALUE_DATE_1))), 23)))
                    ELSE NULL
                END AS TRANSACTION_NUMBER,
                CASE
                    WHEN TELLER_HIS.VALUE_DATE_1 = 0 THEN '0000-00-00T00:00:00'
                    WHEN ISDATE(CONVERT(VARCHAR, TRY_CONVERT(INT, TELLER_HIS.VALUE_DATE_1))) = 1 THEN CONVERT(VARCHAR, CONVERT(DATE, CONVERT(VARCHAR, TRY_CONVERT(INT, TELLER_HIS.VALUE_DATE_1))), 23) + 'T00:00:00'
                    ELSE NULL
                END AS DATE_TRANSACTION,
                TELLER_HIS.AMOUNT_LOCAL_2 AS AMOUNT_LOCAL,
                'C' AS TRANSACTION_STATUS_CODE,
                'TELLER_HIS' AS SOURCE
            FROM [MISDW].[TRG].[T24_FATB_TELLER#HIS] AS TELLER_HIS
            LEFT JOIN [MISDW].[TRG].[T24_F_DEPT_ACCT_OFFICER] AS BRANCH ON BRANCH.ACCOUNT_OFFICER = TELLER_HIS.DEPT_CODE
            WHERE
                TELLER_HIS.RECORD_STATUS = 'MAT'
                AND TELLER_HIS.ACCOUNT_2 = '{account}'
                AND CASE
                        WHEN TELLER_HIS.VALUE_DATE_1 = 0 OR TRY_CONVERT(INT, TELLER_HIS.VALUE_DATE_1) IS NULL THEN 0
                        ELSE YEAR(CONVERT(DATE, CONVERT(VARCHAR, TRY_CONVERT(INT, TELLER_HIS.VALUE_DATE_1))))
                    END = '{year}'
                --AND TELLER_HIS.HISTORY_ID = 'TT25217Z71FF'

            UNION

            SELECT
                TELLER_BBE.ACCOUNT_2 AS T24_ACCOUNT,
                TELLER_BBE.HISTORY_ID AS TRANSACTION_REF,
                SUBSTRING(TELLER_BBE.VALUE_DATE_1, 3, LEN(TELLER_BBE.VALUE_DATE_1) - 2) AS TRANSACTION_DATE,
                
                
                -- Account (currency, amount)
                CASE
                    WHEN TELLER_BBE.CURRENCY_2 = 'TND' OR TELLER_BBE.CURRENCY_2 = 'TDC' THEN 'TND'
                    ELSE TELLER_BBE.CURRENCY_2
                END AS CURRENCY_CODE_1,
                'TN' AS COUNTRY_1,
                CASE
                    WHEN TELLER_BBE.CURRENCY_2 = 'TND' THEN TELLER_BBE.AMOUNT_LOCAL_2
                    WHEN TELLER_BBE.CURRENCY_2 <> 'TND' THEN TELLER_BBE.AMOUNT_FCY_2 --TDC
                END AS FOREIGN_AMOUNT_1,

                TELLER_BBE.CURRENCY_1 AS CURRENCY_CODE_2,
                'TN' AS COUNTRY_2,
                CASE
                    WHEN TELLER_BBE.CURRENCY_1 = 'TND' THEN TELLER_BBE.AMOUNT_LOCAL_1
                    WHEN TELLER_BBE.CURRENCY_1 <> 'TND' THEN TELLER_BBE.AMOUNT_FCY_1
                END AS FOREIGN_AMOUNT_2,

                TELLER_BBE.L_ORDONATEUR,
				TELLER_BBE.L_BENEFICIAIRE,
				--TELLER_BBE.L_DONNEUR_ORDRE,
                CASE TELLER_BBE.L_DONNEUR_ORDRE
			        WHEN 'TITULAIRE' THEN '1'
			        WHEN 'SIGNATAIRE' THEN '2'
			        WHEN 'TIERS' THEN '3'
			    END AS L_DONNEUR_ORDRE,
                
				TELLER_BBE.ACCOUNT_2,
				TELLER_BBE.CUSTOMER_2,
				TELLER_BBE.SIGNATORY,
				TELLER_BBE.L_TIERS_NOM,
				TELLER_BBE.L_TIERS_NUMID,

                BRANCH.NAME AS TRANSACTION_LOCATION,
                CASE
                    WHEN TELLER_BBE.VALUE_DATE_1 = 0 OR TRY_CONVERT(INT, TELLER_BBE.VALUE_DATE_1) IS NULL THEN '30/0000/00 00 0000'
                    WHEN ISDATE(CONVERT(VARCHAR, TRY_CONVERT(INT, TELLER_BBE.VALUE_DATE_1))) = 1 THEN
                        '30/' + TELLER_BBE.TRANSACTION_NUMBER + '/' +
                        RIGHT('0' + CONVERT(VARCHAR(2), DAY(CONVERT(VARCHAR, CONVERT(DATE, CONVERT(VARCHAR, TRY_CONVERT(INT, TELLER_BBE.VALUE_DATE_1))), 23))), 2) + ' ' +
                        RIGHT('0' + CONVERT(VARCHAR(2), MONTH(CONVERT(VARCHAR, CONVERT(DATE, CONVERT(VARCHAR, TRY_CONVERT(INT, TELLER_BBE.VALUE_DATE_1))), 23))), 2) + ' ' +
                        CONVERT(VARCHAR(4), YEAR(CONVERT(VARCHAR, CONVERT(DATE, CONVERT(VARCHAR, TRY_CONVERT(INT, TELLER_BBE.VALUE_DATE_1))), 23)))
                    ELSE NULL
                END AS TRANSACTION_NUMBER,
                CASE
                    WHEN TELLER_BBE.VALUE_DATE_1 = 0 THEN '0000-00-00T00:00:00'
                    WHEN ISDATE(CONVERT(VARCHAR, TRY_CONVERT(INT, TELLER_BBE.VALUE_DATE_1))) = 1 THEN CONVERT(VARCHAR, CONVERT(DATE, CONVERT(VARCHAR, TRY_CONVERT(INT, TELLER_BBE.VALUE_DATE_1))), 23) + 'T00:00:00'
                    ELSE NULL
                END AS DATE_TRANSACTION,
                TELLER_BBE.AMOUNT_LOCAL_2 AS AMOUNT_LOCAL,
                'C' AS TRANSACTION_STATUS_CODE,
                'TELLER_BBE' AS SOURCE
            FROM [MISDW].[TRG].[T24_FATB_TELLER_BBE] AS TELLER_BBE
            LEFT JOIN [MISDW].[TRG].[T24_F_DEPT_ACCT_OFFICER] AS BRANCH ON BRANCH.ACCOUNT_OFFICER = TELLER_BBE.DEPT_CODE
            WHERE
                TELLER_BBE.RECORD_STATUS = 'MAT'
                AND TELLER_BBE.ACCOUNT_2 = '{account}'
                AND CASE
                        WHEN TELLER_BBE.VALUE_DATE_1 = 0 OR TRY_CONVERT(INT, TELLER_BBE.VALUE_DATE_1) IS NULL THEN 0
                        ELSE YEAR(CONVERT(DATE, CONVERT(VARCHAR, TRY_CONVERT(INT, TELLER_BBE.VALUE_DATE_1))))
                    END = '{year}'
            """

            # Retry logic for query execution
            self._log('info', "Executing query with max_attempts: %d", max_attempts)
            df = self.query_executor.retry_query_execution(query, self.connection, max_attempts=max_attempts)

            if df.empty:
                self._log('warning', "No Teller's transactions data found for the account: %s, year: %s", account, year)
            else:
                self.teller_transactions = clean_dataframe(df).copy(deep=True) if df is not None else pd.DataFrame()
                self._log('info', "Query executed successfully; Teller's transactions data retrieved for the account.")
        except Exception as e:
            self._log('error', "Error retrieving cashier's transactions data for the account: %s, year: %s, error: %s", account, year, e)
            raise
        finally:
            self._log('info', "Closing database connection.")
            self.disconnect()

        self._log('info', "Returning cleaned DataFrame.")
        

    def process_transactions(
    self,
    party: str,
    party_customer_id: str,
    party_type: str,
    party_related_person: pd.DataFrame
) -> pd.DataFrame:
        """
        Processes transactions and creates XML representations for each entry, including details for parties and related persons.
    
        Args:
            df_trx (pd.DataFrame): DataFrame containing transaction details.
            party (str): The party identifier.
            party_customer_id (str): The customer ID of the party.
            party_type (str): The type of the party (e.g., 'PPH', 'PRO', 'PM').
            party_related_person (pd.DataFrame): DataFrame containing details of related persons.
    
        Returns:
            pd.DataFrame: A DataFrame with transaction dates and XML transaction details.
        """


        getClientT24 = GetClientT24(self.db_config)
        xml = XML()
        df_result = pd.DataFrame(columns=['transaction_date', 'transaction_detail'])
        data_list: List[Dict[str, str]] = []
        initiator_dict: Dict[str, pd.DataFrame] = {}

        def L_fetch(key, row, initiator_dict, party_customer_id, party_related_person):
            print("[ in L_fetch ]")
            print(f"Key = {key}")
            print(row)
            df_customer = pd.DataFrame()
            conductor_xml = ""
            person_xml = ""
            is_third_party = False
            comment = ""

            match key:
                case "1":
                    print("[ in case 1 ]")
                    print(f"Key = {key}")
                    if row.CUSTOMER_2 not in initiator_dict:
                        df_customer = getClientT24.get_PPH(row.CUSTOMER_2, "CUSTOMER_CODE")
                        df_customer = aggregate_legal_id_section(df_customer)
                        initiator_dict[row.CUSTOMER_2] = df_customer
                        comment = " [ First Fetch using CUSTOMER_2 ] "
                    else:
                        df_customer = initiator_dict[row.CUSTOMER_2]
                        comment = " [ Second Fetch usnig CUSTOMER_2 ] "

                    if df_customer.loc[0, 'CUSTOMER_TYPE'] != "PM":
                        conductor_xml = [xml.create_xml_conductor(row, comments=comment) for _, row in df_customer.iterrows()][0]
                        person_xml = [xml.create_xml_person(row, comments=comment) for _, row in df_customer.iterrows()][0]
                    else:

                        #conductor_xml = " [ conductor - 1 - customer code corresponds to a legal entity (PM) ] "
                        #person_xml = " [ person - 1 - customer code corresponds to a legal entity (PM) ] "                   
                        person_list = [row for _, row in party_related_person.iterrows() if row.RELATED_PERSON_ROLE_CODE_ATB == 'SIGNATAIRE']
                        person_xml = xml.create_xml_person(person_list[0], comments='Un tiers appartenant au groupe des signataires (T24_EB_MANDATE) a ete designe') if person_list else f"Aucun signataire n a ete trouve pour : {party_customer_id}"
                        conductor_xml = xml.create_xml_conductor(person_list[0], comments='Un tiers appartenant au groupe des signataires (T24_EB_MANDATE) a ete designe') if person_list else f"Aucun signataire n a ete trouve pour : {party_customer_id}"
                        

                case "2":
                    print("[ in case 2 ]")
                    print(f"Key = {key}")
                    if pd.notna(row.SIGNATORY):
                        if row.SIGNATORY not in initiator_dict:
                            df_customer = getClientT24.get_PPH(row.SIGNATORY, "CUSTOMER_CODE")
                            df_customer = aggregate_legal_id_section(df_customer)
                            initiator_dict[row.SIGNATORY] = df_customer
                            comment = " [ First Fetch using SIGNATORY ] "
                        else:
                            df_customer = initiator_dict[row.SIGNATORY]
                            comment = " [ Second Fetch using SIGNATORY ] "

                    print(df_customer[["CUSTOMER_TYPE"]])
                    print(df_customer.shape)
                    if not df_customer.empty and df_customer["CUSTOMER_TYPE"].iloc[0] != "PM": # fix 2026-01-12 - iat
                        conductor_xml = [xml.create_xml_conductor(row, comments=comment) for _, row in df_customer.iterrows()][0]
                        person_xml = [xml.create_xml_person(row, comments=comment) for _, row in df_customer.iterrows()][0]
                    else:
                        #conductor_xml = " [ conductor - 2 - Missing SIGNATORY Id ] "
                        #person_xml = " [ person - 2 - Missing SIGNATORY Id ] "
                        #person_list = [row for _, row in party_related_person.iterrows() if row.RELATED_PERSON_ROLE_CODE_ATB == 'SIGNATAIRE']
                        #person_xml = xml.create_xml_person(person_list[0], comments='Un tiers appartenant au groupe des signataires (T24_EB_MANDATE) a ete designe') if person_list else f"Aucun signataire n a ete trouve pour : {party_customer_id}"
                        #conductor_xml = xml.create_xml_conductor(person_list[0], comments='Un tiers appartenant au groupe des signataires (T24_EB_MANDATE) a ete designe') if person_list else f"Aucun signataire n a ete trouve pour : {party_customer_id}"
                        # Make sure the dataframe is not empty
                        if not party_related_person.empty:
                        
                            # Case 1: All rows are 'CST'
                            if (party_related_person['ACCOUNT_TYPE'] == 'CST').all():
                                # Filter for the row where ROLE_ACCOUNT is 'TICPT'
                                ticpt_row = party_related_person[party_related_person['ROLE_ACCOUNT'] == 'TICPT']
                                if ticpt_row.empty:
                                    raise ValueError("No row with ROLE_ACCOUNT = 'TICPT' found for CST accounts")
                                row = ticpt_row.iloc[0]  # Take the TICPT row
                                comment = 'Le titulaire du compte a ete designe'
                                conductor_xml = xml.create_xml_conductor(row, comments=comment)
                                person_xml = xml.create_xml_person(row, comments=comment)
                        
                            # Case 2: All rows are 'CJ'
                            elif (party_related_person['ACCOUNT_TYPE'] == 'CJ').all():
                                row = party_related_person.iloc[0]  # Take the first row
                                comment = 'L un des cotitulaires (pour un compte joint) a ete designe'
                                conductor_xml = xml.create_xml_conductor(row, comments=comment)
                                person_xml = xml.create_xml_person(row, comments=comment)

                            # Case 3: All rows are 'CPM'
                            elif (party_related_person['ACCOUNT_TYPE'] == 'CPM').all():
                                signataire_row = party_related_person[party_related_person['RELATED_PERSON_ROLE_CODE_ATB'] == 'SIGNATAIRE'].iloc[0] # Take the first row
                                if signataire_row.empty:
                                    conductor_xml = f"Aucun signataire n a ete trouve pour : {party_customer_id}"
                                    person_xml = f"Aucun signataire n a ete trouve pour : {party_customer_id}"
                                    #raise ValueError("No row with RELATED_PERSON_ROLE_CODE_ATB = 'SIGNATAIRE' found for CST accounts")
                                comment = 'Un tiers appartenant au groupe des signataires (T24_EB_MANDATE) a ete designe'
                                conductor_xml = xml.create_xml_conductor(row, comments=comment)
                                person_xml = xml.create_xml_person(row, comments=comment)

                            else:
                                # Optional: handle mixed types
                                raise ValueError("Mixed ACCOUNT_TYPE values are not supported")
                
                case "3":
                    print("[ in case 3 ]")
                    print(f"Key = {key}")
                    if row.L_TIERS_NUMID not in [None, '']:
                        if row.L_TIERS_NUMID not in initiator_dict:
                            df_customer = getClientT24.get_PPH(row.L_TIERS_NUMID, "LEGAL_ID")
                            if not df_customer.empty:
                                df_customer = aggregate_legal_id_section(df_customer)
                                initiator_dict[row.L_TIERS_NUMID] = df_customer
                                comment = " [ First Fetch using L_TIERS_NUMID ] "
                        else:
                            df_customer = initiator_dict[row.L_TIERS_NUMID]
                            comment = " [ Second Fetch using L_TIERS_NUMID ] "
                    if not df_customer.empty:
                        person_xml = [xml.create_xml_person(row, comments=comment) for _, row in df_customer.iterrows()][0]
                        conductor_xml = [xml.create_xml_conductor(row, comments=comment) for _, row in df_customer.iterrows()][0]
                        #is_third_party = False
                    else:
                        person_xml = "<IB_person><first_name>" + row.L_TIERS_NOM + "</first_name><last_name>" + row.L_TIERS_NOM + "</last_name></IB_person>"
                        is_third_party = True
                case _:
                    person_xml = "<IB_person><first_name>" + row.L_TIERS_NOM + "</first_name><last_name>" + row.L_TIERS_NOM + "</last_name></IB_person>"
                    is_third_party = True

            return initiator_dict, conductor_xml, person_xml, is_third_party
    
        print('--------------- Teller TRX processing ---------------')
        print(self.teller_transactions_to_process.shape)
        print(self.teller_transactions_to_process.head(2))
        #for idx, row in tqdm(self.teller_transactions_to_process[:20].iterrows(), total=len(self.teller_transactions_to_process[:20])):

        customer_dict = {} # BN / Details

        for idx, row in tqdm(self.teller_transactions_to_process.iterrows(), total=len(self.teller_transactions_to_process)):

            comment = f"\nOp Teller - Accountant amount = {row.TRANSACTION_AMOUNT_LCY}"
            #df_customer = pd.DataFrame()
            person_xml = ''
            conductor_xml = ''
            is_third_party = False
            #msg = ""

            ##
            print(f"\nrow.L_ORDONATEUR = {row.L_ORDONATEUR} - row.L_BENEFICIAIRE = {row.L_BENEFICIAIRE} - row.L_DONNEUR_ORDRE = {row.L_DONNEUR_ORDRE}\n")

            comment += f"\nrow.L_ORDONATEUR = {row.L_ORDONATEUR} - row.L_BENEFICIAIRE = {row.L_BENEFICIAIRE} - row.L_DONNEUR_ORDRE = {row.L_DONNEUR_ORDRE}"
            comment += f"\nrow.CUSTOMER_2 = {row.CUSTOMER_2} - row.SIGNATORY = {row.SIGNATORY} - row.L_TIERS_NUMID = {row.L_TIERS_NUMID}"

            if pd.notna(row.L_ORDONATEUR) and pd.isna(row.L_BENEFICIAIRE) and pd.isna(row.L_DONNEUR_ORDRE):
                initiator_dict, conductor_xml, person_xml, is_third_party = L_fetch(str(row.L_ORDONATEUR), row, initiator_dict, party_customer_id, party_related_person)
                is_third_party_I = is_third_party
                is_third_party_B = is_third_party

            if pd.isna(row.L_ORDONATEUR) and pd.notna(row.L_BENEFICIAIRE) and pd.isna(row.L_DONNEUR_ORDRE):
                initiator_dict, conductor_xml, person_xml, is_third_party = L_fetch(str(row.L_BENEFICIAIRE), row, initiator_dict, party_customer_id, party_related_person)
                is_third_party_I = is_third_party
                is_third_party_B = is_third_party

            if pd.isna(row.L_ORDONATEUR) and pd.isna(row.L_BENEFICIAIRE) and pd.notna(row.L_DONNEUR_ORDRE):
                initiator_dict, conductor_xml, person_xml, is_third_party = L_fetch(str(row.L_DONNEUR_ORDRE), row, initiator_dict, party_customer_id, party_related_person)
                is_third_party_I = is_third_party
                is_third_party_B = is_third_party

            if pd.isna(row.L_ORDONATEUR) and pd.isna(row.L_BENEFICIAIRE) and pd.isna(row.L_DONNEUR_ORDRE):
                initiator_dict, conductor_xml, person_xml, is_third_party = L_fetch("3", row, initiator_dict, party_customer_id, party_related_person)
                is_third_party_I = is_third_party
                is_third_party_B = is_third_party

            if pd.notna(row.L_ORDONATEUR) and pd.notna(row.L_BENEFICIAIRE) and pd.isna(row.L_DONNEUR_ORDRE):
                initiator_dict, conductor_xml, _, is_third_party = L_fetch(str(row.L_ORDONATEUR), row, initiator_dict, party_customer_id, party_related_person)
                is_third_party_I = is_third_party

                initiator_dict, _, person_xml, is_third_party = L_fetch(str(row.L_BENEFICIAIRE), row, initiator_dict, party_customer_id, party_related_person)
                is_third_party_B = is_third_party

            if pd.notna(row.L_ORDONATEUR) and pd.isna(row.L_BENEFICIAIRE) and pd.notna(row.L_DONNEUR_ORDRE):
                initiator_dict, conductor_xml, _, is_third_party = L_fetch(str(row.L_ORDONATEUR), row, initiator_dict, party_customer_id, party_related_person)
                is_third_party_I = is_third_party

                initiator_dict, _, person_xml, is_third_party = L_fetch(str(row.L_DONNEUR_ORDRE), row, initiator_dict, party_customer_id, party_related_person)
                is_third_party_B = is_third_party

            if pd.isna(row.L_ORDONATEUR) and pd.notna(row.L_BENEFICIAIRE) and pd.notna(row.L_DONNEUR_ORDRE):
                initiator_dict, conductor_xml, _, is_third_party = L_fetch(str(row.L_DONNEUR_ORDRE), row, initiator_dict, party_customer_id, party_related_person)
                is_third_party_I = is_third_party

                initiator_dict, _, person_xml, is_third_party = L_fetch(str(row.L_BENEFICIAIRE), row, initiator_dict, party_customer_id, party_related_person)
                is_third_party_B = is_third_party

            trx = xml.create_transaction_xml(row, comment=comment)
    
            if row.PARTY_ROLE == 'I':
                obj_1 = xml.create_xml_OBJ(row, 1)
                obj_1 = obj_1.replace('PL3', conductor_xml + party)
                obj_1 = obj_1.replace('PL1', 'from_my_client')
                obj_1 = obj_1.replace('PL2', 'from')
                obj_1 = obj_1.replace('IB_', 'from_')
                trx = trx.replace('PL_FROM', obj_1)
    
                obj_2 = xml.create_xml_OBJ(row, 2)

                if not is_third_party_B:
                    obj_2 = obj_2.replace('PL1', 'to_my_client')
                else:
                    obj_2 = obj_2.replace('PL1', 'to')

                obj_2 = obj_2.replace('PL2', 'to')
                obj_2 = obj_2.replace('PL3', person_xml)
                obj_2 = obj_2.replace('IB_', 'to_')
                trx = trx.replace('PL_TO', obj_2)
    
            elif row.PARTY_ROLE == 'B':
                obj_1 = xml.create_xml_OBJ(row, 1)
                obj_1 = obj_1.replace('PL3', party)
                obj_1 = obj_1.replace('PL1', 'to_my_client')
                obj_1 = obj_1.replace('PL2', 'to')
                obj_1 = obj_1.replace('IB_', 'to_')
                trx = trx.replace('PL_TO', obj_1)

                obj_2 = xml.create_xml_OBJ(row, 2)

                if not is_third_party_I:
                    obj_2 = obj_2.replace('PL1', 'from_my_client')
                else:
                    obj_2 = obj_2.replace('PL1', 'from')

                obj_2 = obj_2.replace('PL2', 'from')

                if not is_third_party_I:
                    obj_2 = obj_2.replace('PL3', conductor_xml + person_xml)
                else:
                    obj_2 = obj_2.replace('PL3', person_xml)

                obj_2 = obj_2.replace('IB_', 'from_')
                trx = trx.replace('PL_FROM', obj_2)
    
            transaction_date = pd.to_datetime(row['DATE_TRANSACTION'][:-9]).strftime('%Y-%m-%d')
            data_list.append({'transaction_date': transaction_date, 'transaction_detail': trx})
    
        df_result = pd.DataFrame(data_list)
    
        self.teller_transactions_processed = df_result.copy(deep=True)

    def clear_cache(self):
        self.teller_transactions = pd.DataFrame()
        self.teller_transactions_to_process = pd.DataFrame()
        self.teller_transactions_processed = pd.DataFrame()
