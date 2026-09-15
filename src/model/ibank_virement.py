from tqdm import tqdm
import pandas as pd

from src.helpers.xmlStructure import XML
from src.helpers.utils import clean_dataframe
from src.db.connection import DatabaseConnection
from src.db.query_executor import QueryExecutor
from src.model.get_client import GetClient
from src.helpers.logger_manager import LoggerManager


class Virement(DatabaseConnection):
    def __init__(self, db_config: dict, log_enabled: bool = True) -> None:

        super().__init__(db_config['server'], db_config['database'], db_config['username'], db_config['password'])

        self.db_config = db_config

        self.logger_manager = LoggerManager(log_enabled)
        self.query_executor = QueryExecutor(self.connection)

        self.virement_transactions = pd.DataFrame()
        self.virement_transactions_to_process = pd.DataFrame()
        self.virement_transactions_processed = pd.DataFrame()

    def _log(self, level, message, *args, **kwargs):
        """Log a message if logging is enabled using the logger manager."""
        self.logger_manager.log(level, message, *args, **kwargs)

    # OK
    def get_virement_ca_ve(self, account: str, year: str, max_attempts: int = 1) -> pd.DataFrame:

        self._log('info', "Starting Virement_ca emis's transactions retrieval for account: %s, year: %s", account, year)
        self.connect()

        df = pd.DataFrame()

        try:
            query = f"""
            SELECT
                'Y' AS PART_1_IS_MY_CLIENT,
                'I' AS PART_1_ROLE,
                TRIM(TRIM(VIREMENT_EMIS.BRN_ACC) + TRIM(VIREMENT_EMIS.ACCOUNT_ID) + TRIM(VIREMENT_EMIS.SFX_ACC)) AS EQ_ACCOUNT,
                TRIM(VIREMENT_EMIS.POSTING_REF) AS TRANSACTION_REF,
                VIREMENT_EMIS.POSTING_DATE AS TRANSACTION_DATE,
                
                
                'A' AS FUND_CODE_1,
                VIREMENT_EMIS.COD_DEV AS CURRENCY_CODE_1,
                'TN' AS COUNTRY_1,
                VIREMENT_EMIS.LOCAL_AMOUNT AS FOREIGN_AMOUNT_1,
                
                
                'N' AS PART_2_IS_MY_CLIENT,
                '' AS PART_2_TYPE,
                'B' AS PART_2_ROLE,
                '' AS PART_2_ACCOUNT,
                '<IB_account>' +
                    '<institution_name>' +
                    CASE
                        WHEN TRIM(ISNULL(BANQUE_TN_DETAILS.LIBBQE, '')) = '' THEN 'N.A'
                    ELSE BANQUE_TN_DETAILS.LIBBQE
                    END + 
                    '</institution_name>' +
                    '<swift>' + 
                    CASE
                        WHEN TRIM(ISNULL(BANQUE_TN_DETAILS.ADRSWIFT, '')) = '' THEN 'N.A'
                        --WHEN LEN(BANQUE_TN_DETAILS.ADRSWIFT) > 11 THEN 'N.A'
                        ELSE BANQUE_TN_DETAILS.ADRSWIFT
                    END + 
                    '</swift>' +
                    '<institution_country>TN</institution_country>' +
                    '<account>' + 
                    CASE
                        WHEN TRIM(ISNULL(VIREMENT_EMIS.BENIF_RIB, '')) = '' THEN 'N.A'	-- RIB
                        ELSE VIREMENT_EMIS.BENIF_RIB
                    END + 
                    '</account>' +
                '</IB_account>' AS PART_2_DETAILS,
                
                
                'A' AS FUND_CODE_2,
                VIREMENT_EMIS.COD_DEV AS CURRENCY_CODE_2,
                'TN' AS COUNTRY_2,
                VIREMENT_EMIS.LOCAL_AMOUNT AS FOREIGN_AMOUNT_2,
                
                
                '30' + '/' + VIREMENT_EMIS.TRANSACTION_NUMBER + '/' +
				CAST(YEAR(VIREMENT_EMIS.POSTING_DATE) AS NVARCHAR(4)) + ' ' +
				RIGHT('0' + CAST(MONTH(VIREMENT_EMIS.POSTING_DATE) AS NVARCHAR(2)), 2) + ' ' +
				RIGHT('0' + CAST(DAY(VIREMENT_EMIS.POSTING_DATE) AS NVARCHAR(2)), 2) AS TRANSACTION_NUMBER,
                'TN' AS TRANSACTION_LOCATION,
                CAST(YEAR(VIREMENT_EMIS.POSTING_DATE) AS NVARCHAR(4)) + '-' +
				RIGHT('0' + CAST(MONTH(VIREMENT_EMIS.POSTING_DATE) AS NVARCHAR(2)), 2) + '-' +
				RIGHT('0' + CAST(DAY(VIREMENT_EMIS.POSTING_DATE) AS NVARCHAR(2)), 2) + 'T00:00:00' AS DATE_TRANSACTION,
                VIREMENT_EMIS.TRANS_CODE_DESC AS TRANS_CODE_DESC_ATB,
                VIREMENT_EMIS.TRANS_CODE AS TRANSMODE_CODE_ATB,
                'B399' AS TRANSACTION_CODE_GOAML,
                VIREMENT_EMIS.LOCAL_AMOUNT AS AMOUNT_LOCAL,
                'C' AS TRANSACTION_STATUS_CODE,

                ' VIREMENT_EMIS AB ' AS NAR,

                'VIREMENT_EMIS' AS SOURCE

            FROM
                [MISDW].[GO_AML].[IBANK_VIREMENT_EMIS] AS VIREMENT_EMIS
            LEFT JOIN
                [MISDW].[GO_AML].[BANQUE TN DETAILS] AS BANQUE_TN_DETAILS ON RIGHT('00' + BANQUE_TN_DETAILS.CODBQE, 2) = RIGHT('00' + VIREMENT_EMIS.BENIF_BQE, 2)
			WHERE
				YEAR(VIREMENT_EMIS.POSTING_DATE) = '{year}'
				AND VIREMENT_EMIS.BRN_ACC + VIREMENT_EMIS.ACCOUNT_ID + VIREMENT_EMIS.SFX_ACC = '{account}'
            """

            # Retry logic for query execution
            self._log('info', "Executing query with max_attempts: %d", max_attempts)
            df = self.query_executor.retry_query_execution(query, self.connection, max_attempts=max_attempts)

            if df.empty:
                self._log('warning', "No Virement_ca emis's transactions data found for the account: %s, year: %s", account, year)
            else:
                #self.virement_transactions = pd.concat([self.virement_transactions, clean_dataframe(df)], ignore_index=True)
                self.virement_transactions = pd.concat(
                    [self.virement_transactions.copy(), clean_dataframe(df)], 
                    ignore_index=True
                )

                self._log('info', "Query executed successfully; Virement_ca emis's transactions data retrieved for the account.")
        except Exception as e:
            self._log('error', "Error retrieving Virement_ca emis's transactions data for the account: %s, year: %s, error: %s", account, year, e)
            raise
        finally:
            self._log('info', "Closing database connection.")
            self.disconnect()

        self._log('info', "Returning cleaned DataFrame.")
    
    # OK
    def get_virement_ca_vr(self, account: str, year: str, max_attempts: int = 1) -> pd.DataFrame:

        self._log('info', "Starting Virement_ca recu's transactions retrieval for account: %s, year: %s", account, year)
        self.connect()

        df = pd.DataFrame()

        try:
            query = f"""
            SELECT
                'Y' AS PART_1_IS_MY_CLIENT,
                'B' AS PART_1_ROLE,
                TRIM(TRIM(VIREMENT_RECU.BRN_ACC) + TRIM(VIREMENT_RECU.ACCOUNT_ID) + TRIM(VIREMENT_RECU.SFX_ACC)) AS EQ_ACCOUNT,
                TRIM(VIREMENT_RECU.POSTING_REF) AS TRANSACTION_REF,
                VIREMENT_RECU.POSTING_DATE AS TRANSACTION_DATE,
                
                
                'A' AS FUND_CODE_1,
                VIREMENT_RECU.COD_DEV AS CURRENCY_CODE_1,
                'TN' AS COUNTRY_1,
                VIREMENT_RECU.LOCAL_AMOUNT AS FOREIGN_AMOUNT_1,
                
                
                'N' AS PART_2_IS_MY_CLIENT,
                '' AS PART_2_TYPE,
                'I' AS PART_2_ROLE,
                '' AS PART_2_ACCOUNT,
                '<IB_account>' +
                    '<institution_name>' +
                    CASE
                        WHEN TRIM(ISNULL(BANQUE_TN_DETAILS.LIBBQE, '')) = '' THEN 'N.A'
                    ELSE BANQUE_TN_DETAILS.LIBBQE
                    END + 
                    '</institution_name>' +
                    '<swift>' + 
                    CASE
                        WHEN TRIM(ISNULL(BANQUE_TN_DETAILS.ADRSWIFT, '')) = '' THEN 'N.A'
                        --WHEN LEN(BANQUE_TN_DETAILS.ADRSWIFT) > 11 THEN 'N.A'
                        ELSE BANQUE_TN_DETAILS.ADRSWIFT
                    END + 
                    '</swift>' +
                    '<institution_country>TN</institution_country>' +
                    '<account>' + 
                    CASE
                        WHEN TRIM(ISNULL(VIREMENT_RECU.INITIATEUR_RIB, '')) = '' THEN 'N.A'	-- RIB
                        ELSE VIREMENT_RECU.INITIATEUR_RIB
                    END + 
                    '</account>' +
                '</IB_account>' AS PART_2_DETAILS,
                
                
                'A' AS FUND_CODE_2,
                VIREMENT_RECU.COD_DEV AS CURRENCY_CODE_2,
                'TN' AS COUNTRY_2,
                VIREMENT_RECU.LOCAL_AMOUNT AS FOREIGN_AMOUNT_2,
                
                
                '30' + '/' + VIREMENT_RECU.TRANSACTION_NUMBER + '/' +
				CAST(YEAR(VIREMENT_RECU.POSTING_DATE) AS NVARCHAR(4)) + ' ' +
				RIGHT('0' + CAST(MONTH(VIREMENT_RECU.POSTING_DATE) AS NVARCHAR(2)), 2) + ' ' +
				RIGHT('0' + CAST(DAY(VIREMENT_RECU.POSTING_DATE) AS NVARCHAR(2)), 2) AS TRANSACTION_NUMBER,
                'TN' AS TRANSACTION_LOCATION,
                CAST(YEAR(VIREMENT_RECU.POSTING_DATE) AS NVARCHAR(4)) + '-' +
				RIGHT('0' + CAST(MONTH(VIREMENT_RECU.POSTING_DATE) AS NVARCHAR(2)), 2) + '-' +
				RIGHT('0' + CAST(DAY(VIREMENT_RECU.POSTING_DATE) AS NVARCHAR(2)), 2) + 'T00:00:00' AS DATE_TRANSACTION,
                VIREMENT_RECU.TRANS_CODE_DESC AS TRANS_CODE_DESC_ATB,
                VIREMENT_RECU.TRANS_CODE AS TRANSMODE_CODE_ATB,
                'B399' AS TRANSACTION_CODE_GOAML,
                VIREMENT_RECU.LOCAL_AMOUNT AS AMOUNT_LOCAL,
                'C' AS TRANSACTION_STATUS_CODE,

                ' VIREMENT_RECU AB '  AS NAR,

                'VIREMENT_RECU' AS SOURCE

            FROM
                [MISDW].[GO_AML].[IBANK_VIREMENT_RECU] AS VIREMENT_RECU
            LEFT JOIN
                [MISDW].[GO_AML].[BANQUE TN DETAILS] AS BANQUE_TN_DETAILS ON RIGHT('00' + BANQUE_TN_DETAILS.CODBQE, 2) = RIGHT('00' + VIREMENT_RECU.INITIATEUR_BQE, 2)
			WHERE
				YEAR(VIREMENT_RECU.POSTING_DATE) = '{year}'
				AND VIREMENT_RECU.BRN_ACC + VIREMENT_RECU.ACCOUNT_ID + VIREMENT_RECU.SFX_ACC = '{account}'
            """

            # Retry logic for query execution
            self._log('info', "Executing query with max_attempts: %d", max_attempts)
            df = self.query_executor.retry_query_execution(query, self.connection, max_attempts=max_attempts)

            if df.empty:
                self._log('warning', "No Virement_ca recu's transactions data found for the account: %s, year: %s", account, year)
            else:
                self.virement_transactions = pd.concat(
                    [self.virement_transactions.copy(), clean_dataframe(df)], 
                    ignore_index=True
                )

                self._log('info', "Query executed successfully; Virement_ca recu's transactions data retrieved for the account.")
        except Exception as e:
            self._log('error', "Error retrieving Virement_ca recu's transactions data for the account: %s, year: %s, error: %s", account, year, e)
            raise
        finally:
            self._log('info', "Closing database connection.")
            self.disconnect()

        self._log('info', "Returning cleaned DataFrame.")

    # OK
    def get_virement_cc_ve(self, account: str, year: str, max_attempts: int = 1) -> pd.DataFrame:

        self._log('info', "Starting Virement_cc emis's transactions retrieval for account: %s, year: %s", account, year)
        self.connect()

        df = pd.DataFrame()

        try:
            query = f"""
            SELECT
                'Y' AS PART_1_IS_MY_CLIENT,
                'I' AS PART_1_ROLE,
                TRIM(TRIM(VIREMENT_EMIS_MEME_BQE.BRN_ACC) + TRIM(VIREMENT_EMIS_MEME_BQE.ACCOUNT_ID) + TRIM(VIREMENT_EMIS_MEME_BQE.SFX_ACC)) AS EQ_ACCOUNT,
                TRIM(VIREMENT_EMIS_MEME_BQE.POSTING_REF) AS TRANSACTION_REF,
                VIREMENT_EMIS_MEME_BQE.POSTING_DATE AS TRANSACTION_DATE,
                
                'A' AS FUND_CODE_1,
                VIREMENT_EMIS_MEME_BQE.COD_DEV AS CURRENCY_CODE_1,
                'TN' AS COUNTRY_1,
                VIREMENT_EMIS_MEME_BQE.LOCAL_AMOUNT AS FOREIGN_AMOUNT_1,
                            
                'Y' AS PART_2_IS_MY_CLIENT,
                'ACCOUNT' AS PART_2_TYPE,
                'B' AS PART_2_ROLE,
                EQ_ORACLE.NEAB + EQ_ORACLE.NEAN + EQ_ORACLE.NEAS AS PART_2_ACCOUNT,
                '' AS PART_2_DETAILS,
                
                'A' AS FUND_CODE_2,
                VIREMENT_EMIS_MEME_BQE.COD_DEV AS CURRENCY_CODE_2,
                'TN' AS COUNTRY_2,
                VIREMENT_EMIS_MEME_BQE.LOCAL_AMOUNT AS FOREIGN_AMOUNT_2,
                
                '30' + '/' + VIREMENT_EMIS_MEME_BQE.TRANSACTION_NUMBER + '/' +
                    CAST(YEAR(VIREMENT_EMIS_MEME_BQE.POSTING_DATE) AS NVARCHAR(4)) + ' ' +
                    RIGHT('0' + CAST(MONTH(VIREMENT_EMIS_MEME_BQE.POSTING_DATE) AS NVARCHAR(2)), 2) + ' ' +
                    RIGHT('0' + CAST(DAY(VIREMENT_EMIS_MEME_BQE.POSTING_DATE) AS NVARCHAR(2)), 2) AS TRANSACTION_NUMBER,
                'TN' AS TRANSACTION_LOCATION,
                CAST(YEAR(VIREMENT_EMIS_MEME_BQE.POSTING_DATE) AS NVARCHAR(4)) + '-' +
                    RIGHT('0' + CAST(MONTH(VIREMENT_EMIS_MEME_BQE.POSTING_DATE) AS NVARCHAR(2)), 2) + '-' +
                    RIGHT('0' + CAST(DAY(VIREMENT_EMIS_MEME_BQE.POSTING_DATE) AS NVARCHAR(2)), 2) + 'T00:00:00' AS DATE_TRANSACTION,
                VIREMENT_EMIS_MEME_BQE.TRANS_CODE_DESC AS TRANS_CODE_DESC_ATB,
                VIREMENT_EMIS_MEME_BQE.TRANS_CODE AS TRANSMODE_CODE_ATB,
                'B117' AS TRANSACTION_CODE_GOAML,
                VIREMENT_EMIS_MEME_BQE.LOCAL_AMOUNT AS AMOUNT_LOCAL,
                'C' AS TRANSACTION_STATUS_CODE,

                ' BENIF_OPE ' + VIREMENT_EMIS_MEME_BQE.BENIF_OPE AS NAR,

                'VIREMENT_EMIS_MEME_BQE' AS SOURCE
                
            FROM [MISDW].[GO_AML].[IBANK_VIREMENT_EMIS_MEME_BQE] AS VIREMENT_EMIS_MEME_BQE
            LEFT JOIN [MISDW].[TRG].[EQA_ACC_EXTERNAL_ACCOUNT_NUMBER] AS EQ_ORACLE ON EQ_ORACLE.NEEAN = VIREMENT_EMIS_MEME_BQE.BENIF_NYMCPT
            WHERE
                YEAR(VIREMENT_EMIS_MEME_BQE.POSTING_DATE) = '{year}'--'2024'
                AND VIREMENT_EMIS_MEME_BQE.BRN_ACC + VIREMENT_EMIS_MEME_BQE.ACCOUNT_ID + VIREMENT_EMIS_MEME_BQE.SFX_ACC = '{account}'--'5838234740501'
            """

            # Retry logic for query execution
            self._log('info', "Executing query with max_attempts: %d", max_attempts)
            df = self.query_executor.retry_query_execution(query, self.connection, max_attempts=max_attempts)

            if df.empty:
                self._log('warning', "No Virement_cc emis's transactions data found for the account: %s, year: %s", account, year)
            else:
                self.virement_transactions = pd.concat(
                    [self.virement_transactions.copy(), clean_dataframe(df)], 
                    ignore_index=True
                )

                self._log('info', "Query executed successfully; Virement_cc emis's transactions data retrieved for the account.")
        except Exception as e:
            self._log('error', "Error retrieving Virement_cc emis's transactions data for the account: %s, year: %s, error: %s", account, year, e)
            raise
        finally:
            self._log('info', "Closing database connection.")
            self.disconnect()

        self._log('info', "Returning cleaned DataFrame.")
    
    # OK
    def get_virement_cc_vr(self, account: str, year: str, max_attempts: int = 1) -> pd.DataFrame:

        self._log('info', "Starting Virement_cc recu's transactions retrieval for account: %s, year: %s", account, year)
        self.connect()

        df = pd.DataFrame()

        try:
            query = f"""
            SELECT
                'Y' AS PART_1_IS_MY_CLIENT,
                'B' AS PART_1_ROLE,
                TRIM(TRIM(VIREMENT_RECU_MEME_BQE.BRN_ACC) + TRIM(VIREMENT_RECU_MEME_BQE.ACCOUNT_ID) + TRIM(VIREMENT_RECU_MEME_BQE.SFX_ACC)) AS EQ_ACCOUNT,
                TRIM(VIREMENT_RECU_MEME_BQE.POSTING_REF) AS TRANSACTION_REF,
                VIREMENT_RECU_MEME_BQE.POSTING_DATE AS TRANSACTION_DATE,
                
                'A' AS FUND_CODE_1,
                VIREMENT_RECU_MEME_BQE.COD_DEV AS CURRENCY_CODE_1,
                'TN' AS COUNTRY_1,
                VIREMENT_RECU_MEME_BQE.LOCAL_AMOUNT AS FOREIGN_AMOUNT_1,
                            
                'Y' AS PART_2_IS_MY_CLIENT,
                'ACCOUNT' AS PART_2_TYPE,
                'I' AS PART_2_ROLE,
                EQ_ORACLE.NEAB + EQ_ORACLE.NEAN + EQ_ORACLE.NEAS AS PART_2_ACCOUNT,
                '' AS PART_2_DETAILS,
                
                'A' AS FUND_CODE_2,
                VIREMENT_RECU_MEME_BQE.COD_DEV AS CURRENCY_CODE_2,
                'TN' AS COUNTRY_2,
                VIREMENT_RECU_MEME_BQE.LOCAL_AMOUNT AS FOREIGN_AMOUNT_2,
                
                '30' + '/' + VIREMENT_RECU_MEME_BQE.TRANSACTION_NUMBER + '/' +
                    CAST(YEAR(VIREMENT_RECU_MEME_BQE.POSTING_DATE) AS NVARCHAR(4)) + ' ' +
                    RIGHT('0' + CAST(MONTH(VIREMENT_RECU_MEME_BQE.POSTING_DATE) AS NVARCHAR(2)), 2) + ' ' +
                    RIGHT('0' + CAST(DAY(VIREMENT_RECU_MEME_BQE.POSTING_DATE) AS NVARCHAR(2)), 2) AS TRANSACTION_NUMBER,
                'TN' AS TRANSACTION_LOCATION,
                CAST(YEAR(VIREMENT_RECU_MEME_BQE.POSTING_DATE) AS NVARCHAR(4)) + '-' +
                    RIGHT('0' + CAST(MONTH(VIREMENT_RECU_MEME_BQE.POSTING_DATE) AS NVARCHAR(2)), 2) + '-' +
                    RIGHT('0' + CAST(DAY(VIREMENT_RECU_MEME_BQE.POSTING_DATE) AS NVARCHAR(2)), 2) + 'T00:00:00' AS DATE_TRANSACTION,
                VIREMENT_RECU_MEME_BQE.TRANS_CODE_DESC AS TRANS_CODE_DESC_ATB,
                VIREMENT_RECU_MEME_BQE.TRANS_CODE AS TRANSMODE_CODE_ATB,
                'B117' AS TRANSACTION_CODE_GOAML,
                VIREMENT_RECU_MEME_BQE.LOCAL_AMOUNT AS AMOUNT_LOCAL,
                'C' AS TRANSACTION_STATUS_CODE,

                ' INITIATEUR : ' + VIREMENT_RECU_MEME_BQE.INITIATEUR_OPE AS NAR,

                'VIREMENT_RECU_MEME_BQE' AS SOURCE
                
            FROM [MISDW].[GO_AML].[IBANK_VIREMENT_RECU_MEME_BQE] AS VIREMENT_RECU_MEME_BQE
            LEFT JOIN [MISDW].[TRG].[EQA_ACC_EXTERNAL_ACCOUNT_NUMBER] AS EQ_ORACLE ON EQ_ORACLE.NEEAN = VIREMENT_RECU_MEME_BQE.INITIATEUR_NYMCPT
			WHERE
				YEAR(VIREMENT_RECU_MEME_BQE.POSTING_DATE) = '{year}'
                AND VIREMENT_RECU_MEME_BQE.BRN_ACC + VIREMENT_RECU_MEME_BQE.ACCOUNT_ID + VIREMENT_RECU_MEME_BQE.SFX_ACC = '{account}' -- 5822533147500 2024
            """

            # Retry logic for query execution
            self._log('info', "Executing query with max_attempts: %d", max_attempts)
            df = self.query_executor.retry_query_execution(query, self.connection, max_attempts=max_attempts)

            if df.empty:
                self._log('warning', "No Virement_cc recu's transactions data found for the account: %s, year: %s", account, year)
            else:
                self.virement_transactions = pd.concat(
                    [self.virement_transactions.copy(), clean_dataframe(df)], 
                    ignore_index=True
                )
                

                self._log('info', "Query executed successfully; Virement_cc recu's transactions data retrieved for the account.")
        except Exception as e:
            self._log('error', "Error retrieving Virement_cc recu's transactions data for the account: %s, year: %s, error: %s", account, year, e)
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


        if party_type != 'PM':
            #conductor_xml_1 = [xml.create_xml_conductor(row, comments='Le titulaire du compte ou l un des cotitulaires (pour un compte joint) a ete designe') for idx, row in party_related_person.iterrows()][0]

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
                    conductor_xml_1 = xml.create_xml_conductor(row, comments=comment)
                    #person_xml_t = xml.create_xml_person(row, comments=comment)
            
                # Case 2: All rows are 'CJ'
                elif (party_related_person['ACCOUNT_TYPE'] == 'CJ').all():
                    row = party_related_person.iloc[0]  # Take the first row
                    comment = 'L un des cotitulaires (pour un compte joint) a ete designe'
                    conductor_xml_1 = xml.create_xml_conductor(row, comments=comment)
                    #person_xml_t = xml.create_xml_person(row, comments=comment)
            
                else:
                    # Optional: handle mixed types
                    raise ValueError("Mixed ACCOUNT_TYPE values are not supported")
            else:
                raise ValueError("account_related_person is empty")

        elif party_type == 'PM':
            if not party_related_person.empty:
                #person_list = [row for _, row in party_related_person.iterrows() if row.ROLE_RE ['signatory', 'RL']]
                person_list = [row for _, row in party_related_person.iterrows() if row.RELATED_PERSON_ROLE_CODE_ATB == 'SIGNATAIRE']
                conductor_xml_1 = xml.create_xml_conductor(person_list[0], comments='Un tiers (appartenant au groupe des signataires (T24_EB_MANDATE) ou EQ_TIERS - TYPE_TIERS = REPRES-LEGAL) a ete designe') if person_list else f"Aucun signataire n a ete trouve pour : {party_customer_id}"
            else:
                conductor_xml_1 = 'Aucun signataire n a ete trouve'

        valid_accounts = self.virement_transactions['PART_2_ACCOUNT']
        valid_accounts = valid_accounts.str.strip()  # Trim whitespace
        valid_accounts = valid_accounts[valid_accounts.ne('')].dropna().unique()  # Remove '' and NaN

        for p_acc in tqdm(valid_accounts, total=len(valid_accounts), desc="Retrieve account details (PART_2)"):
            account_correspondences, account_details, customer_id, account_type, account_rp = get_client.get_client_details(p_acc)
            account = {
                'account_correspondences': account_correspondences,
                'account_detail': account_details,
                'customer_id': customer_id,
                'account_type': account_type,
                'account_rp': account_rp
            }
            initiator_dict[p_acc] = account

        # 2026-01-12
        # Reset index
        self.virement_transactions_to_process = self.virement_transactions_to_process.reset_index(drop=True)
        # Clean column names thoroughly
        self.virement_transactions_to_process.columns = (
            self.virement_transactions_to_process.columns
            .astype(str)  # Ensure strings
            .str.strip()
            .str.replace('\u00a0', '', regex=False)  # Non-breaking space
            .str.replace('\xa0', '', regex=False)    # Another non-breaking space
            .str.replace(' ', '', regex=False)        # Regular space
            .str.replace('\t', '', regex=False)       # Tab
            .str.replace('\n', '', regex=False)       # Newline
        )

        import re
        # Check column names more carefully
        for col in self.virement_transactions_to_process.columns:
            print(f"Column: '{col}' | Repr: {repr(col)} | Length: {len(col)}")


        # 2026-01-12
        #for idx, row in tqdm(self.virement_transactions_to_process.iterrows(), total=len(self.virement_transactions_to_process)):
        tmp_df = pd.DataFrame()
        tmp_df = self.virement_transactions_to_process.copy(deep=True)

        for idx in tqdm(tmp_df.index, total=len(tmp_df)):

            #row = self.virement_transactions_to_process.loc[idx]
            row_trx = tmp_df.loc[idx]
            # Redefine row to ensure it has all DataFrame columns
            #row = row.reindex(self.virement_transactions_to_process.columns)

            # Check row's columns list     
            print(f"\n--- Row {idx} ---")
            print(f"Row columns: {row_trx.index.tolist()}")
            # Check values of each column
            for col, val in row_trx.items():
                print(f"  {col:30s} = {repr(val)}")  # repr() shows type info
            print(f"{'='*60}")

            account = ''
            person_list = []
            conductor_xml_2 = ''

            comment = (
                f"Op IBANK: {row_trx['SOURCE']} - {row_trx['TRANSACTION_DESC_ATB_ACC']} - {row_trx['TRANSACTION_CODE_ATB']} - Narrative : {row_trx['NAR']}"
            )

            trx = xml.create_transaction_xml(row_trx, comment=comment)
            
            if(row_trx['PART_1_ROLE'] == 'I'): # partie = conductor + PPH # Emis
                obj_1 = ''
                p_1 = conductor_xml_1 + party # already gotten
                obj_1 = xml.create_xml_OBJ(row_trx, 1)
                obj_1 = obj_1.replace('PL3', p_1)
                obj_1 = obj_1.replace('PL_CONDUCTOR', '')
                obj_1 = obj_1.replace('PL1', 'from_my_client')
                obj_1 = obj_1.replace('PL2', 'from')
                obj_1 = obj_1.replace('IB_', 'from_')

                trx = trx.replace('PL_FROM', obj_1)
                

                if(row_trx['PART_2_IS_MY_CLIENT'] == 'Y'):
                    try:
                        account = initiator_dict[row_trx.PART_2_ACCOUNT]
                        obj_2 = ''
                        p_2 = account['account_detail']
                        obj_2 = xml.create_xml_OBJ(row_trx, 2)
                        obj_2 = obj_2.replace('PL3', p_2)
                        obj_2 = obj_2.replace('PL_CONDUCTOR', '')
                        obj_2 = obj_2.replace('PL1', 'to_my_client')
                        obj_2 = obj_2.replace('PL2', 'to')
                        obj_2 = obj_2.replace('IB_', 'to_')
                        trx = trx.replace('PL_TO', obj_2)
                    except KeyError:
                        print(f"Contrepartie Virement {row_trx.PART_2_ACCOUNT} introuvable (donnée manquante), bloc t_to générique utilisé")
                        obj_2 = xml.create_xml_OBJ(row_trx, 2)
                        obj_2 = obj_2.replace('PL3', """
         <IB_account>
            <institution_name>UNKNOWN</institution_name>
            <swift>UNKNOWNXX</swift>
            <institution_country>TN</institution_country>
            <account>UNKNOWN</account>
         </IB_account>
        """)
                        obj_2 = obj_2.replace('PL_CONDUCTOR', '')
                        obj_2 = obj_2.replace('PL1', 'to')
                        obj_2 = obj_2.replace('PL2', 'to')
                        obj_2 = obj_2.replace('IB_', 'to_')
                        trx = trx.replace('PL_TO', obj_2)

                if(row_trx['PART_2_IS_MY_CLIENT'] == 'N'):
                    obj_2 = ''
                    p_2 = row_trx.PART_2_DETAILS
                    obj_2 = xml.create_xml_OBJ(row_trx, 2)
                    obj_2 = obj_2.replace('PL3', p_2)
                    obj_2 = obj_2.replace('PL_CONDUCTOR', '')
                    obj_2 = obj_2.replace('PL1', 'to')
                    obj_2 = obj_2.replace('PL2', 'to')
                    obj_2 = obj_2.replace('IB_', 'to_')
                    trx = trx.replace('PL_TO', obj_2)
                    
            
            if(row_trx['PART_1_ROLE'] == 'B'): # partie = PPH # Recue
                # prob
                obj_1 = ''
                p_1 = party # already gotten
                obj_1 = xml.create_xml_OBJ(row_trx, 1)
                obj_1 = obj_1.replace('PL3', p_1)
                obj_1 = obj_1.replace('PL_CONDUCTOR', '')
                obj_1 = obj_1.replace('PL1', 'to_my_client')
                obj_1 = obj_1.replace('PL2', 'to')
                obj_1 = obj_1.replace('IB_', 'to_')
                trx = trx.replace('PL_TO', obj_1)

                print('**********22222222222**************')
                print(row_trx)
                print(row_trx.PART_2_IS_MY_CLIENT)
                print(row_trx.PART_2_ROLE)
                print(row_trx.PART_2_ACCOUNT)
                print('**********22222***************')

                
                if(row_trx['PART_2_IS_MY_CLIENT'] == 'Y'):
                    try:
                        account = initiator_dict[row_trx.PART_2_ACCOUNT]
                    except KeyError:
                        print(f"Contrepartie Virement {row_trx.PART_2_ACCOUNT} introuvable (donnée manquante), ligne ignorée")
                        continue

                    if account['account_type'] != 'PM':
                        account_related_person = account['account_rp']
                        #conductor_xml_2 = [xml.create_xml_conductor(row, comments='Le titulaire du compte ou l un des cotitulaires (pour un compte joint) a ete designe') for idx, row in account['account_rp'].iterrows()][0]
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
                                conductor_xml_2 = xml.create_xml_conductor(row, comments=comment)
                                #person_xml_t = xml.create_xml_person(row, comments=comment)
                        
                            # Case 2: All rows are 'CJ'
                            elif (account_related_person['ACCOUNT_TYPE'] == 'CJ').all():
                                row = account_related_person.iloc[0]  # Take the first row
                                comment = 'L un des cotitulaires (pour un compte joint) a ete designe'
                                conductor_xml_2 = xml.create_xml_conductor(row, comments=comment)
                                #person_xml_t = xml.create_xml_person(row, comments=comment)
                        
                            else:
                                # Optional: handle mixed types
                                raise ValueError("Mixed ACCOUNT_TYPE values are not supported")
                        else:
                            raise ValueError("account_related_person is empty")
                        ###
                    elif account['account_type'] == 'PM':
                        #person_list = [row for _, row in account['account_rp'].iterrows() if row.ROLE_RE in ['signatory', 'RL']]
                        person_list = [row for _, row in account['account_rp'].iterrows() if row.RELATED_PERSON_ROLE_CODE_ATB == 'SIGNATAIRE']
                        conductor_xml_2 = xml.create_xml_conductor(person_list[0], comments='Un tiers (appartenant au groupe des signataires (T24_EB_MANDATE) ou EQ_TIERS - TYPE_TIERS = REPRES-LEGAL) a ete designe') if person_list else f"Aucun signataire n a ete trouve pour : {account['customer_id']}"

                    obj_2 = ''
                    p_2 = conductor_xml_2 + account['account_detail']
                    obj_2 = xml.create_xml_OBJ(row_trx, 2)
                    obj_2 = obj_2.replace('PL3', p_2)
                    obj_2 = obj_2.replace('PL_CONDUCTOR', '')
                    obj_2 = obj_2.replace('PL1', 'from_my_client')
                    obj_2 = obj_2.replace('PL2', 'from')
                    obj_2 = obj_2.replace('IB_', 'from_')
                    trx = trx.replace('PL_FROM', obj_2)
                    

                if(row_trx['PART_2_IS_MY_CLIENT'] == 'N'):
                    obj_2 = ''
                    p_2 = row_trx['PART_2_DETAILS']
                    obj_2 = xml.create_xml_OBJ(row_trx, 2)
                    obj_2 = obj_2.replace('PL3', p_2)
                    obj_2 = obj_2.replace('PL_CONDUCTOR', '')
                    obj_2 = obj_2.replace('PL1', 'from')
                    obj_2 = obj_2.replace('PL2', 'from')
                    obj_2 = obj_2.replace('IB_', 'from_')
                    trx = trx.replace('PL_FROM', obj_2)
                    
            
            transaction_date = pd.to_datetime(row_trx['DATE_TRANSACTION'][:-9]).strftime('%Y-%m-%d')
            # Ensure DATE_TRANSACTION is a Timestamp and format it properly
            #transaction_date = row.DATE_TRANSACTION.strftime('%Y-%m-%d')

            data_list.append({'transaction_date': transaction_date, 'transaction_detail': trx})
            

        df_result = pd.DataFrame(data_list)

        self.virement_transactions_processed = df_result.copy(deep=True)

    def clear_cache(self):
        self.virement_transactions = pd.DataFrame()
        self.virement_transactions_to_process = pd.DataFrame()
        self.virement_transactions_processed = pd.DataFrame()