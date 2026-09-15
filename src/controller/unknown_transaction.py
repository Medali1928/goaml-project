import pandas as pd
from tqdm import tqdm
from typing import Dict, List

import src.controller.default_handler as dh

from src.helpers.xmlStructure import XML
from src.helpers.utils import clean_dataframe
from src.db.connection import DatabaseConnection
from src.db.query_executor import QueryExecutor
from src.model.get_client import GetClient
from src.helpers.logger_manager import LoggerManager

class UnknownTransaction(DatabaseConnection):
 
    def __init__(self, db_config: dict, log_enabled: bool = True) -> None:

        super().__init__(db_config['server'], db_config['database'], db_config['username'], db_config['password'])

        self.db_config = db_config

        self.logger_manager = LoggerManager(log_enabled)
        self.query_executor = QueryExecutor(self.connection)

        self.account = {}
 
        self.accountant_trx = pd.DataFrame()
 
        self.stacked_df_unknown = pd.DataFrame()
 
        self.processed_accountant_unknown = pd.DataFrame()

        self.unknown_transactions_to_process = pd.DataFrame()

 
    def process_transactions(self,
        party: str
        ) -> pd.DataFrame:

        print("process unknown transactions")

        get_client = GetClient(self.db_config)

        xml = XML()
    
        df_result = pd.DataFrame(columns=['transaction_date', 'transaction_detail'])
        data_list = []
        initiator_dict = dict()
        conductor_xml_1 = ''

       # Bloc t_conductor minimal reutilisable, conforme au schema goAML
        # (nationality1, residence, addresses et occupation sont obligatoires
        # en plus des champs deja presents ; birthdate doit etre un xs:dateTime complet).
        CONDUCTOR_XML = """
        <t_conductor>
            <gender>M</gender>
            <first_name>UNKNOWN</first_name>
            <last_name>UNKNOWN</last_name>
            <birthdate>1900-01-01T00:00:00</birthdate>
            <birth_place>N.A</birth_place>
            <nationality1>TN</nationality1>
            <residence>TN</residence>
            <addresses>
            </addresses>
            <occupation>N.A</occupation>
        </t_conductor>
        """

        # Bloc IB_account minimal pour une contrepartie externe non identifiee
        UNKNOWN_ACCOUNT_XML = """
        <IB_account>
            <institution_name>UNKNOWN</institution_name>
            <swift>UNKNOWNXX</swift>
            <institution_country>TN</institution_country>
            <account>UNKNOWN</account>
        </IB_account>
        """
 
        if self.accountant_trx.empty:
            return
 
        self.unknown_transactions_to_process = dh.handle_missing_extra(
            self.accountant_trx
        )
 
        # self.processed_accountant_unknown = self.accountant_trx.copy(
        #     deep=True
        # )

        print("écriture fichier unknowntransactions")
        try:
            self.unknown_transactions_to_process.to_csv("C:\GOAML\file.csv", index=False) 
            print("DataFrame saved to unknowntransactions.csv successfully.")
        except OSError as e:
            print(f"File error: {e}")

        valid_accounts = self.unknown_transactions_to_process['EQ_ACCOUNT']
        valid_accounts = pd.concat([valid_accounts, self.unknown_transactions_to_process['PART_2_ACCOUNT']], ignore_index=True)
        valid_accounts = valid_accounts[
            valid_accounts.ne('') & valid_accounts.ne('NA')
        ].dropna().unique()  # Remove '', NaN, and placeholder 'NA'

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
                print(f"Contrepartie {p_acc} introuvable, ignorée (compte non traité comme mon client) : {e}")
                continue

        for index, row in tqdm(self.unknown_transactions_to_process.iterrows(), total=len(self.unknown_transactions_to_process)):

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
                obj_1 = obj_1.replace('PL_CONDUCTOR', CONDUCTOR_XML)
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
                        obj_2 = obj_2.replace('PL_CONDUCTOR', CONDUCTOR_XML)
                        obj_2 = obj_2.replace('PL1', 'to_my_client')
                        obj_2 = obj_2.replace('PL2', 'to')
                        obj_2 = obj_2.replace('IB_', 'to_')
                        
                        trx = trx.replace('PL_TO', obj_2)
                    except KeyError as e:
                        print(f"Contrepartie {row.PART_2_ACCOUNT} non résolue, bloc t_to générique utilisé : {e}")
                        obj_2 = xml.create_xml_OBJ(row, 2)
                        obj_2 = obj_2.replace('PL3', UNKNOWN_ACCOUNT_XML)
                        obj_2 = obj_2.replace('PL_CONDUCTOR', '')
                        obj_2 = obj_2.replace('PL1', 'to')
                        obj_2 = obj_2.replace('PL2', 'to')
                        obj_2 = obj_2.replace('IB_', 'to_')
                        trx = trx.replace('PL_TO', obj_2)
                else:
                    obj_2 = xml.create_xml_OBJ(row, 2)
                    obj_2 = obj_2.replace('PL3', UNKNOWN_ACCOUNT_XML)
                    obj_2 = obj_2.replace('PL_CONDUCTOR', '')
                    obj_2 = obj_2.replace('PL1', 'to')
                    obj_2 = obj_2.replace('PL2', 'to')
                    obj_2 = obj_2.replace('IB_', 'to_')
                    trx = trx.replace('PL_TO', obj_2)
            transaction_date = pd.to_datetime(row.DATE_TRANSACTION[:-9]).strftime('%Y-%m-%d')
            data_list.append({'transaction_date': transaction_date, 'transaction_detail': trx})
            

        df_result = pd.DataFrame(data_list)

        # Keep the same contract as the specialised handlers: stacked_df_* is what
        # TransactionRouter appends to the final XML stack, and processed_accountant_*
        # records the accountant rows that have been exported by this handler.
        self.stacked_df_unknown = df_result.copy(deep=True)

        expected_columns = [
            'ACCOUNTANT_SOURCE', 'T24_ACCOUNT', 'EQ_ACCOUNT', 'ORACLE_ACCOUNT',
            'OP_TYPE', 'APP_SOURCE', 'APP_SOURCE_CODE', 'TRANSACTION_CODE_ATB',
            'Categorie_de_transaction', 'TRANSACTION_REF', 'TRANSACTION_SEQ',
            'TRANSACTION_DATE'
        ]
        available_columns = [c for c in expected_columns if c in self.unknown_transactions_to_process.columns]
        self.processed_accountant_unknown = self.unknown_transactions_to_process[available_columns].copy(deep=True)
           
                    

 
    def clear_cache(self):
        
        self.accountant_trx = pd.DataFrame()
        self.stacked_df_unknown = pd.DataFrame()
        self.processed_accountant_unknown = pd.DataFrame()