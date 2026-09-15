import pandas as pd

from src.model.clean_payment_transfert import Transfert as Clean_Payment_transfert
from src.model.tph_transfert import tph_Transfert as tph_transfert


class Transfert:

    def __init__(self, db_config: dict):

        self.account = {}
        self.accountant_trx = pd.DataFrame()
        self.year = ''

        self.clean_payment_transfert = Clean_Payment_transfert(db_config)
        self.tph_transfert = tph_transfert(db_config)

        # IBANK transfert
        self.accountant_transactions_with_trx_code_of_clean_payment_transfert = pd.DataFrame()
        self.accountant_transactions_with_trx_code_and_clean_payment_transfert = pd.DataFrame()

         # TPH transfert
        self.accountant_transactions_with_trx_code_of_tph_transfert = pd.DataFrame()
        self.accountant_transactions_with_trx_code_and_tph_transfert = pd.DataFrame()
        
        # local variables
        self.stacked_df_transfert = pd.DataFrame()
        self.accountant_vs_app_data_transfert = pd.DataFrame()
        self.accountant_vs_app_summary_transfert = pd.DataFrame()

        #self.processed_accountant_transfert = pd.DataFrame()



        self.processed_accountant_transfert = pd.DataFrame()


    def get_transactions(self):

        self.clear_cache()

        if not self.accountant_trx.query("OP_TYPE == 'Transfert'").empty:

            # get ibank transfert
            self.clean_payment_transfert.get_transfert(self.account['account_correspondences']['EQ_ACCOUNT'], self.year)

             # get tph transfert
            self.tph_transfert.get_transfert(self.account['account_correspondences']['T24_ACCOUNT'], self.year)


    def process_transactions(self):

        print("process_transactions")

        if not self.accountant_trx.query("OP_TYPE == 'Transfert'").empty:

            # ibank transfert
            if not self.accountant_trx.query("APP_SOURCE == 'Clean Payment'").empty:

                self.accountant_transactions_with_trx_code_of_clean_payment_transfert = self.accountant_trx.query("APP_SOURCE == 'Clean Payment'").copy(deep=True)

                # Remove duplicates from sub filtered 'accountant_transactions_with_trx_code_of_clean_payment_transfert'
                self.accountant_transactions_with_trx_code_of_clean_payment_transfert.drop_duplicates(subset=['EQ_ACCOUNT', 'TRANSACTION_REF', 'TRANSACTION_DATE'], inplace=True)

                # Normalize the format before merging
                self.accountant_transactions_with_trx_code_of_clean_payment_transfert.loc[:, 'TRANSACTION_DATE'] = self.accountant_transactions_with_trx_code_of_clean_payment_transfert['TRANSACTION_DATE'].astype(str).str.strip()

                # extrat data are available
                if not self.clean_payment_transfert.transfert_transactions.empty:                    

                    self.clean_payment_transfert.transfert_transactions.loc[:, 'TRANSACTION_DATE'] = self.clean_payment_transfert.transfert_transactions['TRANSACTION_DATE'].astype(str).str.strip()

                    # Sort 'virement_transactions' by EQ_ACCOUNT, TRANSACTION_REF, TRANSACTION_DATE_J
                    self.clean_payment_transfert.transfert_transactions = self.clean_payment_transfert.transfert_transactions.sort_values(
                        by=['EQ_ACCOUNT', 'TRANSACTION_REF', 'TRANSACTION_DATE']
                    )

                    # Remove duplicates in 'virement_transactions' (keep first occurrence)
                    self.clean_payment_transfert.transfert_transactions = self.clean_payment_transfert.transfert_transactions.drop_duplicates(
                        subset=['EQ_ACCOUNT', 'TRANSACTION_REF', 'TRANSACTION_DATE'], keep='first'
                    )
                    print("================= 2 =================")
                    print('self.accountant_transactions_with_trx_code_of_clean_payment_transfert')
                    print(self.accountant_transactions_with_trx_code_of_clean_payment_transfert.info())
                    print(self.accountant_transactions_with_trx_code_of_clean_payment_transfert[['EQ_ACCOUNT', 'TRANSACTION_REF', 'TRANSACTION_DATE']])
                    print('self.clean_payment_transfert.transfert_transactions')
                    print(self.clean_payment_transfert.transfert_transactions.info())
                    print(self.clean_payment_transfert.transfert_transactions[['EQ_ACCOUNT', 'TRANSACTION_REF', 'TRANSACTION_DATE']])
                    print("=====================================")
                    self.accountant_transactions_with_trx_code_and_clean_payment_transfert = pd.merge(
                        left=self.accountant_transactions_with_trx_code_of_clean_payment_transfert[['ACCOUNTANT_SOURCE', 'T24_ACCOUNT', 'EQ_ACCOUNT', 'ORACLE_ACCOUNT', 'OP_TYPE', 'APP_SOURCE', 'APP_SOURCE_CODE', 'TRANSACTION_REF', 'TRANSACTION_SEQ', 'TRANSACTION_DATE', 'TRANSACTION_CODE_ATB', 'TRANSACTION_DESC_ATB_ACC', 'Categorie_de_transaction', 'TRANSACTION_AMOUNT']],
                        right=self.clean_payment_transfert.transfert_transactions,
                        left_on=['EQ_ACCOUNT', 'TRANSACTION_REF', 'TRANSACTION_DATE'],
                        right_on=['EQ_ACCOUNT', 'TRANSACTION_REF', 'TRANSACTION_DATE'],
                        how='left',
                        indicator=True
                    ).copy(deep=True)
                else:
                    self.accountant_transactions_with_trx_code_and_clean_payment_transfert = self.accountant_transactions_with_trx_code_of_clean_payment_transfert
                    self.accountant_transactions_with_trx_code_and_clean_payment_transfert['_merge'] = 'left_only'

                if (self.accountant_transactions_with_trx_code_and_clean_payment_transfert['_merge'] == 'both').all():
                    self.clean_payment_transfert.transfert_transactions_to_process = self.accountant_transactions_with_trx_code_and_clean_payment_transfert.copy(deep=True)
                    self.clean_payment_transfert.process_transaction(self.account['account_detail'], self.account['customer_id'], self.account['account_type'], self.account['account_rp'])
                    self.stacked_df_transfert = pd.concat([self.stacked_df_transfert, self.clean_payment_transfert.transfert_transactions_processed], ignore_index=True).copy(deep=True)

                    self.processed_accountant_transfert = pd.concat([self.processed_accountant_transfert, self.accountant_transactions_with_trx_code_and_clean_payment_transfert[['ACCOUNTANT_SOURCE', 'T24_ACCOUNT', 'EQ_ACCOUNT', 'ORACLE_ACCOUNT', 'OP_TYPE', 'Categorie_de_transaction', 'APP_SOURCE_CODE', 'TRANSACTION_REF', 'TRANSACTION_SEQ', 'TRANSACTION_DATE', 'TRANSACTION_CODE_ATB']]], ignore_index=True).copy(deep=True)

                elif (self.accountant_transactions_with_trx_code_and_clean_payment_transfert['_merge'] == 'left_only').all():

                    new_row = {
                        'Operation_Type': 'Transfert',
                        'Accountant_TRX_Non_Matched': self.accountant_transactions_with_trx_code_and_clean_payment_transfert,
                        'Accountant_TRX_Matched': pd.DataFrame(),
                        'App_TRX': self.clean_payment_transfert.transfert_transactions
                    }
                    print(new_row)
                    new_row_df = pd.DataFrame([new_row])
                    #self.accountant_vs_app_data_virement = pd.concat([self.accountant_vs_app_data_virement, new_row_df], ignore_index=True)
                    self.accountant_vs_app_data_transfert = pd.concat([self.accountant_vs_app_data_transfert, new_row_df], ignore_index=True).copy(deep=True)
                else:

                    self.clean_payment_transfert.transfert_transactions_to_process = self.accountant_transactions_with_trx_code_and_clean_payment_transfert[self.accountant_transactions_with_trx_code_and_clean_payment_transfert['_merge'] == 'both'].copy(deep=True)
                    self.clean_payment_transfert.process_transaction(self.account['account_detail'], self.account['customer_id'], self.account['account_type'], self.account['account_rp'])
                    self.stacked_df_transfert = pd.concat([self.stacked_df_transfert, self.clean_payment_transfert.transfert_transactions_processed], ignore_index=True).copy(deep=True)
                    
                    self.processed_accountant_transfert = pd.concat([self.processed_accountant_transfert, self.accountant_transactions_with_trx_code_and_clean_payment_transfert.query("_merge == 'both'")[['ACCOUNTANT_SOURCE', 'T24_ACCOUNT', 'EQ_ACCOUNT', 'ORACLE_ACCOUNT', 'OP_TYPE', 'Categorie_de_transaction', 'APP_SOURCE_CODE', 'TRANSACTION_REF', 'TRANSACTION_SEQ', 'TRANSACTION_DATE', 'TRANSACTION_CODE_ATB']]], ignore_index=True).copy(deep=True)
                    
                    new_row = {
                        'Operation_Type': 'Transfert',
                        'Accountant_TRX_Non_Matched': self.accountant_transactions_with_trx_code_and_clean_payment_transfert[self.accountant_transactions_with_trx_code_and_clean_payment_transfert['_merge'] != 'both'],
                        'Accountant_TRX_Matched': self.accountant_transactions_with_trx_code_and_clean_payment_transfert[self.accountant_transactions_with_trx_code_and_clean_payment_transfert['_merge'] == 'both'],
                        'App_TRX': self.clean_payment_transfert.transfert_transactions
                    }
                    new_row_df = pd.DataFrame([new_row])
                    self.accountant_vs_app_data_transfert = pd.concat([self.accountant_vs_app_data_transfert, new_row_df], ignore_index=True).copy(deep=True)
                
                accountant_transactions_count = len(self.accountant_transactions_with_trx_code_of_clean_payment_transfert)
                app_transactions_count = len(self.clean_payment_transfert.transfert_transactions)
                matching_rows_count = (self.accountant_transactions_with_trx_code_and_clean_payment_transfert['_merge'] != 'both').sum()
                new_row = {
                    'Operation_Type': 'Transfert',
                    'Accountant_Transactions_Count': accountant_transactions_count,
                    'App_Transactions_Count': app_transactions_count,
                    'Non_Matched_ops': matching_rows_count
                }
                # Convert the new row to a DataFrame
                new_row_df = pd.DataFrame([new_row])
                # Use pd.concat to add the new row
                self.accountant_vs_app_summary_transfert = pd.concat([self.accountant_vs_app_summary_transfert, new_row_df], ignore_index=True).copy(deep=True)

            # tph transfert
            if not self.accountant_trx.query("APP_SOURCE == 'TPH'").empty:

                self.accountant_transactions_with_trx_code_of_tph_transfert = self.accountant_trx.query("APP_SOURCE == 'TPH'").copy(deep=True)

                # Remove duplicates from sub filtered 'accountant_transactions_with_trx_code_of_tph_transfert'
                self.accountant_transactions_with_trx_code_of_tph_transfert.drop_duplicates(subset=['T24_ACCOUNT', 'TRANSACTION_REF', 'TRANSACTION_DATE'], inplace=True)

                # Normalize the format before merging
                self.accountant_transactions_with_trx_code_of_tph_transfert.loc[:, 'TRANSACTION_DATE'] = self.accountant_transactions_with_trx_code_of_tph_transfert['TRANSACTION_DATE'].astype(str).str.strip()

                # extrat data are available
                if not self.tph_transfert.transfert_transactions.empty:                    

                    self.tph_transfert.transfert_transactions.loc[:, 'TRANSACTION_DATE'] = self.tph_transfert.transfert_transactions['TRANSACTION_DATE'].astype(str).str.strip()

                    # Sort 'virement_transactions' by EQ_ACCOUNT, TRANSACTION_REF, TRANSACTION_DATE_J
                    self.tph_transfert.transfert_transactions = self.tph_transfert.transfert_transactions.sort_values(
                        by=['T24_ACCOUNT', 'TRANSACTION_REF', 'TRANSACTION_DATE']
                    )

                    # Remove duplicates in 'virement_transactions' (keep first occurrence)
                    self.tph_transfert.transfert_transactions = self.tph_transfert.transfert_transactions.drop_duplicates(
                        subset=['T24_ACCOUNT', 'TRANSACTION_REF', 'TRANSACTION_DATE'], keep='first'
                    )

                    print("écriture fichier extra")
                    try:
                        self.tph_transfert.transfert_transactions.to_csv("C:\GOAML\extra.csv", index=False) 
                        print("DataFrame saved to extra.csv successfully.")
                    except OSError as e:
                        print(f"File error: {e}")

                    print("================= 2 =================")
                    print('self.accountant_transactions_with_trx_code_of_tph_transfert')
                    print(self.accountant_transactions_with_trx_code_of_tph_transfert.info())
                    print(self.accountant_transactions_with_trx_code_of_tph_transfert[['T24_ACCOUNT', 'TRANSACTION_REF', 'TRANSACTION_DATE']])
                    print('self.tph_transfert.transfert_transactions')
                    print(self.tph_transfert.transfert_transactions.info())
                    print(self.tph_transfert.transfert_transactions[['T24_ACCOUNT', 'TRANSACTION_REF', 'TRANSACTION_DATE']])
                    print("=====================================")
                    self.accountant_transactions_with_trx_code_and_tph_transfert = pd.merge(
                        left=self.accountant_transactions_with_trx_code_of_tph_transfert[['ACCOUNTANT_SOURCE', 'T24_ACCOUNT', 'EQ_ACCOUNT', 'ORACLE_ACCOUNT', 'OP_TYPE', 'APP_SOURCE', 'APP_SOURCE_CODE', 'TRANSACTION_REF', 'TRANSACTION_SEQ', 'TRANSACTION_DATE', 'TRANSACTION_CODE_ATB', 'TRANSACTION_DESC_ATB_ACC', 'Categorie_de_transaction', 'TRANSACTION_AMOUNT']],
                        right=self.tph_transfert.transfert_transactions,
                        left_on=['T24_ACCOUNT', 'TRANSACTION_REF', 'TRANSACTION_DATE'],                        
                        right_on=['T24_ACCOUNT', 'TRANSACTION_REF', 'TRANSACTION_DATE'],
                        how='left',
                        indicator=True
                    ).copy(deep=True)
                else:
                    self.accountant_transactions_with_trx_code_and_tph_transfert = self.accountant_transactions_with_trx_code_of_tph_transfert
                    self.accountant_transactions_with_trx_code_and_tph_transfert['_merge'] = 'left_only'

                if (self.accountant_transactions_with_trx_code_and_tph_transfert['_merge'] == 'both').all():
                    self.tph_transfert.transfert_transactions_to_process = self.accountant_transactions_with_trx_code_and_tph_transfert.copy(deep=True)
                    self.tph_transfert.process_transaction(self.account['account_detail'], self.account['customer_id'], self.account['account_type'], self.account['account_rp'])
                    self.stacked_df_transfert = pd.concat([self.stacked_df_transfert, self.tph_transfert.transfert_transactions_processed], ignore_index=True).copy(deep=True)

                    self.processed_accountant_transfert = pd.concat([self.processed_accountant_transfert, self.accountant_transactions_with_trx_code_and_tph_transfert[['ACCOUNTANT_SOURCE', 'T24_ACCOUNT', 'EQ_ACCOUNT', 'ORACLE_ACCOUNT', 'OP_TYPE', 'Categorie_de_transaction', 'APP_SOURCE_CODE', 'TRANSACTION_REF', 'TRANSACTION_SEQ', 'TRANSACTION_DATE', 'TRANSACTION_CODE_ATB']]], ignore_index=True).copy(deep=True)

                elif (self.accountant_transactions_with_trx_code_and_tph_transfert['_merge'] == 'left_only').all():

                    new_row = {
                        'Operation_Type': 'Transfert',
                        'Accountant_TRX_Non_Matched': self.accountant_transactions_with_trx_code_and_tph_transfert,
                        'Accountant_TRX_Matched': pd.DataFrame(),
                        'App_TRX': self.tph_transfert.transfert_transactions
                    }
                    print(new_row)
                    new_row_df = pd.DataFrame([new_row])
                    #self.accountant_vs_app_data_virement = pd.concat([self.accountant_vs_app_data_virement, new_row_df], ignore_index=True)
                    self.accountant_vs_app_data_transfert = pd.concat([self.accountant_vs_app_data_transfert, new_row_df], ignore_index=True).copy(deep=True)
                else:

                    self.tph_transfert.transfert_transactions_to_process = self.accountant_transactions_with_trx_code_and_tph_transfert[self.accountant_transactions_with_trx_code_and_tph_transfert['_merge'] == 'both'].copy(deep=True)
                    self.tph_transfert.process_transaction(self.account['account_detail'], self.account['customer_id'], self.account['account_type'], self.account['account_rp'])
                    self.stacked_df_transfert = pd.concat([self.stacked_df_transfert, self.tph_transfert.transfert_transactions_processed], ignore_index=True).copy(deep=True)
                    
                    self.processed_accountant_transfert = pd.concat([self.processed_accountant_transfert, self.accountant_transactions_with_trx_code_and_tph_transfert.query("_merge == 'both'")[['ACCOUNTANT_SOURCE', 'T24_ACCOUNT', 'EQ_ACCOUNT', 'ORACLE_ACCOUNT', 'OP_TYPE', 'Categorie_de_transaction', 'APP_SOURCE_CODE', 'TRANSACTION_REF', 'TRANSACTION_SEQ', 'TRANSACTION_DATE', 'TRANSACTION_CODE_ATB']]], ignore_index=True).copy(deep=True)
                    
                    new_row = {
                        'Operation_Type': 'Transfert',
                        'Accountant_TRX_Non_Matched': self.accountant_transactions_with_trx_code_and_tph_transfert[self.accountant_transactions_with_trx_code_and_tph_transfert['_merge'] != 'both'],
                        'Accountant_TRX_Matched': self.accountant_transactions_with_trx_code_and_tph_transfert[self.accountant_transactions_with_trx_code_and_tph_transfert['_merge'] == 'both'],
                        'App_TRX': self.tph_transfert.transfert_transactions
                    }
                    new_row_df = pd.DataFrame([new_row])
                    self.accountant_vs_app_data_transfert = pd.concat([self.accountant_vs_app_data_transfert, new_row_df], ignore_index=True).copy(deep=True)
                
                accountant_transactions_count = len(self.accountant_transactions_with_trx_code_of_tph_transfert)
                app_transactions_count = len(self.tph_transfert.transfert_transactions)
                matching_rows_count = (self.accountant_transactions_with_trx_code_and_tph_transfert['_merge'] != 'both').sum()
                new_row = {
                    'Operation_Type': 'Transfert',
                    'Accountant_Transactions_Count': accountant_transactions_count,
                    'App_Transactions_Count': app_transactions_count,
                    'Non_Matched_ops': matching_rows_count
                }
                # Convert the new row to a DataFrame
                new_row_df = pd.DataFrame([new_row])
                # Use pd.concat to add the new row
                self.accountant_vs_app_summary_transfert = pd.concat([self.accountant_vs_app_summary_transfert, new_row_df], ignore_index=True).copy(deep=True)


    def clear_cache(self):
        
        self.stacked_df_transfert = pd.DataFrame()
        self.accountant_vs_app_data_transfert = pd.DataFrame()
        self.accountant_vs_app_summary_transfert = pd.DataFrame()

        # IBANK transfert
        self.accountant_transactions_with_trx_code_of_clean_payment_transfert = pd.DataFrame()
        self.accountant_transactions_with_trx_code_and_clean_payment_transfert = pd.DataFrame()

        # TPH transfert
        self.accountant_transactions_with_trx_code_of_tph_transfert = pd.DataFrame()
        self.accountant_transactions_with_trx_code_and_tph_transfert = pd.DataFrame()

        self.processed_accountant_transfert = pd.DataFrame()

        self.clean_payment_transfert.clear_cache()
        self.tph_transfert.clear_cache()