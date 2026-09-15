import pandas as pd
import src.controller.default_handler as dh
from src.model.ibank_cheque import Cheque as IBANK_Cheque


class Cheque:

    def __init__(self, db_config: dict):

        self.account = {}
        self.accountant_trx = pd.DataFrame()
        self.year = ''

        self.ibank_cheque = IBANK_Cheque(db_config)

        # IBANK Cheque
        self.accountant_transactions_with_trx_code_of_ibank_cheque = pd.DataFrame()
        self.accountant_transactions_with_trx_code_and_ibank_cheque = pd.DataFrame()
        
        # local variables
        self.stacked_df_cheque = pd.DataFrame()
        self.accountant_vs_app_data_cheque = pd.DataFrame()
        self.accountant_vs_app_summary_cheque = pd.DataFrame()


        self.processed_accountant_cheque = pd.DataFrame()


    def get_transactions(self):

        self.clear_cache()

        if not self.accountant_trx.query("OP_TYPE == 'Cheque'").empty:

            # get ibank cheque
            self.ibank_cheque.get_cheque_cc_ce(self.account['account_correspondences']['EQ_ACCOUNT'], self.year)
            self.ibank_cheque.get_cheque_cc_cr(self.account['account_correspondences']['EQ_ACCOUNT'], self.year)
            self.ibank_cheque.get_cheque_ca_ce(self.account['account_correspondences']['EQ_ACCOUNT'], self.year)
            self.ibank_cheque.get_cheque_ca_cr(self.account['account_correspondences']['EQ_ACCOUNT'], self.year)


    def process_transactions(self):

        print("process_transactions_chq")

        if not self.accountant_trx.query("OP_TYPE == 'Cheque'").empty:

            # ibank cheque
            if not self.accountant_trx.query("(ACCOUNTANT_SOURCE == 'EQ') & (OP_TYPE == 'Cheque') & (APP_SOURCE == 'IBANK')").empty:

                self.accountant_transactions_with_trx_code_of_ibank_cheque = self.accountant_trx.query("(ACCOUNTANT_SOURCE == 'EQ') & (OP_TYPE == 'Cheque') & (APP_SOURCE == 'IBANK')").copy(deep=True)

                # Remove duplicates from sub filtered 'accountant_transactions_with_trx_code_of_ibank_cheque'
                self.accountant_transactions_with_trx_code_of_ibank_cheque.drop_duplicates(subset=['EQ_ACCOUNT', 'TRANSACTION_REF', 'TRANSACTION_DATE'], inplace=True)

                print(self.ibank_cheque.cheque_transactions.info)

                # extrat data are available
                if not self.ibank_cheque.cheque_transactions.empty:     

                    print("extra_chq_non_vide")               

                    # Add TRANSACTION_DATE_J column in virement_transactions
                    self.ibank_cheque.cheque_transactions['TRANSACTION_DATE_J'] = '1' + self.ibank_cheque.cheque_transactions['TRANSACTION_DATE'].dt.strftime('%y%m%d')

                    # Delete TRANSACTION_DATE column
                    self.ibank_cheque.cheque_transactions.drop(columns=['TRANSACTION_DATE'], inplace=True)

                    # Sort 'virement_transactions' by EQ_ACCOUNT, TRANSACTION_REF, TRANSACTION_DATE_J
                    self.ibank_cheque.cheque_transactions = self.ibank_cheque.cheque_transactions.sort_values(
                        by=['EQ_ACCOUNT', 'TRANSACTION_REF', 'TRANSACTION_DATE_J']
                    )

                    # Remove duplicates in 'virement_transactions' (keep first occurrence)
                    self.ibank_cheque.cheque_transactions = self.ibank_cheque.cheque_transactions.drop_duplicates(
                        subset=['EQ_ACCOUNT', 'TRANSACTION_REF', 'TRANSACTION_DATE_J'], keep='first'
                    )
                    
                    self.accountant_transactions_with_trx_code_and_ibank_cheque = pd.merge(
                        #left=self.accountant_transactions_with_trx_code_of_ibank_cheque[['T24_ACCOUNT', 'EQ_ACCOUNT', 'ORACLE_ACCOUNT', 'APP_SOURCE', 'APP_SOURCE_CODE', 'TRANSACTION_REF', 'TRANSACTION_DATE', 'TRANSACTION_CODE_ATB', 'TRANSACTION_DESC_ATB_ACC', 'Categorie_de_transaction', 'TRANSACTION_AMOUNT']],
                        left=self.accountant_transactions_with_trx_code_of_ibank_cheque[['ACCOUNTANT_SOURCE', 'T24_ACCOUNT', 'EQ_ACCOUNT', 'ORACLE_ACCOUNT', 'OP_TYPE', 'APP_SOURCE', 'APP_SOURCE_CODE', 'TRANSACTION_REF', 'TRANSACTION_SEQ', 'TRANSACTION_DATE', 'TRANSACTION_CODE_ATB', 'TRANSACTION_DESC_ATB_ACC', 'Categorie_de_transaction', 'TRANSACTION_AMOUNT']],
                        right=self.ibank_cheque.cheque_transactions,
                        left_on=['EQ_ACCOUNT', 'TRANSACTION_REF', 'TRANSACTION_DATE'],
                        right_on=['EQ_ACCOUNT', 'TRANSACTION_REF', 'TRANSACTION_DATE_J'],
                        how='left',
                        indicator=True
                    ).copy(deep=True)
                else:
                    print("extra_chq_vide")   
                    self.accountant_transactions_with_trx_code_and_ibank_cheque = self.accountant_transactions_with_trx_code_of_ibank_cheque
                    self.accountant_transactions_with_trx_code_and_ibank_cheque['_merge'] = 'left_only'


                if (self.accountant_transactions_with_trx_code_and_ibank_cheque['_merge'] == 'both').all():
                    self.ibank_cheque.cheque_transactions_to_process = self.accountant_transactions_with_trx_code_and_ibank_cheque.copy(deep=True)
                    self.ibank_cheque.process_transaction(self.account['account_detail'], self.account['customer_id'], self.account['account_type'], self.account['account_rp'])
                    self.stacked_df_cheque = pd.concat([self.stacked_df_cheque, self.ibank_cheque.cheque_transactions_processed], ignore_index=True).copy(deep=True)
                
                    self.processed_accountant_cheque = pd.concat([self.processed_accountant_cheque, self.accountant_transactions_with_trx_code_and_ibank_cheque[['ACCOUNTANT_SOURCE', 'T24_ACCOUNT', 'EQ_ACCOUNT', 'ORACLE_ACCOUNT', 'OP_TYPE', 'APP_SOURCE', 'APP_SOURCE_CODE', 'TRANSACTION_CODE_ATB', 'Categorie_de_transaction', 'TRANSACTION_REF', 'TRANSACTION_SEQ', 'TRANSACTION_DATE']]], ignore_index=True).copy(deep=True)
                
                elif (self.accountant_transactions_with_trx_code_and_ibank_cheque['_merge'] == 'left_only').all():
                    self.ibank_cheque.cheque_transactions_to_process = dh.handle_missing_extra(self.accountant_transactions_with_trx_code_and_ibank_cheque)
                    self.ibank_cheque.process_transaction(self.account['account_detail'], self.account['customer_id'], self.account['account_type'], self.account['account_rp'])
                    self.stacked_df_cheque = pd.concat([self.stacked_df_cheque, self.ibank_cheque.cheque_transactions_processed], ignore_index=True).copy(deep=True)

                    new_row = {
                        'Operation_Type': 'Cheque',
                        'Accountant_TRX_Non_Matched': self.accountant_transactions_with_trx_code_and_ibank_cheque,
                        'Accountant_TRX_Matched': pd.DataFrame(),
                        'App_TRX': self.ibank_cheque.cheque_transactions
                    }
                    print(new_row)
                    new_row_df = pd.DataFrame([new_row])
                    
                    self.accountant_vs_app_data_cheque = pd.concat([self.accountant_vs_app_data_cheque, new_row_df], ignore_index=True)
                else:
                    
                    self.ibank_cheque.cheque_transactions_to_process = self.accountant_transactions_with_trx_code_and_ibank_cheque[self.accountant_transactions_with_trx_code_and_ibank_cheque['_merge'] == 'both'].copy(deep=True)
                   
                    unmatched_rows = (
                        self.accountant_transactions_with_trx_code_and_ibank_cheque[
                            self.accountant_transactions_with_trx_code_and_ibank_cheque['_merge'] == 'left_only'
                        ]
                    )
                    
                    enriched_rows = dh.handle_missing_extra(unmatched_rows)
                    
                    self.ibank_cheque.cheque_transactions_to_process = pd.concat(
                        [
                            self.ibank_cheque.cheque_transactions_to_process,
                            enriched_rows
                        ],
                        ignore_index=True
                    )

                    self.ibank_cheque.process_transaction(self.account['account_detail'], self.account['customer_id'], self.account['account_type'], self.account['account_rp'])
                    self.stacked_df_cheque = pd.concat([self.stacked_df_cheque, self.ibank_cheque.cheque_transactions_processed], ignore_index=True).copy(deep=True)
                    
                    self.processed_accountant_cheque = pd.concat([self.processed_accountant_cheque, self.accountant_transactions_with_trx_code_and_ibank_cheque.query("_merge == 'both'")[['ACCOUNTANT_SOURCE', 'T24_ACCOUNT', 'EQ_ACCOUNT', 'ORACLE_ACCOUNT', 'OP_TYPE', 'APP_SOURCE', 'APP_SOURCE_CODE', 'TRANSACTION_CODE_ATB', 'Categorie_de_transaction', 'TRANSACTION_REF', 'TRANSACTION_SEQ', 'TRANSACTION_DATE']]], ignore_index=True).copy(deep=True)
                    
                    new_row = {
                        'Operation_Type': 'Cheque',
                        'Accountant_TRX_Non_Matched': self.accountant_transactions_with_trx_code_and_ibank_cheque[self.accountant_transactions_with_trx_code_and_ibank_cheque['_merge'] != 'both'],
                        'Accountant_TRX_Matched': self.accountant_transactions_with_trx_code_and_ibank_cheque[self.accountant_transactions_with_trx_code_and_ibank_cheque['_merge'] == 'both'],
                        'App_TRX': self.ibank_cheque.cheque_transactions
                    }
                    new_row_df = pd.DataFrame([new_row])
                    self.accountant_vs_app_data_cheque = pd.concat([self.accountant_vs_app_data_cheque, new_row_df], ignore_index=True).copy(deep=True)
                
                accountant_transactions_count = len(self.accountant_transactions_with_trx_code_of_ibank_cheque)
                app_transactions_count = len(self.ibank_cheque.cheque_transactions)
                matching_rows_count = (self.accountant_transactions_with_trx_code_and_ibank_cheque['_merge'] != 'both').sum()
                new_row = {
                    'Operation_Type': 'Cheque',
                    'Accountant_Transactions_Count': accountant_transactions_count,
                    'App_Transactions_Count': app_transactions_count,
                    'Non_Matched_ops': matching_rows_count
                }
                # Convert the new row to a DataFrame
                new_row_df = pd.DataFrame([new_row])
                # Use pd.concat to add the new row
                self.accountant_vs_app_summary_cheque = pd.concat([self.accountant_vs_app_summary_cheque, new_row_df], ignore_index=True).copy(deep=True)


    def clear_cache(self):
        
        self.stacked_df_cheque = pd.DataFrame()
        self.accountant_vs_app_data_cheque = pd.DataFrame()
        self.accountant_vs_app_summary_cheque = pd.DataFrame()

        # IBANK Cheque
        self.accountant_transactions_with_trx_code_of_ibank_cheque = pd.DataFrame()
        self.accountant_transactions_with_trx_code_and_ibank_cheque = pd.DataFrame()


        self.processed_accountant_cheque = pd.DataFrame()

        self.ibank_cheque.clear_cache()