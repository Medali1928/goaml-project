import pandas as pd

from src.model.cashier import Cashier
from src.model.teller import Teller

class Caisse:

    def __init__(self, db_config: dict):

        self.account = {}
        self.accountant_trx = pd.DataFrame()
        self.year = ''

        self.cashier = Cashier(db_config)
        self.teller = Teller(db_config)

        # Cashier
        self.accountant_transactions_with_trx_code_of_cashier = pd.DataFrame()
        self.accountant_transactions_with_trx_code_and_cashier = pd.DataFrame()

        # Teller
        self.accountant_transactions_with_trx_code_of_teller = pd.DataFrame()
        self.accountant_transactions_with_trx_code_and_teller = pd.DataFrame()
        
        # local variables
        self.stacked_df_caisse = pd.DataFrame()
        self.accountant_vs_app_data_caisse = pd.DataFrame()
        self.accountant_vs_app_summary_caisse = pd.DataFrame()

        self.processed_accountant_caisse = pd.DataFrame()
        

    def get_transactions(self):

        self.clear_cache()

        if not self.accountant_trx.query("OP_TYPE == 'Caisse'").empty:
        #if not self.accountant_trx.query("APP_SOURCE_CODE == '@AAA' | APP_SOURCE_CODE == 'T24TL'").empty:

            # get Cashier transactions
            if not self.accountant_trx.query("(ACCOUNTANT_SOURCE == 'EQ') & (OP_TYPE == 'Caisse') & (APP_SOURCE == 'Cashier') & (APP_SOURCE_CODE == '@AAA') & (IS_MANUELLE != 'Y')").empty and int(self.year) < 2025:
                
                print('==================  accountant - Cashier  ==================')
                print(self.accountant_trx.query("(ACCOUNTANT_SOURCE == 'EQ') & (OP_TYPE == 'Caisse') & (APP_SOURCE == 'Cashier') & (APP_SOURCE_CODE == '@AAA')").info())
                print('=========================================================')

                self.cashier.get_cashier_transactions(self.account['account_correspondences']['EQ_ACCOUNT'], self.year)

                print('================= caisse - cashier ==================')
                print(self.cashier.cashier_transactions.info())
                print('=====================================================')

            # get Teller Transactions
            if not self.accountant_trx.query("(ACCOUNTANT_SOURCE == 'T24') & (OP_TYPE == 'Caisse') & (APP_SOURCE == 'Teller') & (APP_SOURCE_CODE == 'TT') & (IS_MANUELLE != 'Y')").empty and int(self.year) >= 2023:
                
                print('==================  accountant - Teller  ==================')
                print(self.accountant_trx.query("(ACCOUNTANT_SOURCE == 'T24') & (OP_TYPE == 'Caisse') & (APP_SOURCE == 'Teller') & (APP_SOURCE_CODE == 'TT')").info())
                print('=========================================================')

                self.teller.get_teller_transactions(self.account['account_correspondences']['T24_ACCOUNT'], self.year)

                print('================= caisse - Teller ==================')
                print(self.teller.teller_transactions.info())
                print('=====================================================')


    def process_transactions(self):

        if not self.accountant_trx.query("OP_TYPE == 'Caisse'").empty:
            # get rectification
            #if not self.accountant_trx.query("APP_SOURCE_CODE == '@AAA' | APP_SOURCE_CODE == 'T24TL'").empty:
            # Cashier
            if not self.accountant_trx.query("(ACCOUNTANT_SOURCE == 'EQ') & (OP_TYPE == 'Caisse') & (APP_SOURCE == 'Cashier') & (APP_SOURCE_CODE == '@AAA') & (IS_MANUELLE != 'Y')").empty:
            #if not self.accountant_trx.query("APP_SOURCE_CODE == '@AAA'").empty:

                self.accountant_transactions_with_trx_code_of_cashier = self.accountant_trx.query("(ACCOUNTANT_SOURCE == 'EQ') & (OP_TYPE == 'Caisse') & (APP_SOURCE == 'Cashier') & (APP_SOURCE_CODE == '@AAA') & (IS_MANUELLE != 'Y')").copy(deep=True)
                #self.accountant_transactions_with_trx_code_of_cashier = self.accountant_trx.query("APP_SOURCE_CODE == '@AAA'").copy(deep=True)

                # Remove duplicates from sub filtered 'accountant_transactions_with_trx_code_of_cashier'
                self.accountant_transactions_with_trx_code_of_cashier.drop_duplicates(subset=['EQ_ACCOUNT', 'TRANSACTION_REF', 'TRANSACTION_DATE'], inplace=True)

                #self.accountant_transactions_with_trx_code_of_cashier['AMOUNT_LOCAL'] = self.accountant_transactions_with_trx_code_of_cashier['TRANSACTION_AMOUNT_LCY']
                def compute_amount_local(row):

                    if row['TRANSACTION_CURRENCY'] != 'TND':
                        return str(float(row['TRANSACTION_AMOUNT_LCY']))
                    else:
                        return str(float(row['TRANSACTION_AMOUNT']))

                self.accountant_transactions_with_trx_code_of_cashier['AMOUNT_LOCAL'] = (
                    self.accountant_transactions_with_trx_code_of_cashier.apply(
                        compute_amount_local, axis=1
                    )
                )
            
                # extrat data are available
                if not self.cashier.cashier_transactions.empty:
                    # Sort 'cashier_transactions' by EQ_ACCOUNT, TRANSACTION_DATE, TRANSACTION_REF
                    self.cashier.cashier_transactions.sort_values(
                        by=['EQ_ACCOUNT', 'TRANSACTION_DATE', 'TRANSACTION_REF'],
                        inplace=True
                    )
                    # Remove duplicates in 'cashier_transactions' (keep first occurrence)
                    self.cashier.cashier_transactions.drop_duplicates(
                        subset=['EQ_ACCOUNT', 'TRANSACTION_DATE', 'TRANSACTION_REF'],
                        keep='first',
                        inplace=True
                    )
                    self.accountant_transactions_with_trx_code_and_cashier = pd.merge(
                        left=self.accountant_transactions_with_trx_code_of_cashier,
                        right=self.cashier.cashier_transactions,
                        left_on=['EQ_ACCOUNT', 'TRANSACTION_DATE', 'TRANSACTION_REF'],
                        right_on=['EQ_ACCOUNT', 'TRANSACTION_DATE', 'TRANSACTION_REF'],
                        how='left',
                        indicator=True,
                        validate='one_to_one'
                    ).copy(deep=True)
                else:
                    self.accountant_transactions_with_trx_code_and_cashier = self.accountant_transactions_with_trx_code_of_cashier
                    self.accountant_transactions_with_trx_code_and_cashier['_merge'] = 'left_only'


                if (self.accountant_transactions_with_trx_code_and_cashier['_merge'] == 'both').all():
                    print('======================== caisse - cashier - case 1 - all both =============================')
                    self.cashier.cashier_transactions_to_process = self.accountant_transactions_with_trx_code_and_cashier.copy(deep=True)
                    self.cashier.process_transactions(self.account['account_detail'], self.account['customer_id'], self.account['account_type'], self.account['account_rp'])
                    self.stacked_df_caisse = pd.concat([self.stacked_df_caisse, self.cashier.cashier_transactions_processed], ignore_index=True).copy(deep=True)
                
                    self.processed_accountant_caisse = pd.concat([self.processed_accountant_caisse, self.accountant_transactions_with_trx_code_and_cashier[['ACCOUNTANT_SOURCE', 'T24_ACCOUNT', 'EQ_ACCOUNT', 'ORACLE_ACCOUNT', 'OP_TYPE', 'APP_SOURCE', 'APP_SOURCE_CODE', 'TRANSACTION_CODE_ATB', 'Categorie_de_transaction', 'TRANSACTION_REF', 'TRANSACTION_SEQ', 'TRANSACTION_DATE']]], ignore_index=True).copy(deep=True)
                elif (self.accountant_transactions_with_trx_code_and_cashier['_merge'] == 'left_only').all():
                    print('======================== caisse - cashier - case 2 - all left only =============================')
                    new_row = {
                        'Operation_Type': 'Cashier',
                        'Accountant_TRX_Non_Matched': self.accountant_transactions_with_trx_code_and_cashier,
                        'Accountant_TRX_Matched': pd.DataFrame(),
                        'App_TRX': self.cashier.cashier_transactions
                    }
                    new_row_df = pd.DataFrame([new_row])
                    self.accountant_vs_app_data_caisse = pd.concat([self.accountant_vs_app_data_caisse, new_row_df], ignore_index=True)
                else:
                    print('======================== caisse - cashier - case 3 - both & left =============================')
                    self.cashier.cashier_transactions_to_process = self.accountant_transactions_with_trx_code_and_cashier[self.accountant_transactions_with_trx_code_and_cashier['_merge'] == 'both'].copy(deep=True)
                    self.cashier.process_transactions(self.account['account_detail'], self.account['customer_id'], self.account['account_type'], self.account['account_rp'])
                    self.stacked_df_caisse = pd.concat([self.stacked_df_caisse, self.cashier.cashier_transactions_processed], ignore_index=True).copy(deep=True)
                    
                    self.processed_accountant_caisse = pd.concat([self.processed_accountant_caisse, self.accountant_transactions_with_trx_code_and_cashier.query("_merge == 'both'")[['ACCOUNTANT_SOURCE', 'T24_ACCOUNT', 'EQ_ACCOUNT', 'ORACLE_ACCOUNT', 'OP_TYPE', 'APP_SOURCE', 'APP_SOURCE_CODE', 'TRANSACTION_CODE_ATB', 'Categorie_de_transaction', 'TRANSACTION_REF', 'TRANSACTION_SEQ', 'TRANSACTION_DATE']]], ignore_index=True).copy(deep=True)
                    new_row = {
                        'Operation_Type': 'Cashier',
                        'Accountant_TRX_Non_Matched': self.accountant_transactions_with_trx_code_and_cashier[self.accountant_transactions_with_trx_code_and_cashier['_merge'] != 'both'],
                        'Accountant_TRX_Matched': self.accountant_transactions_with_trx_code_and_cashier[self.accountant_transactions_with_trx_code_and_cashier['_merge'] == 'both'],
                        'App_TRX': self.cashier.cashier_transactions
                    }
                    new_row_df = pd.DataFrame([new_row])
                    self.accountant_vs_app_data_caisse = pd.concat([self.accountant_vs_app_data_caisse, new_row_df], ignore_index=True).copy(deep=True)
                
                accountant_transactions_count = len(self.accountant_transactions_with_trx_code_of_cashier)
                app_transactions_count = len(self.cashier.cashier_transactions)
                matching_rows_count = (self.accountant_transactions_with_trx_code_and_cashier['_merge'] != 'both').sum()
                new_row = {
                    'Operation_Type': 'Cashier',
                    'Accountant_Transactions_Count': accountant_transactions_count,
                    'App_Transactions_Count': app_transactions_count,
                    'Non_Matched_ops': matching_rows_count
                }
                # Convert the new row to a DataFrame
                new_row_df = pd.DataFrame([new_row])
                # Use pd.concat to add the new row
                self.accountant_vs_app_summary_caisse = pd.concat([self.accountant_vs_app_summary_caisse, new_row_df], ignore_index=True).copy(deep=True)

            # Teller
            #if not self.accountant_trx.query("APP_SOURCE == 'Teller'").empty:
            if not self.accountant_trx.query("(ACCOUNTANT_SOURCE == 'T24') & (OP_TYPE == 'Caisse') & (APP_SOURCE == 'Teller') & (APP_SOURCE_CODE == 'TT') & (IS_MANUELLE != 'Y')").empty:
            #if not self.accountant_trx.query("APP_SOURCE_CODE == 'T24TL'").empty:

                #self.accountant_transactions_with_trx_code_of_teller = self.accountant_trx.query("APP_SOURCE == 'Teller'").copy(deep=True)
                self.accountant_transactions_with_trx_code_of_teller = self.accountant_trx.query("(ACCOUNTANT_SOURCE == 'T24') & (OP_TYPE == 'Caisse') & (APP_SOURCE == 'Teller') & (APP_SOURCE_CODE == 'TT') & (IS_MANUELLE != 'Y')").copy(deep=True)
                #self.accountant_transactions_with_trx_code_of_teller = self.accountant_trx.query("APP_SOURCE_CODE == 'T24TL'").copy(deep=True)

                # Remove duplicates from sub filtered 'accountant_transactions_with_trx_code_of_teller'
                self.accountant_transactions_with_trx_code_of_teller.drop_duplicates(subset=['T24_ACCOUNT', 'TRANSACTION_REF', 'TRANSACTION_DATE'], keep='first', inplace=True)

                #self.accountant_transactions_with_trx_code_of_teller.loc[:, 'TRANSACTION_DATE'] = self.accountant_transactions_with_trx_code_of_teller['TRANSACTION_DATE'].astype(str).str[1:].astype('object')
                #self.accountant_transactions_with_trx_code_of_teller.loc[:, 'PARTY_ROLE'] = self.accountant_transactions_with_trx_code_of_teller['TRANSACTION_AMOUNT_LCY'].apply(lambda x: 'I' if x < 0 else 'B')

                # Convert to numeric first, then apply the condition
                self.accountant_transactions_with_trx_code_of_teller.loc[:, 'PARTY_ROLE'] = (
                    pd.to_numeric(self.accountant_transactions_with_trx_code_of_teller['TRANSACTION_AMOUNT_LCY'])
                    .apply(lambda x: 'I' if x < 0 else 'B') # org : <
                )
                # extrat data are available
                if not self.teller.teller_transactions.empty:
                    # Sort 'teller_transactions' by EQ_ACCOUNT, TRANSACTION_DATE, TRANSACTION_REF
                    self.teller.teller_transactions.sort_values(
                        by=['T24_ACCOUNT', 'TRANSACTION_DATE', 'TRANSACTION_REF'],#'SOURCE'
                        inplace=True
                    )

                    # Remove duplicates in 'teller_transactions' (keep first occurrence)
                    self.teller.teller_transactions.drop_duplicates(
                        subset=['T24_ACCOUNT', 'TRANSACTION_DATE', 'TRANSACTION_REF'],#'SOURCE'
                        keep='first',
                        inplace=True
                    )
                    self.teller.teller_transactions['TRANSACTION_DATE'] = '20' + self.teller.teller_transactions['TRANSACTION_DATE'].astype(str)

                    self.accountant_transactions_with_trx_code_and_teller = pd.merge(
                        left=self.accountant_transactions_with_trx_code_of_teller,
                        right=self.teller.teller_transactions[
                            [col for col in self.teller.teller_transactions.columns if col != 'TRANSACTION_DATE']
                            ],
                        left_on=['T24_ACCOUNT', 'TRANSACTION_REF'],#'TRANSACTION_DATE',
                        right_on=['T24_ACCOUNT', 'TRANSACTION_REF'],
                        how='left',
                        indicator=True,
                        validate='one_to_one'
                    ).copy(deep=True)
                else:
                    self.accountant_transactions_with_trx_code_and_teller = self.accountant_transactions_with_trx_code_of_teller
                    self.accountant_transactions_with_trx_code_and_teller['_merge'] = 'left_only'


                print('****************  self.accountant_transactions_with_trx_code_and_teller.columns  ******************')
                print(self.accountant_transactions_with_trx_code_and_teller.columns)
                if (self.accountant_transactions_with_trx_code_and_teller['_merge'] == 'both').all():
                    print('======================== caisse - Teller - case 1 - all both =============================')
                    self.teller.teller_transactions_to_process = self.accountant_transactions_with_trx_code_and_teller.copy(deep=True)
                    self.teller.process_transactions(self.account['account_detail'], self.account['customer_id'], self.account['account_type'], self.account['account_rp'])
                    self.stacked_df_caisse = pd.concat([self.stacked_df_caisse, self.teller.teller_transactions_processed], ignore_index=True).copy(deep=True)

                    tmp = pd.DataFrame()
                    tmp = self.accountant_transactions_with_trx_code_and_teller[['ACCOUNTANT_SOURCE', 'T24_ACCOUNT', 'EQ_ACCOUNT', 'ORACLE_ACCOUNT', 'OP_TYPE', 'APP_SOURCE', 'APP_SOURCE_CODE', 'TRANSACTION_CODE_ATB', 'Categorie_de_transaction', 'TRANSACTION_REF', 'TRANSACTION_SEQ', 'TRANSACTION_DATE']].copy(deep=True)
                    #tmp.loc[:, 'TRANSACTION_DATE'] = '1' + tmp['TRANSACTION_DATE']
                    self.processed_accountant_caisse = pd.concat([self.processed_accountant_caisse, tmp], ignore_index=True).copy(deep=True)
                    
                elif (self.accountant_transactions_with_trx_code_and_teller['_merge'] == 'left_only').all():
                    print('======================== caisse - Teller - case 2 - left only =============================')
                    tmp = pd.DataFrame()
                    tmp = self.accountant_transactions_with_trx_code_and_teller[['ACCOUNTANT_SOURCE', 'T24_ACCOUNT', 'EQ_ACCOUNT', 'ORACLE_ACCOUNT', 'OP_TYPE', 'Categorie_de_transaction', 'APP_SOURCE_CODE', 'TRANSACTION_REF', 'TRANSACTION_SEQ', 'TRANSACTION_DATE', 'TRANSACTION_CODE_ATB']].copy(deep=True)
                    #tmp.loc[:, 'TRANSACTION_DATE'] = '1' + tmp['TRANSACTION_DATE']

                    new_row = {
                        'Operation_Type': 'Teller',
                        'Accountant_TRX_Non_Matched': self.accountant_transactions_with_trx_code_and_teller,
                        'Accountant_TRX_Matched': pd.DataFrame(),
                        'App_TRX': self.teller.teller_transactions
                    }
                    new_row_df = pd.DataFrame([new_row])
                    self.accountant_vs_app_data_caisse = pd.concat([self.accountant_vs_app_data_caisse, new_row_df], ignore_index=True).copy(deep=True)
                else:
                    print('======================== caisse - Teller - case 3 - both & left =============================')
                    self.teller.teller_transactions_to_process = self.accountant_transactions_with_trx_code_and_teller[self.accountant_transactions_with_trx_code_and_teller['_merge'] == 'both'].copy(deep=True)                                       
                    self.teller.process_transactions(self.account['account_detail'], self.account['customer_id'], self.account['account_type'], self.account['account_rp'])
                    self.stacked_df_caisse = pd.concat([self.stacked_df_caisse, self.teller.teller_transactions_processed], ignore_index=True).copy(deep=True)
                    
                    
                    tmp = pd.DataFrame()
                    tmp = self.accountant_transactions_with_trx_code_and_teller.query("_merge == 'both'")[['ACCOUNTANT_SOURCE', 'T24_ACCOUNT', 'EQ_ACCOUNT', 'ORACLE_ACCOUNT', 'OP_TYPE', 'APP_SOURCE', 'APP_SOURCE_CODE', 'TRANSACTION_CODE_ATB', 'Categorie_de_transaction', 'TRANSACTION_REF', 'TRANSACTION_SEQ', 'TRANSACTION_DATE']].copy(deep=True)
                    #tmp.loc[:, 'TRANSACTION_DATE'] = '1' + tmp['TRANSACTION_DATE']
                    self.processed_accountant_caisse = pd.concat([self.processed_accountant_caisse, tmp], ignore_index=True).copy(deep=True)
                    


                    new_row = {
                        'Operation_Type': 'Teller',
                        'Accountant_TRX_Non_Matched': self.accountant_transactions_with_trx_code_and_teller[self.accountant_transactions_with_trx_code_and_teller['_merge'] != 'both'],
                        'Accountant_TRX_Matched': self.accountant_transactions_with_trx_code_and_teller[self.accountant_transactions_with_trx_code_and_teller['_merge'] == 'both'],
                        'App_TRX': self.teller.teller_transactions
                    }
                    new_row_df = pd.DataFrame([new_row])
                    self.accountant_vs_app_data_caisse = pd.concat([self.accountant_vs_app_data_caisse, new_row_df], ignore_index=True).copy(deep=True)
                
                accountant_transactions_count = len(self.accountant_transactions_with_trx_code_of_teller)
                app_transactions_count = len(self.teller.teller_transactions)

                matching_rows_count = (self.accountant_transactions_with_trx_code_and_teller['_merge'] != 'both').sum()

                new_row = {
                    'Operation_Type': 'Teller',
                    'Accountant_Transactions_Count': accountant_transactions_count,
                    'App_Transactions_Count': app_transactions_count,
                    'Non_Matched_ops': matching_rows_count
                }
                new_row_df = pd.DataFrame([new_row])
                self.accountant_vs_app_summary_caisse = pd.concat([self.accountant_vs_app_summary_caisse, new_row_df], ignore_index=True).copy(deep=True)



    def clear_cache(self):
        
        self.stacked_df_caisse = pd.DataFrame()
        self.accountant_vs_app_data_caisse = pd.DataFrame()
        self.accountant_vs_app_summary_caisse = pd.DataFrame()

        # Cashier
        self.accountant_transactions_with_trx_code_of_cashier = pd.DataFrame()
        self.accountant_transactions_with_trx_code_and_cashier = pd.DataFrame()
        self.cashier.clear_cache()

        # Teller
        self.accountant_transactions_with_trx_code_of_teller = pd.DataFrame()
        self.accountant_transactions_with_trx_code_and_teller = pd.DataFrame()
        self.teller.clear_cache()

        self.processed_accountant_caisse = pd.DataFrame()
