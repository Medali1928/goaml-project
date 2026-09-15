import time
from tqdm import tqdm
from typing import Optional, List
import pandas as pd
from src.helpers.xmlStructure import XML
from src.helpers.utils import clean_dataframe
from src.db.connection import DatabaseConnection
from src.db.query_executor import QueryExecutor
from src.helpers.logger_manager import LoggerManager


class Cashier(DatabaseConnection):
    def __init__(self, db_config: dict, log_enabled: bool = True) -> None:
        """
        Initialize the Cashier class with database configuration and logging options.

        Args:
            db_config (dict): Database configuration dictionary containing server, database, username, and password.
            log_enabled (bool): Whether to enable logging. Defaults to True.
        """
        super().__init__(db_config['server'], db_config['database'], db_config['username'], db_config['password'])
        self.logger_manager = LoggerManager(log_enabled)
        self.query_executor = QueryExecutor(self.connection)

        self.cashier_transactions = pd.DataFrame()
        self.cashier_transactions_to_process = pd.DataFrame()
        self.cashier_transactions_processed = pd.DataFrame()
        

    def _log(self, level: str, message: str, *args, **kwargs) -> None:
        """
        Log a message using the logger manager.

        Args:
            level (str): Logging level (e.g., 'info', 'warning', 'error').
            message (str): Log message format.
        """
        self.logger_manager.log(level, message, *args, **kwargs)

    def get_cashier_transactions(self, account: str, year: str, max_attempts: int = 1) -> pd.DataFrame:
        """
        Retrieve transaction details for a specific account and year.

        Args:
            account (str): The account number in the format BR+BN+SFX.
            year (str): The year for which the data is required.
            max_attempts (int): Maximum number of retry attempts. Defaults to 3.

        Returns:
            pd.DataFrame: A DataFrame containing the transaction details.
        """
        self._log('info', "Starting cashier's transactions retrieval for account: %s, year: %s", account, year)

        df = pd.DataFrame()

        query = f"""
        SELECT
            TRIM(CAST(CASHIER.PWABX AS VARCHAR) + CAST(CASHIER.PWANX AS VARCHAR) + CAST(CASHIER.PWASX AS VARCHAR)) AS EQ_ACCOUNT,
            TRIM(CAST(CASHIER.PWDRFX AS VARCHAR)) AS TRANSACTION_REF,
            TRIM(CAST(CASHIER.PWDATEX AS VARCHAR)) AS TRANSACTION_DATE,
            
            CASHIER.PWCCYX AS CURRENCY_CODE_1,
            FORMAT(CASHIER.PWAMTX / POWER(10, CURRENCY_1.NO_OF_DECIMALS), '0.##################') AS FOREIGN_AMOUNT_1,
            'TN' AS COUNTRY_1,
            
            CASE
                WHEN CASHIER.PWCCY2X IS NULL OR LTRIM(RTRIM(CASHIER.PWCCY2X)) = '' THEN CASHIER.PWCCYX
                ELSE CASHIER.PWCCY2X
            END AS CURRENCY_CODE_2,
            CASE 
            	WHEN CASHIER.PWAMT2X IS NOT NULL AND CASHIER.PWAMT2X <> 0 THEN FORMAT(CASHIER.PWAMT2X / POWER(10,
	            	CASE 
	            		WHEN CURRENCY_2.NO_OF_DECIMALS IS NOT NULL AND CURRENCY_2.NO_OF_DECIMALS <> '' THEN CURRENCY_2.NO_OF_DECIMALS
	            		ELSE CURRENCY_1.NO_OF_DECIMALS
	            	END
            	), '0.##################')
            	ELSE FORMAT(CASHIER.PWAMTX / POWER(10, CURRENCY_1.NO_OF_DECIMALS), '0.##################')
            END AS FOREIGN_AMOUNT_2,
            'TN' AS COUNTRY_2,
            
            --CASE
            --    WHEN CASHIER.PWCCYX = 'TND' THEN FORMAT(CASHIER.PWAMTX / POWER(10, CURRENCY_1.NO_OF_DECIMALS), '0.##################')
			--	WHEN CASHIER.PWCCY2X = 'TND' THEN FORMAT(CASHIER.PWAMT2X / POWER(10, CURRENCY_1.NO_OF_DECIMALS), '0.##################')
            --    ELSE FORMAT(CASHIER.PWAMTX / POWER(10, CURRENCY_1.NO_OF_DECIMALS) * CURRENCY_1.MID_REVAL_RATE, '0.##################')
            --END AS AMOUNT_LOCAL,
            
            '30' + '/' + TRIM(CASHIER.PWDRFX) + '/' + '20' + SUBSTRING(CONVERT(VARCHAR, CASHIER.PWDATEX), 2, 2) + ' ' +
            SUBSTRING(CONVERT(VARCHAR, CASHIER.PWDATEX), 4, 2) + ' ' + SUBSTRING(CONVERT(VARCHAR, CASHIER.PWDATEX), 6, 2) + 'T00:00:00' AS TRANSACTION_NUMBER,
            '20' + SUBSTRING(CONVERT(VARCHAR, CASHIER.PWDATEX), 2, 2) + '-' +
            SUBSTRING(CONVERT(VARCHAR, CASHIER.PWDATEX), 4, 2) + '-' + SUBSTRING(CONVERT(VARCHAR, CASHIER.PWDATEX), 6, 2) + 'T00:00:00' AS DATE_TRANSACTION,
            BRANCH.NAME AS TRANSACTION_LOCATION,
            'C' AS TRANSACTION_STATUS_CODE,
            CASE
                WHEN TRIM(CASHIER.PWNRX) + TRIM(CASHIER.PWNR2X) + TRIM(CASHIER.PWNR3X) = '' THEN 'N.A'
                ELSE TRIM(CASHIER.PWNRX) + TRIM(CASHIER.PWNR2X) + TRIM(CASHIER.PWNR3X)
            END AS NAR,

            'Cashier' AS SOURCE

        FROM [MISDW].[HIST].[EQA_CASHIER] AS CASHIER
        LEFT JOIN [MISDW].[TRG].[T24_FBNK_CURRENCY] AS CURRENCY_1 ON CURRENCY_1.CURRENCY_CODE = CASHIER.PWCCYX
        LEFT JOIN [MISDW].[TRG].[T24_FBNK_CURRENCY] AS CURRENCY_2 ON CURRENCY_2.CURRENCY_CODE = CASHIER.PWCCY2X
        LEFT JOIN [MISDW].[TRG].[T24_F_DEPT_ACCT_OFFICER] AS BRANCH ON BRANCH.ACCOUNT_OFFICER = CASHIER.PWBBNX
        WHERE
            TRIM(CAST(CASHIER.PWABX AS VARCHAR) + CAST(CASHIER.PWANX AS VARCHAR) + CAST(CASHIER.PWASX AS VARCHAR)) = '{account}'
            AND '20' + SUBSTRING(CONVERT(VARCHAR, CASHIER.PWDATEX), 2, 2) = '{year}'
        """

        try:
            # Ensure the connection is established
            self.connect()
            self._log('info', "Executing query for account: %s, year: %s", account, year)

            # Execute the query with retry logic
            df = self.query_executor.retry_query_execution(query, self.connection, max_attempts=max_attempts)

            if df.empty:
                self._log('warning', "No cashier's transactions data found for the account: %s, year: %s", account, year)
            else:
                
                self.cashier_transactions = clean_dataframe(df).copy(deep=True)
                self._log('info', "Query executed successfully; cashier's transactions data retrieved for the account.")

        except Exception as e:
            self._log('error', "Error retrieving cashier's transactions data for the account: %s, year: %s. Error: %s", account, year, e)
            raise
        finally:
            self.disconnect()
            self._log('info', "Database connection closed.")

        self._log('info', "Cleaning and returning the retrieved DataFrame.")

    def process_transactions(
        self,
        account: str,
        customer_id: str,
        account_type: str,
        account_related_person: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Processes transactions and creates an XML representation for each entry.

        Args:
            account (str): The account number.
            account_type (str): The type of the account (e.g., 'PPH', 'PPH_CJ', 'PM').
            account_related_person (pd.DataFrame): A DataFrame containing information about account-related persons.

        Returns:
            pd.DataFrame: A DataFrame with transaction dates and XML transaction details.
        """
        # Create an instance of XML helper class
        xml = XML()

        # Initialize an empty DataFrame for results
        df_result = pd.DataFrame(columns=['transaction_date', 'transaction_detail'])

        # Initialize a list for collecting transaction data
        data_list: List[dict] = []

        # Placeholder for conductor XML
        conductor_xml: str = ''

        # Logic for account types
        if account_type != 'PM':
            # Generate XML for person and conductor for PPH-related accounts
            #person_xml = [xml.create_xml_person(row, comments='Le titulaire du compte ou l un des cotitulaires (pour un compte joint) a ete designe') for _, row in account_related_person.iterrows()][0]
            #conductor_xml = [xml.create_xml_conductor(row, comments='Le titulaire du compte ou l un des cotitulaires (pour un compte joint) a ete designe') for _, row in account_related_person.iterrows()][0]
            # Make sure the dataframe is not empty

            print("écriture fichier transactions_to_process")
            try:
                self.cashier_transactions_to_process.to_csv("C:\GOAML\procopr.csv", index=False) 
                print("DataFrame saved to procopr.csv successfully.")
            except OSError as e:
                print(f"File error: {e}")

            if not account_related_person.empty:
            
                # Case 1: All rows are 'CST'
                if (account_related_person['ACCOUNT_TYPE'] == 'CST').all():
                    # Filter for the row where ROLE_ACCOUNT is 'TICPT'
                    ticpt_row = account_related_person[account_related_person['ROLE_ACCOUNT'] == 'TICPT']
                    if ticpt_row.empty:
                        raise ValueError("No row with ROLE_ACCOUNT = 'TICPT' found for CST accounts")
                    row = ticpt_row.iloc[0]  # Take the TICPT row
                    comment = 'Le titulaire du compte a ete designe'
                    conductor_xml = xml.create_xml_conductor(row, comments=comment)
                    person_xml = xml.create_xml_person(row, comments=comment)
            
                # Case 2: All rows are 'CJ'
                elif (account_related_person['ACCOUNT_TYPE'] == 'CJ').all():
                    row = account_related_person.iloc[0]  # Take the first row
                    comment = 'L un des cotitulaires (pour un compte joint) a ete designe'
                    conductor_xml = xml.create_xml_conductor(row, comments=comment)
                    person_xml = xml.create_xml_person(row, comments=comment)
                else:
                    # Optional: handle mixed types
                    raise ValueError("Mixed ACCOUNT_TYPE values are not supported")
                
        elif account_type == 'PM':
            # Filter related persons by a specific code
            #person_list = [row for _, row in account_related_person.iterrows() if row.RELATED_PERSON_RELATION_CODE_ATB == '309']
            person_list = [row for _, row in account_related_person.iterrows() if row.RELATED_PERSON_ROLE_CODE_ATB == 'SIGNATAIRE']
            person_xml = xml.create_xml_person(person_list[0], comments='Un tiers (appartenant au groupe des signataires (T24_EB_MANDATE) ou EQ_TIERS - TYPE_TIERS = REPRES-LEGAL) a ete designe') if person_list else f"Aucun signataire n a ete trouve pour : {customer_id}"
            conductor_xml = xml.create_xml_conductor(person_list[0], comments='Un tiers (appartenant au groupe des signataires (T24_EB_MANDATE) ou EQ_TIERS - TYPE_TIERS = REPRES-LEGAL) a ete designe') if person_list else f"Aucun signataire n a ete trouve pour : {customer_id}"#{account['customer_id']}
        # Iterate through transactions with progress bar
        for index, row in tqdm(self.cashier_transactions_to_process.iterrows(), total=len(self.cashier_transactions_to_process)):
            #print('++++')
            #print(row['TRANSACTIONLOCATION'])
            # Create a comment string from transaction details
            comment = (
                f"Op Cashier: {row['SOURCE']} - {row['TRANSACTION_DESC_ATB_ACC']} - {row['TRANSACTION_CODE_ATB']} - Narrative : {row['NAR']}"
            )
            # Generate base XML for transaction
            trx = xml.create_transaction_xml(row, comment=comment)

            # Logic for negative transaction amounts
            if row['TRANSACTION_AMOUNT'] < 0:
                obj_1 = xml.create_xml_OBJ(row, 1)
                obj_1 = obj_1.replace('PL3', conductor_xml + account)
                obj_1 = obj_1.replace('PL1', 'from_my_client')
                obj_1 = obj_1.replace('PL2', 'from')
                obj_1 = obj_1.replace('IB_', 'from_')
                trx = trx.replace('PL_FROM', obj_1)

                obj_2 = xml.create_xml_OBJ(row, 2)
                obj_2 = obj_2.replace('PL3', person_xml)
                obj_2 = obj_2.replace('PL1', 'to_my_client')
                obj_2 = obj_2.replace('PL2', 'to')
                obj_2 = obj_2.replace('IB_', 'to_')
                trx = trx.replace('PL_TO', obj_2)

            # Logic for positive transaction amounts
            if row['TRANSACTION_AMOUNT'] >= 0:
                obj_1 = xml.create_xml_OBJ(row, 1)
                obj_1 = obj_1.replace('PL3', account)
                obj_1 = obj_1.replace('PL1', 'to_my_client')
                obj_1 = obj_1.replace('PL2', 'to')
                obj_1 = obj_1.replace('IB_', 'to_')
                trx = trx.replace('PL_TO', obj_1)

                p_2 = conductor_xml + person_xml
                obj_2 = xml.create_xml_OBJ(row, 2)
                obj_2 = obj_2.replace('PL3', p_2)
                obj_2 = obj_2.replace('PL1', 'from_my_client')
                obj_2 = obj_2.replace('PL2', 'from')
                obj_2 = obj_2.replace('IB_', 'from_')
                trx = trx.replace('PL_FROM', obj_2)

            # Extract and format the transaction date
            transaction_date = pd.to_datetime(row['DATE_TRANSACTION'][:-9]).strftime('%Y-%m-%d')
            # Append transaction data to the list
            data_list.append({'transaction_date': transaction_date, 'transaction_detail': trx})

        # Convert collected transaction data to DataFrame
        df_result = pd.DataFrame(data_list)

        # Update the class attribute with processed transactions
        self.cashier_transactions_processed = df_result.copy(deep=True)

    def clear_cache(self):
        self.cashier_transactions = pd.DataFrame()
        self.cashier_transactions_to_process = pd.DataFrame()
        self.cashier_transactions_processed = pd.DataFrame()