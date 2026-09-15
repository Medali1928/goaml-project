from typing import Dict

import time
from tqdm import tqdm
from typing import Optional, List
import pandas as pd

from src.helpers.xmlStructure import XML
from src.helpers.utils import clean_dataframe
from src.db.connection import DatabaseConnection
from src.db.query_executor import QueryExecutor
from src.helpers.logger_manager import LoggerManager
from src.helpers.utils import clean_text, aggregate_legal_id_section, construct_identification

from src.model.get_client_T24 import GetClientT24
from src.model.get_client_EQ import GetClientEQ

class Card(DatabaseConnection):
    def __init__(self, db_config: dict, log_enabled: bool = True) -> None:
        """
        Initialize the Card class with database configuration and logging options.

        Args:
            db_config (dict): Database configuration dictionary containing server, database, username, and password.
            log_enabled (bool): Whether to enable logging. Defaults to True.
        """
        super().__init__(db_config['server'], db_config['database'], db_config['username'], db_config['password'])
        self.logger_manager = LoggerManager(log_enabled)
        self.query_executor = QueryExecutor(self.connection)
        self.xml = XML()
        self.getClientT24 = GetClientT24(db_config)
        self.getClientEQ = GetClientEQ(db_config)

        #self.account_related_cards = Dict[str, pd.DataFrame] = {}
        self.account_related_cards = {}

        self.card_transactions = pd.DataFrame()
        self.card_transactions_to_process = pd.DataFrame()
        self.card_transactions_processed = pd.DataFrame()


    def _log(self, level: str, message: str, *args, **kwargs) -> None:
        """
        Log a message using the logger manager.

        Args:
            level (str): Logging level (e.g., 'info', 'warning', 'error').
            message (str): Log message format.
        """
        self.logger_manager.log(level, message, *args, **kwargs)

    def retrieve_cards_by_account(self, account_number: str, max_attempts: int = 3) -> pd.DataFrame:
        """
        Retrieve cards associated with a specific account number from the database.

        Args:
            account_number (str): The account number to retrieve associated cards for.
            max_attempts (int): Maximum number of retry attempts for the query. Defaults to 3.

        Returns:
            pd.DataFrame: DataFrame containing card details associated with the account.
        """
        self._log('info', "Starting retrieval of cards for account: %s", account_number)

        
        df = pd.DataFrame()

        query = f"""
            SELECT 
                CUSTOMER_CARDHOLDER.CUS_IDEN AS ORACLE_ACC,
                CUSTOMER_CARDHOLDER.CUS_CODE AS CARD_ID,
                CARDS.CAR_NUMB AS CARD_NUMBER,
                CUSTOMER_CARDHOLDER.CUS_FIRS_NAM1 AS CARD_HOLDER_NAME,
                UPPER(CUSTOMER_CARDHOLDER.CUS_FIRS_IDE1) AS CARD_HOLDER_LEGAL_ID
            FROM [MISDW].[TRG].[ATM_CUSTOMER_CARDHOLDER] AS CUSTOMER_CARDHOLDER 
            LEFT JOIN [MISDW].[TRG].[ATM_CARDS] AS CARDS ON CARDS.CAR_CUS_CODE = CUSTOMER_CARDHOLDER.CUS_CODE
            WHERE 
                CUSTOMER_CARDHOLDER.CUS_IDEN = '{account_number}'
        """

        try:
            # Ensure the database connection is established
            self.connect()
            self._log('info', "Executing query for account: %s", account_number)

            # Execute the query with retry logic
            df = self.query_executor.retry_query_execution(query, self.connection, max_attempts=max_attempts)

            card_holder: Dict[str, pd.DataFrame] = {}

            if df.empty:
                self._log('warning', "No cards found for account: %s", account_number)
            else:
                self._log('info', "Query executed successfully; card data retrieved for account: %s", account_number)

                for idx, row in df.iterrows():
                    # Retrieve PPH data for the card holder
                    response = pd.DataFrame()
                    # T24
                    response = self.getClientT24.get_PPH(row["CARD_HOLDER_LEGAL_ID"], "LEGAL_ID")
                    if not response.empty:
                        response = aggregate_legal_id_section(response)
                    # EQ
                    else:
                        response = self.getClientEQ.get_PPH_2(row["CARD_HOLDER_LEGAL_ID"], "LEGAL_ID")
                        if not response.empty:
                            response['IDENTIFICATIONS_ID_SECTION'] = response.apply(construct_identification, axis=1)
                    #print('================================')
                    #print('================================')
                    #print(response.empty)
                    #print(response)
                    #print('================================')
                    #print('================================')
                    #if not response.empty:
                    #    response = aggregate_legal_id_section(response)
                    #    response = self.getClientEQ.get_PPH_2(row["CARD_HOLDER_LEGAL_ID"], "LEGAL_ID")
                    #    response['IDENTIFICATIONS_ID_SECTION'] = response.apply(construct_identification, axis=1)

                    # Check if the response is not empty before accessing the first row
                    if not response.empty:
                        # Safe to access the first row if the response is not empty
                        card_holder[row['CARD_NUMBER']] = response.iloc[0]
                    else:
                        # Log a warning if no data was found for this CARD_HOLDER_LEGAL_ID
                        self._log('warning', "No data found for CARD_HOLDER_LEGAL_ID: %s", row["CARD_HOLDER_LEGAL_ID"])

                self.account_related_cards = card_holder

        except Exception as e:
            self._log('error', "Error retrieving cards for account: %s. Error: %s", account_number, e)
            raise

        finally:
            # Close the database connection
            self.disconnect()
            self._log('info', "Database connection closed.")

        self._log('info', "Cleaning and returning the retrieved DataFrame.")


    def get_card_transactions(self, account_number: str, year: str, max_attempts: int = 3) -> pd.DataFrame:


        self._log('info', "Starting retrieval of cards trx for account: %s", account_number)
        df = pd.DataFrame()

        query = f"""
            SELECT
                EQA_ACC_EXTERNAL_ACCOUNT_NUMBER.NEAB + EQA_ACC_EXTERNAL_ACCOUNT_NUMBER.NEAN + EQA_ACC_EXTERNAL_ACCOUNT_NUMBER.NEAS AS EQ_ACCOUNT,
            	CARD_TRX.AUT_ACCO_ID1_F102 AS ORACLE_ACCOUNT,
                CARD_TRX.AUT_PRIM_ACCT_NUMB_F002 AS CARD_NUMBER,
                'S' + SUBSTRING(CAST(CARD_TRX.AUT_CARD_ACCP_TERM_ID_F041 AS VARCHAR), 1, 6) + CARD_TRX.AUT_SYST_TRAC_AUDIT_NUMB_F011 AS TRANSACTION_REF,
                FORMAT(CARD_TRX.AUT_RESP_SYST_TIME, 'yyyy-MM-dd HH.mm') AS TRANSACTION_DATE_TS,

                'TN' AS COUNTRY_1,
                
                'TN' AS COUNTRY_2,
                CURRENCY_2.AlphabeticCode AS CURRENCY_CODE_2,
				FORMAT(ISNULL(CARD_TRX.AUT_BILL_AMOU_F006, 0) + ISNULL(CARD_TRX.AUT_BILL_AMOU_FEES_F008, 0) / POWER(10, CURRENCY_2.MinorUnit), '0.##################') FOREIGN_AMOUNT_2,
                
                '30' + '/' + SUBSTRING(CAST(CARD_TRX.AUT_CARD_ACCP_TERM_ID_F041 AS VARCHAR), 1, 6) + CARD_TRX.AUT_SYST_TRAC_AUDIT_NUMB_F011 + '/' + FORMAT(CARD_TRX.AUT_REQU_SYST_TIME, 'dd MM yyyy') AS TRANSACTION_NUMBER,
                CARD_TRX.AUT_CARD_ACCP_NAME_LOC_F043 AS TRANSACTION_LOCATION,
                FORMAT(CARD_TRX.AUT_REQU_SYST_TIME, 'yyyy-MM-dd') + 'T00:00:00' AS DATE_TRANSACTION,
                'C' AS TRANSACTION_STATUS_CODE,
                
                CARD_TRX.AUT_CARD_ACCP_NAME_LOC_F043 AS NAR,

                'Card - AUTHORIZATION' AS MXP_SOURCE
                
            FROM [MISDW].[TRG].[ATM_AUTHORIZATION] AS CARD_TRX
            LEFT JOIN [MISDW].[TRG].[EQA_ACC_EXTERNAL_ACCOUNT_NUMBER] AS EQA_ACC_EXTERNAL_ACCOUNT_NUMBER ON EQA_ACC_EXTERNAL_ACCOUNT_NUMBER.NEEAN = CARD_TRX.AUT_ACCO_ID1_F102
            LEFT JOIN [MISDW].[GO_AML].[CURRENCY_CODES] AS CURRENCY_2 ON FORMAT(CURRENCY_2.NumericCode, '000') = CARD_TRX.AUT_ADDI_AMOU_F054_CURR_CODE2
            WHERE
                CARD_TRX.AUT_ACCO_ID1_F102 = '{account_number}'
                AND FORMAT(CARD_TRX.AUT_REQU_SYST_TIME, 'yyyy') = '{year}'
        """

        try:
            # Ensure the database connection is established
            self.connect()
            self._log('info', "Executing query for account: %s", account_number)

            # Execute the query with retry logic
            df = self.query_executor.retry_query_execution(query, self.connection, max_attempts=max_attempts)

            if df.empty:
                self._log('warning', "No cards trx found for account: %s", account_number)
            else:
                df['TRANSACTION_LOCATION'] = df['TRANSACTION_LOCATION'].apply(clean_text)
                #self.card_transactions = df
                self.card_transactions = pd.concat([self.card_transactions, df], ignore_index=True).copy(deep=True)
                self._log('info', "Query executed successfully; card trx data retrieved for account: %s", account_number)

        except Exception as e:
            self._log('error', "Error retrieving cards trx for account: %s. Error: %s", account_number, e)
            raise

        finally:
            # Close the database connection
            self.disconnect()
            self._log('info', "Database connection closed.")

        self._log('info', "Cleaning and returning the retrieved DataFrame.")


    def get_card_transactions_2(self, account_number: str, year: str, max_attempts: int = 3) -> pd.DataFrame:


        self._log('info', "Starting retrieval of cards trx for account: %s", account_number)
        df = pd.DataFrame()
        query = f"""
            SELECT
                HCPCOMPTA.NUMCPT AS EQ_ACCOUNT,
                EQ_ORACLE.NEEAN AS ORACLE_ACCOUNT,
                HCPATB_SMT.NUMPOR AS CARD_NUMBER,
                HCPCOMPTA.REFEQA AS TRANSACTION_REF,
                HCPCOMPTA.SEQEQA AS TRANSACTION_SEQ,
                
                'TN' AS COUNTRY_1,
                --'TND' AS CURRENCY_CODE_1,
                --ABS(FORMAT(HCPCOMPTA.MNTMVT / POWER(10, NO_OF_DECIMALS), '0.##################')) AS FOREIGN_AMOUNT_1,
                
                'TN' AS COUNTRY_2,
                'TND' AS CURRENCY_CODE_2,
                ABS(FORMAT(HCPCOMPTA.MNTMVT / POWER(10, CURRENCY_1.NO_OF_DECIMALS), '0.##################')) AS FOREIGN_AMOUNT_2,
                
                --ABS(FORMAT(HCPCOMPTA.MNTMVT / POWER(10, NO_OF_DECIMALS), '0.##################')) AS AMOUNT_LOCAL,
                
                '30' + '/' + HCPCOMPTA.REFEQA + '/' + FORMAT(HCPCOMPTA.DATEQA, 'dd MM yyyy') AS TRANSACTION_NUMBER,--yyyy MM ddTHH:mm:ss
                HCPATB_SMT.LOCABR AS TRANSACTION_LOCATION,
                FORMAT(HCPCOMPTA.DATEQA, 'yyyy-MM-ddTHH:mm:ss') AS DATE_TRANSACTION,
                'C' AS TRANSACTION_STATUS_CODE,
                
                HCPATB_SMT.ENSABR AS NAR,

                'Card - HCPATB_SMT' AS MXP_SOURCE
                
                
            FROM [MISDW].[TRG].[ATM_HCPCOMPTA] AS HCPCOMPTA
            LEFT JOIN [MISDW].[TRG].[EQA_ACC_EXTERNAL_ACCOUNT_NUMBER] AS EQ_ORACLE ON EQ_ORACLE.NEAB + EQ_ORACLE.NEAN + EQ_ORACLE.NEAS = HCPCOMPTA.NUMCPT
            LEFT JOIN [MISDW].[TRG].[ATM_HCPATB_SMT] AS HCPATB_SMT ON
                                                                    HCPATB_SMT.DATTRT = HCPCOMPTA.DATTRT
                                                                    AND HCPATB_SMT.REFTRS = HCPCOMPTA.REFARC
            LEFT JOIN [MISDW].[TRG].[T24_FBNK_CURRENCY] AS CURRENCY_1 ON CURRENCY_1.CURRENCY_CODE = HCPCOMPTA.DEVMVT
            WHERE 
                HCPCOMPTA.NUMCPT = '{account_number}'
                AND YEAR(HCPCOMPTA.DATEQA) = '{year}'
        """

        try:
            # Ensure the database connection is established
            self.connect()
            self._log('info', "Executing query for account: %s", account_number)

            # Execute the query with retry logic
            df = self.query_executor.retry_query_execution(query, self.connection, max_attempts=max_attempts)

            if df.empty:
                self._log('warning', "No cards trx found for account: %s", account_number)
            else:
                df['TRANSACTION_LOCATION'] = df['TRANSACTION_LOCATION'].apply(clean_text)
                self.card_transactions = pd.concat([self.card_transactions, df], ignore_index=True).copy(deep=True)
                #self.card_transactions_2 = df
                self._log('info', "Query executed successfully; card trx data retrieved for account: %s", account_number)

        except Exception as e:
            self._log('error', "Error retrieving cards trx for account: %s. Error: %s", account_number, e)
            raise

        finally:
            # Close the database connection
            self.disconnect()
            self._log('info', "Database connection closed.")

        self._log('info', "Cleaning and returning the retrieved DataFrame.")

    def get_card_transactions_international(self, account_number: str, year: str, max_attempts: int = 3) -> pd.DataFrame:


        self._log('info', "Starting retrieval of cards trx for account: %s", account_number)
        df = pd.DataFrame()
        query = f"""
            SELECT
                HCPCOMPTA_VISA.NUMCPT AS EQ_ACCOUNT,
                EQ_ORACLE.NEEAN AS ORACLE_ACCOUNT,
                HVISAINC.NUM_POR AS CARD_NUMBER,
                HCPCOMPTA_VISA.REFEQA AS TRANSACTION_REF,
                SUBSTRING(HCPCOMPTA_VISA.SEQEQA, 2, LEN(HCPCOMPTA_VISA.SEQEQA)) AS TRANSACTION_SEQ,
                
                HCPCOMPTA_VISA.TYPCPT,
                HCPCOMPTA_VISA.DEVMVT AS CURRENCY_CODE_COMPTABLE,
                
                'TN' AS COUNTRY_1,							-- Pays où la transaction a été initiée.

                HVISAINC.PAY_COM AS COUNTRY_2,				-- Pays destinataire des fonds [OK]
                CURRENCY_2.AlphabeticCode AS CURRENCY_CODE_2,-- Code de devise
                ABS(FORMAT(HVISAINC.MNT_ORG / POWER(10, CURRENCY_2.MinorUnit), '0.##################')) AS FOREIGN_AMOUNT_2, -- -- Montant de la transaction dans la devise d'origine

                --ABS(FORMAT(HCPCOMPTA_VISA.MNTMVT / POWER(10, CURRENCY_1.NO_OF_DECIMALS), '0.##################')) AS AMOUNT_LOCAL,
                
                '30' + '/' + HCPCOMPTA_VISA.REFEQA + '/' + FORMAT(HCPCOMPTA_VISA.DATEQA, 'dd MM yyyy') AS TRANSACTION_NUMBER,
                HVISAINC.PAY_COM + ' - ' + HVISAINC.CIT_COM AS TRANSACTION_LOCATION,
                FORMAT(HCPCOMPTA_VISA.DATEQA, 'yyyy-MM-ddTHH:mm:ss') AS DATE_TRANSACTION,
                'C' AS TRANSACTION_STATUS_CODE,
                
                'VISA - ' + HVISAINC.NOM_COM AS NAR,
                
                'Card - HVISAINC' AS MXP_SOURCE
                
            FROM [MISDW].[TRG].[ATM_HCPCOMPTA_VISA] AS HCPCOMPTA_VISA
            LEFT JOIN [MISDW].[TRG].[EQA_ACC_EXTERNAL_ACCOUNT_NUMBER] AS EQ_ORACLE ON EQ_ORACLE.NEAB + EQ_ORACLE.NEAN + EQ_ORACLE.NEAS = HCPCOMPTA_VISA.NUMCPT
            LEFT JOIN [MISDW].[TRG].[ATM_HVISAINC] AS HVISAINC ON
                                                                                                        HVISAINC.REFTRS = HCPCOMPTA_VISA.REFARC
                                                                                                        AND HVISAINC.DAT_EQA = HCPCOMPTA_VISA.DATEQA
            LEFT JOIN [MISDW].[GO_AML].[CURRENCY_CODES] AS CURRENCY_2 ON FORMAT(CURRENCY_2.NumericCode, '000') = FORMAT(HVISAINC.MON_ORG, '000')
            WHERE
                HCPCOMPTA_VISA.NUMCPT = '{account_number}'
                AND YEAR(HCPCOMPTA_VISA.DATEQA) = '{year}'

            UNION

            SELECT
                HCPCOMPTA_MCD.NUMCPT AS EQ_ACCOUNT,
                EQ_ORACLE.NEEAN AS ORACLE_ACCOUNT,
                HINCMCD.NUM_POR AS CARD_NUMBER,
                HCPCOMPTA_MCD.REFEQA AS TRANSACTION_REF,
                HCPCOMPTA_MCD.SEQEQA AS TRANSACTION_SEQ,
                
                HCPCOMPTA_MCD.TYPCPT,
                HCPCOMPTA_MCD.DEVMVT AS CURRENCY_CODE_COMPTABLE,
                
                'TN' AS COUNTRY_1,                        -- Pays où la transaction a été initiée.

                
                COUNTRIES_ISO.alpha_2 AS COUNTRY_2,                        -- Pays où la transaction a été initiée.
                CURRENCY_2.AlphabeticCode AS CURRENCY_CODE_2, -- Code de devise
                ABS(FORMAT(HINCMCD.MNT_ORG_TRS / POWER(10, CURRENCY_2.MinorUnit), '0.##################')) AS FOREIGN_AMOUNT_2, -- Montant de la transaction dans la devise d'origine

                --ABS(FORMAT(HINCMCD.MNT_ORG_TRS / POWER(10, CURRENCY_2.NO_OF_DECIMALS), '0.##################')) AS AMOUNT_LOCAL,
                
                '30' + '/' + HCPCOMPTA_MCD.REFEQA + '/' + FORMAT(HCPCOMPTA_MCD.DATEQA, 'dd MM yyyy') AS TRANSACTION_NUMBER,
                HINCMCD.LOCALIS + ' - ' + HINCMCD.ENSEIGNE AS TRANSACTION_LOCATION,
                FORMAT(HCPCOMPTA_MCD.DATEQA, 'yyyy-MM-ddTHH:mm:ss') AS DATE_TRANSACTION,
                'C' AS TRANSACTION_STATUS_CODE,
                
                'HINCMCD - ' + HINCMCD.ENSEIGNE AS NAR,

                'Card - HINCMCD' AS MXP_SOURCE
                
            FROM [MISDW].[TRG].[ATM_HCPCOMPTA_MCD] AS HCPCOMPTA_MCD
            LEFT JOIN [MISDW].[TRG].[EQA_ACC_EXTERNAL_ACCOUNT_NUMBER] AS EQ_ORACLE ON EQ_ORACLE.NEAB + EQ_ORACLE.NEAN + EQ_ORACLE.NEAS = HCPCOMPTA_MCD.NUMCPT
            LEFT JOIN [MISDW].[TRG].[ATM_HINCMCD] AS HINCMCD ON
                                                                                                    HINCMCD.CPTEQA = HCPCOMPTA_MCD.NUMCPT
                                                                                            AND       HINCMCD.REFTRS = HCPCOMPTA_MCD.REFARC
                                                                                            AND HINCMCD.DAT_EQA = HCPCOMPTA_MCD.DATEQA
            LEFT JOIN [MISDW].[TRG].[T24_FBNK_CURRENCY] AS CURRENCY_1 ON CURRENCY_1.CURRENCY_CODE = HINCMCD.COD_DEV
            LEFT JOIN [MISDW].[GO_AML].[COUNTRIES_ISO_3166] AS COUNTRIES_ISO ON COUNTRIES_ISO.alpha_3 = HINCMCD.LOCALIS
            LEFT JOIN [MISDW].[GO_AML].[CURRENCY_CODES] AS CURRENCY_2 ON FORMAT(CURRENCY_2.NumericCode, '000') = FORMAT(HINCMCD.CODE_MON_ORG, '000')
            WHERE
                HCPCOMPTA_MCD.NUMCPT = '{account_number}'
                AND YEAR(HCPCOMPTA_MCD.DATEQA) = '{year}'
        """

        try:
            # Ensure the database connection is established
            self.connect()
            self._log('info', "Executing query for account: %s", account_number)

            # Execute the query with retry logic
            df = self.query_executor.retry_query_execution(query, self.connection, max_attempts=max_attempts)

            if df.empty:
                self._log('warning', "No cards trx found for account: %s", account_number)
            else:
                df['TRANSACTION_LOCATION'] = df['TRANSACTION_LOCATION'].apply(clean_text)
                self.card_transactions = pd.concat([self.card_transactions, df], ignore_index=True).copy(deep=True)
                #self.card_transactions_international = df
                self._log('info', "Query executed successfully; card trx data retrieved for account: %s", account_number)

        except Exception as e:
            self._log('error', "Error retrieving cards trx for account: %s. Error: %s", account_number, e)
            raise

        finally:
            # Close the database connection
            self.disconnect()
            self._log('info', "Database connection closed.")

        self._log('info', "Cleaning and returning the retrieved DataFrame.")

        

    def process_transactions(
        self,
        #card_transactions,
        account,
        account_type,
        account_related_person,
        account_related_cards
    ) -> pd.DataFrame:

        #print('============== 1 =================')
        #print(account_related_cards)
        #print('==================================')
        
        #self.card_transactions_processed = None
        
        data_list: List[dict] = []
        
        xml = XML()

        df_result = pd.DataFrame()
        
        if account_type != 'PM':
            #conductor_xml_t = [xml.create_xml_conductor(row, comments='Le titulaire du compte ou l un des cotitulaires (pour un compte joint) a ete designe') for _, row in account_related_person.iterrows()][0]
            #person_xml_t = [xml.create_xml_person(row, comments='Le titulaire du compte ou l un des cotitulaires (pour un compte joint) a ete designe') for _, row in account_related_person.iterrows()][0]

            # Make sure the dataframe is not empty
            if not account_related_person.empty:
            
                # Case 1: All rows are 'CST'
                if (account_related_person['ACCOUNT_TYPE'] == 'CST').all():
                    # Filter for the row where ROLE_ACCOUNT is 'TICPT'
                    ticpt_row = account_related_person[account_related_person['ROLE_ACCOUNT'] == 'TICPT']
                    if ticpt_row.empty:
                        raise ValueError("No row with ROLE_ACCOUNT = 'TICPT' found for CST accounts")
                    row = ticpt_row.iloc[0]  # Take the TICPT row
                    comment = 'Le titulaire du compte a ete designe'
                    conductor_xml_t = xml.create_xml_conductor(row, comments=comment)
                    person_xml_t = xml.create_xml_person(row, comments=comment)
            
                # Case 2: All rows are 'CJ'
                elif (account_related_person['ACCOUNT_TYPE'] == 'CJ').all():
                    row = account_related_person.iloc[0]  # Take the first row
                    comment = 'L un des cotitulaires (pour un compte joint) a ete designe'
                    conductor_xml_t = xml.create_xml_conductor(row, comments=comment)
                    person_xml_t = xml.create_xml_person(row, comments=comment)
            
                else:
                    # Optional: handle mixed types
                    raise ValueError("Mixed ACCOUNT_TYPE values are not supported")
            else:
                raise ValueError("account_related_person is empty")

        elif account_type == 'PM':
            #person_list = [row for _, row in account_related_person.iterrows() if row.ROLE_RE in ['signatory', 'RL']]
            person_list = [row for _, row in account_related_person.iterrows() if row.RELATED_PERSON_ROLE_CODE_ATB == 'SIGNATAIRE']
            conductor_xml_t = xml.create_xml_conductor(person_list[0], comments='Un tiers (appartenant au groupe des signataires (T24_EB_MANDATE) ou EQ_TIERS - TYPE_TIERS = REPRES-LEGAL) a ete designe') if person_list else "Aucun signataire n a ete trouve"
            person_xml_t = xml.create_xml_person(person_list[0], comments='Un tiers (appartenant au groupe des signataires (T24_EB_MANDATE) ou EQ_TIERS - TYPE_TIERS = REPRES-LEGAL) a ete designe') if person_list else "Aucun signataire n a ete trouve"
        
        print('card - model')
        print(self.card_transactions_to_process)
        for index, row in tqdm(self.card_transactions_to_process.iterrows(), total=len(self.card_transactions_to_process)):
            #print('============== 2 =================')
            #print(row['CARD_NUMBER'])
            #print('==================================')
            if row['CARD_NUMBER'] in account_related_cards:
                print('============== 3 =================')
                #print('IS IN')
                print(account_related_cards[row['CARD_NUMBER']])
                print('==================================')
                conductor_xml = xml.create_xml_conductor(account_related_cards[row['CARD_NUMBER']], comments="Is the holder of the card")
                person_xml = xml.create_xml_person(account_related_cards[row['CARD_NUMBER']])
                #print(conductor_xml)
            else:
                conductor_xml = conductor_xml_t
                person_xml = person_xml_t
            

            #trx = xml.create_transaction_xml(row)

            comment = (
                f"Op Carte: {row['MXP_SOURCE']} - {row['TRANSACTION_DESC_ATB_ACC']} - {row['TRANSACTION_CODE_ATB']}"
            )
            trx = xml.create_transaction_xml(row, comment=comment)
            
            obj_1 = xml.create_xml_OBJ(row, 1)
            obj_1 = obj_1.replace('PL3', conductor_xml + account)
            obj_1 = obj_1.replace('PL_CONDUCTOR', '')
            obj_1 = obj_1.replace('PL1', 'from_my_client')
            obj_1 = obj_1.replace('PL2', 'from')
            obj_1 = obj_1.replace('IB_', 'from_')
            trx = trx.replace('PL_FROM', obj_1)

            print("========= card ==============")
            print("trx ", trx)
            print("TRANSACTION_CODE_ATB", row['TRANSACTION_CODE_ATB'])
            print("TRANSACTION_NATURE", row['TRANSACTION_NATURE'])

            if row['TRANSACTION_NATURE'] == 'ATM_Withdrawal':
                print("case 1")
                obj_2 = xml.create_xml_OBJ(row, 2)
                print("1 ", obj_2)
                obj_2 = obj_2.replace('PL3', person_xml)
                obj_2 = obj_2.replace('PL_CONDUCTOR', '')
                print("2 ", obj_2)
                obj_2 = obj_2.replace('PL1', 'to_my_client')
                print("3 ", obj_2)
                obj_2 = obj_2.replace('PL2', 'to')
                print("4 ", obj_2)
                obj_2 = obj_2.replace('IB_', 'to_')
                print("5 ", obj_2)
                trx = trx.replace('PL_TO', obj_2)
                print("6 ", trx)
            elif row['TRANSACTION_NATURE'] == 'Card_Payment':
                print("case 2")
                entity_xml = xml.create_xml_entity_nc(row['NAR'])
                obj_2 = xml.create_xml_OBJ(row, 2)
                print("1 ", obj_2)
                obj_2 = obj_2.replace('PL3', entity_xml)
                obj_2 = obj_2.replace('PL_CONDUCTOR', '')
                print("2 ", obj_2)
                obj_2 = obj_2.replace('PL1', 'to')
                print("3 ", obj_2)
                obj_2 = obj_2.replace('PL2', 'to')
                print("4 ", obj_2)
                obj_2 = obj_2.replace('IB_', 'to_')
                print("5 ", obj_2)
                trx = trx.replace('PL_TO', obj_2)
                print("trx ", trx)

            # Extract and format the transaction date
            transaction_date = pd.to_datetime(row['DATE_TRANSACTION'][:-9]).strftime('%Y-%m-%d')
            # Append transaction data to the list
            data_list.append({'transaction_date': transaction_date, 'transaction_detail': trx})
        
        # Convert collected transaction data to DataFrame
        df_result = pd.DataFrame(data_list)
        
        self.card_transactions_processed = df_result.copy(deep=True)


    def clear_cache(self):
        self.card_transactions = pd.DataFrame()
        self.card_transactions_to_process = pd.DataFrame()
        self.card_transactions_processed = pd.DataFrame()

        self.account_related_cards = {}


