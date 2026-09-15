import pandas as pd

from src.model.effet import Effet as effet


class Effet:

    def __init__(self, db_config: dict):

        self.account = {}
        self.accountant_trx = pd.DataFrame()
        self.year = ''

        self.effet = effet(db_config)

        # Effet
        self.accountant_transactions_with_trx_code_of_effet = pd.DataFrame()
        self.accountant_transactions_with_trx_code_and_effet = pd.DataFrame()
        
        # local variables
        self.stacked_df_effet = pd.DataFrame()
        self.accountant_vs_app_data_effet = pd.DataFrame()
        self.accountant_vs_app_summary_effet = pd.DataFrame()


        self.processed_accountant_effet = pd.DataFrame()


    def get_transactions(self):

        self.clear_cache()

        if not self.accountant_trx.query("OP_TYPE == 'Effet'").empty:

            # get effet
            self.effet.get_effet_ca(self.account['account_correspondences']['ORACLE_ACCOUNT'], self.year)
            self.effet.get_effet_cc(self.account['account_correspondences']['ORACLE_ACCOUNT'], self.year)


    def process_transactions(self):

        print("process_transactions effet")

        if not self.accountant_trx.query("OP_TYPE == 'Effet'").empty:
            print("accountant_trx not empty")
            # effet
            if not self.accountant_trx.query("(ACCOUNTANT_SOURCE == 'EQ') & (OP_TYPE == 'Effet') & (APP_SOURCE == 'IBANK')").empty:
                print("accountant_trx subquery")
                self.accountant_transactions_with_trx_code_of_effet = self.accountant_trx.query("(ACCOUNTANT_SOURCE == 'EQ') & (OP_TYPE == 'Effet') & (APP_SOURCE == 'IBANK')").copy(deep=True)

                # Remove duplicates from sub filtered 'accountant_transactions_with_trx_code_of_effet'
                self.accountant_transactions_with_trx_code_of_effet.drop_duplicates(subset=['ORACLE_ACCOUNT', 'TRANSACTION_REF', 'TRANSACTION_DATE'], inplace=True)

                # extrat data are available
                if not self.effet.effet_transactions.empty:                    

                    print("extra data not empty")

                    print(self.effet.effet_transactions['TRANSACTION_DATE'])

                    # Add TRANSACTION_DATE_J column in effet_transactions
                    self.effet.effet_transactions['TRANSACTION_DATE_J'] = '1' + pd.to_datetime(self.effet.effet_transactions['TRANSACTION_DATE']).dt.strftime('%y%m%d')

                    # Delete TRANSACTION_DATE column
                    self.effet.effet_transactions.drop(columns=['TRANSACTION_DATE'], inplace=True)

                    # Sort 'effet_transactions' by T24_ACCOUNT, TRANSACTION_REF, TRANSACTION_DATE_J
                    self.effet.effet_transactions = self.effet.effet_transactions.sort_values(
                        by=['ORACLE_ACCOUNT', 'TRANSACTION_REF', 'TRANSACTION_DATE_J']
                    )

                    # Remove duplicates in 'effet_transactions' (keep first occurrence)
                    self.effet.effet_transactions = self.effet.effet_transactions.drop_duplicates(
                        subset=['ORACLE_ACCOUNT', 'TRANSACTION_REF', 'TRANSACTION_DATE_J'], keep='first'
                    )
                    

                    print("écriture fichier extra")
                    try:
                        self.effet.effet_transactions.to_csv("C:\GOAML\extra.csv", index=False) 
                        print("DataFrame saved to extra.csv successfully.")
                    except OSError as e:
                        print(f"File error: {e}")




                    self.accountant_transactions_with_trx_code_and_effet = pd.merge(
                        #left=self.accountant_transactions_with_trx_code_of_effet[['T24_ACCOUNT', 'EQ_ACCOUNT', 'ORACLE_ACCOUNT', 'APP_SOURCE', 'APP_SOURCE_CODE', 'TRANSACTION_REF', 'TRANSACTION_DATE', 'TRANSACTION_CODE_ATB', 'TRANSACTION_DESC_ATB_ACC', 'Categorie_de_transaction', 'TRANSACTION_AMOUNT']],
                        left=self.accountant_transactions_with_trx_code_of_effet[['ACCOUNTANT_SOURCE', 'T24_ACCOUNT', 'EQ_ACCOUNT', 'ORACLE_ACCOUNT', 'OP_TYPE', 'APP_SOURCE', 'APP_SOURCE_CODE', 'TRANSACTION_REF', 'TRANSACTION_SEQ', 'TRANSACTION_DATE', 'TRANSACTION_CODE_ATB', 'TRANSACTION_DESC_ATB_ACC', 'Categorie_de_transaction', 'TRANSACTION_AMOUNT']],
                        right=self.effet.effet_transactions,
                        left_on=['ORACLE_ACCOUNT', 'TRANSACTION_REF', 'TRANSACTION_DATE'],
                        right_on=['ORACLE_ACCOUNT', 'TRANSACTION_REF', 'TRANSACTION_DATE_J'],
                        how='left',
                        indicator=True
                    ).copy(deep=True)
                else:
                    self.accountant_transactions_with_trx_code_and_effet = self.accountant_transactions_with_trx_code_of_effet
                    self.accountant_transactions_with_trx_code_and_effet['_merge'] = 'left_only'

                if (self.accountant_transactions_with_trx_code_and_effet['_merge'] == 'both').all():
                    self.effet.effet_transactions_to_process = self.accountant_transactions_with_trx_code_and_effet.copy(deep=True)
                    self.effet.process_transaction(self.account['account_detail'], self.account['customer_id'], self.account['account_type'], self.account['account_rp'])
                    self.stacked_df_effet = pd.concat([self.stacked_df_effet, self.effet.effet_transactions_processed], ignore_index=True).copy(deep=True)
                
                    print(self.processed_accountant_effet.info())
                    print(self.accountant_transactions_with_trx_code_and_effet.info())

                    self.processed_accountant_effet = pd.concat([self.processed_accountant_effet, self.accountant_transactions_with_trx_code_and_effet[['ACCOUNTANT_SOURCE', 'T24_ACCOUNT', 'EQ_ACCOUNT_x', 'ORACLE_ACCOUNT', 'OP_TYPE', 'APP_SOURCE', 'APP_SOURCE_CODE', 'TRANSACTION_CODE_ATB', 'Categorie_de_transaction', 'TRANSACTION_REF', 'TRANSACTION_SEQ_x', 'TRANSACTION_DATE']]], ignore_index=True).copy(deep=True)
                
                elif (self.accountant_transactions_with_trx_code_and_effet['_merge'] == 'left_only').all():

                    new_row = {
                        'Operation_Type': 'Effet',
                        'Accountant_TRX_Non_Matched': self.accountant_transactions_with_trx_code_and_effet,
                        'Accountant_TRX_Matched': pd.DataFrame(),
                        'App_TRX': self.effet.effet_transactions
                    }
                    print(new_row)
                    new_row_df = pd.DataFrame([new_row])
                    
                    self.accountant_vs_app_data_effet = pd.concat([self.accountant_vs_app_data_effet, new_row_df], ignore_index=True)
                else:

                    self.effet.effet_transactions_to_process = self.accountant_transactions_with_trx_code_and_effet[self.accountant_transactions_with_trx_code_and_effet['_merge'] == 'both'].copy(deep=True)
                    self.effet.process_transaction(self.account['account_detail'], self.account['customer_id'], self.account['account_type'], self.account['account_rp'])
                    self.stacked_df_effet = pd.concat([self.stacked_df_effet, self.effet.effet_transactions_processed], ignore_index=True).copy(deep=True)
                    
                    self.processed_accountant_effet = pd.concat([self.processed_accountant_effet, self.accountant_transactions_with_trx_code_and_effet.query("_merge == 'both'")[['ACCOUNTANT_SOURCE', 'T24_ACCOUNT', 'EQ_ACCOUNT_x', 'ORACLE_ACCOUNT', 'OP_TYPE', 'APP_SOURCE', 'APP_SOURCE_CODE', 'TRANSACTION_CODE_ATB', 'Categorie_de_transaction', 'TRANSACTION_REF', 'TRANSACTION_SEQ_x', 'TRANSACTION_DATE']]], ignore_index=True).copy(deep=True)
                    
                    new_row = {
                        'Operation_Type': 'Effet',
                        'Accountant_TRX_Non_Matched': self.accountant_transactions_with_trx_code_and_effet[self.accountant_transactions_with_trx_code_and_effet['_merge'] != 'both'],
                        'Accountant_TRX_Matched': self.accountant_transactions_with_trx_code_and_effet[self.accountant_transactions_with_trx_code_and_effet['_merge'] == 'both'],
                        'App_TRX': self.effet.effet_transactions
                    }
                    new_row_df = pd.DataFrame([new_row])
                    self.accountant_vs_app_data_effet = pd.concat([self.accountant_vs_app_data_effet, new_row_df], ignore_index=True).copy(deep=True)
                
                accountant_transactions_count = len(self.accountant_transactions_with_trx_code_of_effet)
                app_transactions_count = len(self.effet.effet_transactions)
                matching_rows_count = (self.accountant_transactions_with_trx_code_and_effet['_merge'] != 'both').sum()
                new_row = {
                    'Operation_Type': 'Effet',
                    'Accountant_Transactions_Count': accountant_transactions_count,
                    'App_Transactions_Count': app_transactions_count,
                    'Non_Matched_ops': matching_rows_count
                }
                # Convert the new row to a DataFrame
                new_row_df = pd.DataFrame([new_row])
                # Use pd.concat to add the new row
                self.accountant_vs_app_summary_effet = pd.concat([self.accountant_vs_app_summary_effet, new_row_df], ignore_index=True).copy(deep=True)


    def clear_cache(self):
        
        self.stacked_df_effet = pd.DataFrame()
        self.accountant_vs_app_data_effet = pd.DataFrame()
        self.accountant_vs_app_summary_effet = pd.DataFrame()

        # Effet
        self.accountant_transactions_with_trx_code_of_effet = pd.DataFrame()
        self.accountant_transactions_with_trx_code_and_effet = pd.DataFrame()


        self.processed_accountant_effet = pd.DataFrame()

        self.effet.clear_cache()