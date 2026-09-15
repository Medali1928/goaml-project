import pandas as pd

from src.model.ibank_virement import Virement as IBANK_Virement


class Virement:

    def __init__(self, db_config: dict):

        self.account = {}
        self.accountant_trx = pd.DataFrame()
        self.year = ''

        self.ibank_virement = IBANK_Virement(db_config)

        # IBANK Virement
        self.accountant_transactions_with_trx_code_of_ibank_virement = pd.DataFrame()
        self.accountant_transactions_with_trx_code_and_ibank_virement = pd.DataFrame()
        
        # local variables
        self.stacked_df_virement = pd.DataFrame()
        self.accountant_vs_app_data_virement = pd.DataFrame()
        self.accountant_vs_app_summary_caisse = pd.DataFrame()

        self.processed_accountant_virement = pd.DataFrame()


    def get_transactions(self):

        self.clear_cache()

        if not self.accountant_trx.query("OP_TYPE == 'Virement'").empty:

            #print("===============================")
            #print(" accountant trx virement ")
            #print(self.accountant_trx.query("OP_TYPE == 'Virement'").shape)
            #print("===============================")

            # get ibank virements
            if not self.accountant_trx.query("(ACCOUNTANT_SOURCE == 'EQ') & (OP_TYPE == 'Virement') & (APP_SOURCE == 'IBANK') & (IS_MANUELLE != 'Y')").empty:
                #print("===============================")
                #print("IBANK Virement Trx")
                #print(self.accountant_trx.query("APP_SOURCE_CODE == 'TLVIR'").shape)
                #print(self.accountant_trx.query("APP_SOURCE == 'IBANK'").shape) #
                #print("===============================")
                
                unique_values = set(self.accountant_trx['TRANSACTION_CODE_ATB'])
                #print("===============================")
                #print("unique_values")
                #print(unique_values)
                #print("===============================")
                ##self.ibank_virement.get_virement_cc_ve(self.account['account_correspondences']['EQ_ACCOUNT'], self.year)
                #print("===============================")
                #print("ibank_virement")
                #print(self.ibank_virement.virement_transactions.shape)
                #print("===============================")
                for value in unique_values:
                    match value:
                        case '021' | '023' | '024' | '026': # Virement Emis
                            self.ibank_virement.get_virement_ca_ve(self.account['account_correspondences']['EQ_ACCOUNT'], self.year, max_attempts=3)
                            self.ibank_virement.get_virement_cc_ve(self.account['account_correspondences']['EQ_ACCOUNT'], self.year, max_attempts=3)
                        case '521' | '522' | '524': # Virement Recu
                            self.ibank_virement.get_virement_ca_vr(self.account['account_correspondences']['EQ_ACCOUNT'], self.year, max_attempts=3)
                            self.ibank_virement.get_virement_cc_vr(self.account['account_correspondences']['EQ_ACCOUNT'], self.year, max_attempts=3)

                print('============  self.ibank_virement.virement_transactions  ==============')
                if not self.ibank_virement.virement_transactions.empty:
                    print(self.ibank_virement.virement_transactions[['EQ_ACCOUNT', 'TRANSACTION_REF', 'TRANSACTION_DATE']])
                else:
                    print("Empty DataFrame (no IBANK virement detail found)")
                print('==========================')


    def process_transactions(self):

        print("process_transactions")


        print(self.accountant_trx.query("(ACCOUNTANT_SOURCE == 'EQ') & (OP_TYPE == 'Virement') & (APP_SOURCE == 'IBANK')")[['ACCOUNTANT_SOURCE', 'APP_SOURCE_CODE', 'EQ_ACCOUNT', 'OP_TYPE', 'TRANSACTION_CODE_GOAML']])

        if not self.accountant_trx.query("OP_TYPE == 'Virement'").empty:

            #print("===============================")
            #print(" accountant trx virement ")
            #print(self.accountant_trx.query("OP_TYPE == 'Virement'").shape)
            #distinct_values = self.accountant_trx.query("OP_TYPE == 'Virement'")['APP_SOURCE_CODE'].unique()
            #print(distinct_values)
            #print("===============================")

            # ibank virements
            if not self.accountant_trx.query("(ACCOUNTANT_SOURCE == 'EQ') & (OP_TYPE == 'Virement') & (APP_SOURCE == 'IBANK') & (IS_MANUELLE != 'Y')").empty:

                #print("case 1")
                #print("===============================")
                #print(" accountant trx virement IBANK")
                #print(self.accountant_trx.query("APP_SOURCE == 'IBANK'").shape)
                #print("===============================")

                self.accountant_transactions_with_trx_code_of_ibank_virement = self.accountant_trx.query("(ACCOUNTANT_SOURCE == 'EQ') & (OP_TYPE == 'Virement') & (APP_SOURCE == 'IBANK') & (IS_MANUELLE != 'Y')").copy(deep=True)

                # Remove duplicates from sub filtered 'accountant_transactions_with_trx_code_of_virement'
                self.accountant_transactions_with_trx_code_of_ibank_virement.drop_duplicates(subset=['EQ_ACCOUNT', 'TRANSACTION_REF', 'TRANSACTION_DATE'], inplace=True)

                # extrat data are available
                if not self.ibank_virement.virement_transactions.empty:

                  #print("case 2")
                    

                    # Add TRANSACTION_DATE_J column in virement_transactions
                    self.ibank_virement.virement_transactions['TRANSACTION_DATE'] = pd.to_datetime(
                        self.ibank_virement.virement_transactions['TRANSACTION_DATE']
                    )
                    self.ibank_virement.virement_transactions['TRANSACTION_DATE_J'] = '1' + self.ibank_virement.virement_transactions['TRANSACTION_DATE'].dt.strftime('%y%m%d')

                    # Delete TRANSACTION_DATE column
                    self.ibank_virement.virement_transactions.drop(columns=['TRANSACTION_DATE'], inplace=True)

                    # Sort 'virement_transactions' by EQ_ACCOUNT, TRANSACTION_REF, TRANSACTION_DATE_J
                    self.ibank_virement.virement_transactions = self.ibank_virement.virement_transactions.sort_values(
                        by=['EQ_ACCOUNT', 'TRANSACTION_REF', 'TRANSACTION_DATE_J']
                    )

                    # Remove duplicates in 'virement_transactions' (keep first occurrence)
                    self.ibank_virement.virement_transactions = self.ibank_virement.virement_transactions.drop_duplicates(
                        subset=['EQ_ACCOUNT', 'TRANSACTION_REF', 'TRANSACTION_DATE_J'], keep='first'
                    )

                    #print("===============================")
                    #print(" IBANK trx virement")
                    #print(self.ibank_virement.virement_transactions.shape)
                    #print("===============================")
                    
                    self.accountant_transactions_with_trx_code_and_ibank_virement = pd.merge(
                        left=self.accountant_transactions_with_trx_code_of_ibank_virement[['ACCOUNTANT_SOURCE', 'T24_ACCOUNT', 'EQ_ACCOUNT', 'ORACLE_ACCOUNT', 'OP_TYPE', 'APP_SOURCE', 'APP_SOURCE_CODE', 'TRANSACTION_REF', 'TRANSACTION_SEQ', 'TRANSACTION_DATE', 'TRANSACTION_CODE_ATB', 'TRANSACTION_DESC_ATB_ACC', 'Categorie_de_transaction', 'TRANSACTION_AMOUNT']],
                        right=self.ibank_virement.virement_transactions,
                        left_on=['EQ_ACCOUNT', 'TRANSACTION_REF', 'TRANSACTION_DATE'],
                        right_on=['EQ_ACCOUNT', 'TRANSACTION_REF', 'TRANSACTION_DATE_J'],
                        how='left',
                        indicator=True
                    ).copy(deep=True)


                    print("===============================")
                    print("===============================")
                    print("===============================")
                    print(self.accountant_transactions_with_trx_code_and_ibank_virement.columns)
                    print("===============================")
                    print("===============================")
                    print("===============================")
                    #print("case 3")
                    #print("===============================")
                    #print(" join ")
                    #print(self.accountant_transactions_with_trx_code_and_ibank_virement.shape)
                    #print("===============================")
                else:
                    #print("case 4")
                    self.accountant_transactions_with_trx_code_and_ibank_virement = self.accountant_transactions_with_trx_code_of_ibank_virement
                    self.accountant_transactions_with_trx_code_and_ibank_virement['_merge'] = 'left_only'
                # 2026-01-12
                if (self.accountant_transactions_with_trx_code_and_ibank_virement['_merge'] == 'both').all():

                    #print("cas 11")
                    
                    self.ibank_virement.virement_transactions_to_process = self.accountant_transactions_with_trx_code_and_ibank_virement.copy(deep=True)
                    self.ibank_virement.process_transaction(self.account['account_detail'], self.account['customer_id'], self.account['account_type'], self.account['account_rp'])
                    self.stacked_df_virement = pd.concat([self.stacked_df_virement, self.ibank_virement.virement_transactions_processed], ignore_index=True).copy(deep=True)
                
                    self.processed_accountant_virement = pd.concat([self.processed_accountant_virement, self.accountant_transactions_with_trx_code_and_ibank_virement[['ACCOUNTANT_SOURCE', 'T24_ACCOUNT', 'EQ_ACCOUNT', 'ORACLE_ACCOUNT', 'OP_TYPE', 'APP_SOURCE', 'APP_SOURCE_CODE', 'TRANSACTION_CODE_ATB', 'Categorie_de_transaction', 'TRANSACTION_REF', 'TRANSACTION_SEQ', 'TRANSACTION_DATE']]], ignore_index=True).copy(deep=True)

                elif (self.accountant_transactions_with_trx_code_and_ibank_virement['_merge'] == 'left_only').all():

                    #print("cas 22")
                    #print("===============================")
                    #print(" join ")
                    #print(self.accountant_transactions_with_trx_code_and_ibank_virement.shape)
                    #print("===============================")
                    #print("===============================")
                    #print(" IBANK trx virement")
                    #print(self.ibank_virement.virement_transactions.shape)
                    #print("===============================")

                    new_row = {
                        'Operation_Type': 'Virement',
                        'Accountant_TRX_Non_Matched': self.accountant_transactions_with_trx_code_and_ibank_virement,
                        'Accountant_TRX_Matched': pd.DataFrame(),
                        'App_TRX': self.ibank_virement.virement_transactions
                    }
                    print(new_row)
                    new_row_df = pd.DataFrame([new_row])
                    self.accountant_vs_app_data_virement = pd.concat([self.accountant_vs_app_data_virement, new_row_df], ignore_index=True)
                else:

                    #print("cas 33")
                    
                    self.ibank_virement.virement_transactions_to_process = self.accountant_transactions_with_trx_code_and_ibank_virement[self.accountant_transactions_with_trx_code_and_ibank_virement['_merge'] == 'both'].copy(deep=True)
                    self.ibank_virement.process_transaction(self.account['account_detail'], self.account['customer_id'], self.account['account_type'], self.account['account_rp'])
                    self.stacked_df_virement = pd.concat([self.stacked_df_virement, self.ibank_virement.virement_transactions_processed], ignore_index=True).copy(deep=True)
                    
                    self.processed_accountant_virement = pd.concat([self.processed_accountant_virement, self.accountant_transactions_with_trx_code_and_ibank_virement.query("_merge == 'both'")[['ACCOUNTANT_SOURCE', 'T24_ACCOUNT', 'EQ_ACCOUNT', 'ORACLE_ACCOUNT', 'OP_TYPE', 'APP_SOURCE', 'APP_SOURCE_CODE', 'TRANSACTION_CODE_ATB', 'Categorie_de_transaction', 'TRANSACTION_REF', 'TRANSACTION_SEQ', 'TRANSACTION_DATE']]], ignore_index=True).copy(deep=True)

                    new_row = {
                        'Operation_Type': 'Virement',
                        'Accountant_TRX_Non_Matched': self.accountant_transactions_with_trx_code_and_ibank_virement[self.accountant_transactions_with_trx_code_and_ibank_virement['_merge'] != 'both'],
                        'Accountant_TRX_Matched': self.accountant_transactions_with_trx_code_and_ibank_virement[self.accountant_transactions_with_trx_code_and_ibank_virement['_merge'] == 'both'],
                        'App_TRX': self.ibank_virement.virement_transactions
                    }
                    new_row_df = pd.DataFrame([new_row])
                    self.accountant_vs_app_data_virement = pd.concat([self.accountant_vs_app_data_virement, new_row_df], ignore_index=True).copy(deep=True)
                
                accountant_transactions_count = len(self.accountant_transactions_with_trx_code_of_ibank_virement)
                app_transactions_count = len(self.ibank_virement.virement_transactions)
                matching_rows_count = (self.accountant_transactions_with_trx_code_and_ibank_virement['_merge'] != 'both').sum()
                new_row = {
                    'Operation_Type': 'Virement',
                    'Accountant_Transactions_Count': accountant_transactions_count,
                    'App_Transactions_Count': app_transactions_count,
                    'Non_Matched_ops': matching_rows_count
                }
                # Convert the new row to a DataFrame
                new_row_df = pd.DataFrame([new_row])
                # Use pd.concat to add the new row
                self.accountant_vs_app_summary_virement = pd.concat([self.accountant_vs_app_summary_virement, new_row_df], ignore_index=True).copy(deep=True)


    def clear_cache(self):
        
        self.stacked_df_virement = pd.DataFrame()
        self.accountant_vs_app_data_virement = pd.DataFrame()
        self.accountant_vs_app_summary_virement = pd.DataFrame()

        # IBANK Virement
        self.accountant_transactions_with_trx_code_of_ibank_virement = pd.DataFrame()
        self.accountant_transactions_with_trx_code_and_ibank_virement = pd.DataFrame()

        self.processed_accountant_virement = pd.DataFrame()

        self.ibank_virement.clear_cache()


