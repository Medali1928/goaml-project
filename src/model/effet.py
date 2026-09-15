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


class Effet(DatabaseConnection):
    def __init__(self, db_config: dict, log_enabled: bool = True) -> None:

        super().__init__(db_config['server'], db_config['database'], db_config['username'], db_config['password'])

        self.db_config = db_config

        self.logger_manager = LoggerManager(log_enabled)
        self.query_executor = QueryExecutor(self.connection)

        self.effet_transactions = pd.DataFrame()
        self.effet_transactions_to_process = pd.DataFrame()
        self.effet_transactions_processed = pd.DataFrame()

    def _log(self, level, message, *args, **kwargs):
        """Log a message if logging is enabled using the logger manager."""
        self.logger_manager.log(level, message, *args, **kwargs)

    def get_effet_cc(self, account: str, year: str, max_attempts: int = 3) -> pd.DataFrame:

        self._log('info', "Starting effet_cc's transactions retrieval for account: %s, year: %s", account, year)
        self.connect()

        df = pd.DataFrame()

        try:
            query = f"""
           --recu effet atb-atb
            select

            'Effet' AS TYPE_OP,
            'Y' AS PART_1_IS_MY_CLIENT,
            'I' PART_1_ROLE,
            'ACCOUNT' AS PART_1_TYPE,

            'A' AS FUND_CODE_1,
            COD_DEV AS CURRENCY_CODE_1,
            'TN' AS COUNTRY_1,
            mnt_eff AS FORRIGNN_AMOUNT_1,

            'TN' AS TRANSACTION_LOCATION,
            CONVERT(VARCHAR, DAT_JOU, 23) + 'T00:00:00' AS DATE_TRANSACTION,
            ref_ope AS TRANS_CODE_DESC_ATB,
            ref_ope AS TRANSMODE_CODE_ATB,
            'B132' AS TRANSACTION_CODE_GOAML,
            mnt_eff AS AMOUNT_LOCAL,
            'C' AS TRANSACTION_STATUS_CODE,

            ref_ope TRANSACTION_REF,
            num_cpt ORACLE_ACCOUNT,
            CPT_EQA EQ_ACCOUNT,
            num_seq_ope TRANSACTION_SEQ,
            cod_age Agence,
            DAT_JOU TRANSACTION_DATE,
            mnt_eff FOREIGN_AMOUNT_1,


            --  PART_2_DETAILS


            '30' + '/' + TRIM(ref_ope) + '/' + FORMAT(DAT_JOU, 'dd MM yyyy') AS TRANSACTION_NUMBER,
            'Y' AS PART_2_IS_MY_CLIENT,
            'ACCOUNT' AS PART_2_TYPE,
            'B' AS PART_2_ROLE,
            EQUATION AS PART_2_ACCOUNT,
            '<IB_account>' +
                '<institution_name>' + ISNULL((select [LIB_LON_BQE]  FROM [MISDW].[TRG].[IBANK_RF_BANQUE] where [COD_BQE]=SUBSTRING(rib_tir,1,2)), 'N.A') + '</institution_name>' +
                '<swift>ATBKTNTTXXX</swift>'+
                '<institution_country>TN</institution_country>' +
                '<account>' + ISNULL(rib_tir, 'N.A') + '</account>' +
            '</IB_account>' AS PART_2_DETAILS,

            'A' AS FUND_CODE_2,
            COD_DEV AS CURRENCY_CODE_2,
            'TN' AS COUNTRY_2,
            mnt_eff AS FORRIGNN_AMOUNT_2,

            rib_tir account_benif,
            ORACLE ORACLE_ACCOUNT_benif,
            ben_ope Nom_benif,
            mnt_eff FOREIGN_AMOUNT_2,
            cod_bqe banque,

            (select [LIB_LON_BQE]  FROM [MISDW].[TRG].[IBANK_RF_BANQUE] where [COD_BQE]=SUBSTRING(rib_tir,1,2)) as institution_name,
            'TN' institution_country,

            'EFFET_RECU_MEME_BQE' AS NAR,
            'EFFET_RECU_MEME_BQE' AS SOURCE

            FROM [MISDW].[TRG].[IBANK_IB_REGLEMENT_EFFET] EFFET_RECU_MEME_BQE
            left join [MISDW].[MASTER_DATA].[T24_MAPPING_RIB] tir on tir.RIB=rib_tir
            where SUBSTRING(RIB_TIR,1,2)='01'
            and num_cpt ='{account}'
            and YEAR(DAT_JOU)='{year}'    
            """

            # Retry logic for query execution
            self._log('info', "Executing query with max_attempts: %d", max_attempts)
            df = self.query_executor.retry_query_execution(query, self.connection, max_attempts=max_attempts)

            if df.empty:
                self._log('warning', "No effet_cc's transactions data found for the account: %s, year: %s", account, year)
            else:
                if self.effet_transactions.empty:
                    self.effet_transactions = clean_dataframe(df)
                else:
                    self.effet_transactions = pd.concat([self.effet_transactions, clean_dataframe(df)], ignore_index=True)

                self._log('info', "Query executed successfully; effet_cc's transactions data retrieved for the account.")
        except Exception as e:
            self._log('error', "Error retrieving effet_cc's transactions data for the account: %s, year: %s, error: %s", account, year, e)
            raise
        finally:
            self._log('info', "Closing database connection.")
            self.disconnect()

        self._log('info', "Returning cleaned DataFrame.")

    def get_effet_ca(self, account: str, year: str, max_attempts: int = 3) -> pd.DataFrame:

        self._log('info', "Starting effet_ca's transactions retrieval for account: %s, year: %s", account, year)
        self.connect()

        df = pd.DataFrame()

        try:
            query = f"""
            --recu effet 
           select

            'Effet' AS TYPE_OP,
            'Y' AS PART_1_IS_MY_CLIENT,
            'I' PART_1_ROLE,
            'ACCOUNT' AS PART_1_TYPE,

            'A' AS FUND_CODE_1,
            COD_DEV AS CURRENCY_CODE_1,
            'TN' AS COUNTRY_1,
            mnt_eff AS FORRIGNN_AMOUNT_1,

            'TN' AS TRANSACTION_LOCATION,
            CONVERT(VARCHAR, DAT_JOU, 23) + 'T00:00:00' AS DATE_TRANSACTION,
            ref_ope AS TRANS_CODE_DESC_ATB,
            ref_ope AS TRANSMODE_CODE_ATB,
            'B132' AS TRANSACTION_CODE_GOAML,
            mnt_eff AS AMOUNT_LOCAL,
            'C' AS TRANSACTION_STATUS_CODE,

            ref_ope TRANSACTION_REF,
            num_cpt ORACLE_ACCOUNT,
            CPT_EQA EQ_ACCOUNT,
            num_seq_ope TRANSACTION_SEQ,
            cod_age Agence,
            DAT_JOU TRANSACTION_DATE,
            mnt_eff FOREIGN_AMOUNT_1,


            --  PART_2_DETAILS


            '30' + '/' + TRIM(ref_ope) + '/' + FORMAT(DAT_JOU, 'dd MM yyyy') AS TRANSACTION_NUMBER,
            'N' AS PART_2_IS_MY_CLIENT,
            'ACCOUNT' AS PART_2_TYPE,
            'B' AS PART_2_ROLE,
            EQUATION AS PART_2_ACCOUNT,
            '<IB_account>' +
                '<institution_name>' + ISNULL((select [LIB_LON_BQE]  FROM [MISDW].[TRG].[IBANK_RF_BANQUE] where [COD_BQE]=SUBSTRING(rib_tir,1,2)), 'N.A') + '</institution_name>' +
                '<swift>ATBKTNTTXXX</swift>'+
                '<institution_country>TN</institution_country>' +
                '<account>' + ISNULL(rib_tir, 'N.A') + '</account>' +
            '</IB_account>' AS PART_2_DETAILS,

            'A' AS FUND_CODE_2,
            COD_DEV AS CURRENCY_CODE_2,
            'TN' AS COUNTRY_2,
            mnt_eff AS FORRIGNN_AMOUNT_2,

            rib_tir account_benif,
            ORACLE ORACLE_ACCOUNT_benif,
            ben_ope Nom_benif,
            mnt_eff FOREIGN_AMOUNT_2,
            cod_bqe banque,

            (select [LIB_LON_BQE]  FROM [MISDW].[TRG].[IBANK_RF_BANQUE] where [COD_BQE]=SUBSTRING(rib_tir,1,2)) as institution_name,
            'TN' institution_country,

            'EFFET_RECU_MEME_BQE' AS NAR,
            'EFFET_RECU_MEME_BQE' AS SOURCE

            FROM [MISDW].[TRG].[IBANK_IB_REGLEMENT_EFFET] EFFET_RECU_MEME_BQE
            left join [MISDW].[MASTER_DATA].[T24_MAPPING_RIB] tir on tir.RIB=rib_tir
                where  SUBSTRING(RIB_TIR,1,2)!='01' 
                and num_cpt = '{account}'
                and YEAR(DAT_JOU)='{year}'
            """

            # Retry logic for query execution
            self._log('info', "Executing query with max_attempts: %d", max_attempts)
            df = self.query_executor.retry_query_execution(query, self.connection, max_attempts=max_attempts)

            if df.empty:
                self._log('warning', "No effet_ca's transactions data found for the account: %s, year: %s", account, year)
            else:
                if self.effet_transactions.empty:
                    self.effet_transactions = clean_dataframe(df)
                else:
                    self.effet_transactions = pd.concat([self.effet_transactions, clean_dataframe(df)], ignore_index=True)
                    

                self._log('info', "Query executed successfully; effet_ca's transactions data retrieved for the account.")
        except Exception as e:
            self._log('error', "Error retrieving effet_ca's transactions data for the account: %s, year: %s, error: %s", account, year, e)
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
        print(self.effet_transactions_to_process.info())

        print("écriture fichier transactions_to_process")
        try:
            self.effet_transactions_to_process.to_csv("C:\GOAML\procopr.csv", index=False) 
            print("DataFrame saved to procopr.csv successfully.")
        except OSError as e:
            print(f"File error: {e}")


        # Correctif : le nom de la colonne EQ_ACCOUNT peut varier ('EQ_ACCOUNT'
        # ou 'EQ_ACCOUNT_x' selon un eventuel suffixe de merge pandas) ; on
        # se protege contre une KeyError si le nom exact differe (donnee
        # manquante / schema inattendu) plutot que de planter tout le module.
        eq_account_col = 'EQ_ACCOUNT_x' if 'EQ_ACCOUNT_x' in self.effet_transactions_to_process.columns else 'EQ_ACCOUNT'
        if eq_account_col in self.effet_transactions_to_process.columns:
            valid_accounts = self.effet_transactions_to_process[eq_account_col]
            valid_accounts = pd.concat([valid_accounts, self.effet_transactions_to_process['PART_2_ACCOUNT']], ignore_index=True)
        else:
            print("Colonne EQ_ACCOUNT introuvable (donnee manquante), utilisation de PART_2_ACCOUNT uniquement")
            valid_accounts = self.effet_transactions_to_process['PART_2_ACCOUNT']
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
                print(f"Contrepartie Effet {p_acc} introuvable (donnee manquante), ignoree : {e}")
                continue



        for index, row in tqdm(self.effet_transactions_to_process.iterrows(), total=len(self.effet_transactions_to_process)):

            account = ''
            person_list = []
            conductor_xml_2 = ''

            comment = (
                f"{index} Op IBANK: {row['SOURCE']} - {row['TRANSACTION_DESC_ATB_ACC']} - {row['TRANSACTION_CODE_ATB']} - Narrative : {row['NAR']}"
            )

            trx = xml.create_transaction_xml(row, comment)
            if(row.PART_1_ROLE == 'I'): # partie = conductor + PPH # Emis
                obj_1 = ''
                print(f"{party} party ")
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

                        print(f"details account : {row.PART_2_ACCOUNT}") 
                        print(f"details dict : {initiator_dict[row.PART_2_ACCOUNT]}")          
                        account = initiator_dict[row.PART_2_ACCOUNT]

                        obj_2 = ''
                        p_2 = account['account_detail']
                        print (f"atbatb row 2 :{row}")
                        obj_2 = xml.create_xml_OBJ(row, 2)
                        obj_2 = obj_2.replace('PL3', p_2)
                        obj_2 = obj_2.replace('PL_CONDUCTOR', '')
                        obj_2 = obj_2.replace('PL1', 'to_my_client')
                        obj_2 = obj_2.replace('PL2', 'to')
                        obj_2 = obj_2.replace('IB_', 'to_')
                        

                        trx = trx.replace('PL_TO', obj_2)

                    except KeyError as e:
                        print(f"Contrepartie Effet {row.PART_2_ACCOUNT} introuvable (donnee manquante), bloc t_to generique utilise : {e}")
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
                    print (f"comp row 2 :{row}")
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
                print (f"B row 1 :{row}")
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
                    except KeyError as e:
                        print(f"Contrepartie Effet {row.PART_2_ACCOUNT} introuvable (donnee manquante), bloc t_from generique utilise : {e}")
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

        self.effet_transactions_processed = df_result.copy(deep=True)


    def clear_cache(self):
        self.effet_transactions = pd.DataFrame()
        self.effet_transactions_to_process = pd.DataFrame()
        self.effet_transactions_processed = pd.DataFrame()