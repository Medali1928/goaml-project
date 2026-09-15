import pandas as pd

from src.model.mxp_carte import Card as MXP_Carte


class Carte:

    def __init__(self, db_config: dict):

        self.account = {}
        self.accountant_trx = pd.DataFrame()
        self.year = ''

        self.mxp_carte = MXP_Carte(db_config)

        # IBANK carte
        self.accountant_transactions_with_trx_code_of_mxp_carte = pd.DataFrame() # accountant + trx_codes (param-file)
        self.accountant_transactions_with_trx_code_and_mxp_carte = pd.DataFrame() # accountant + trx_codes (param-file) + extrat
        
        # local variables
        self.stacked_df_carte = pd.DataFrame()
        self.accountant_vs_app_data_carte = pd.DataFrame()
        self.accountant_vs_app_summary_carte = pd.DataFrame()

        self.processed_accountant_carte = pd.DataFrame()

    def get_transactions(self):

        #self.clear_cache()

        if not self.accountant_trx.query("OP_TYPE == 'Carte'").empty:

            if not self.accountant_trx.query("(ACCOUNTANT_SOURCE == 'EQ') & (OP_TYPE == 'Carte') & (APP_SOURCE == 'MXP') & (IS_MANUELLE != 'Y')").empty:

                if not self.mxp_carte.account_related_cards:
                    print("self.account_related_cards is empty")
                    self.mxp_carte.retrieve_cards_by_account(self.account['account_correspondences']['ORACLE_ACCOUNT'])

                self.mxp_carte.get_card_transactions(self.account['account_correspondences']['ORACLE_ACCOUNT'], self.year)
                #self.mxp_carte.get_card_transactions_2(self.account['account_correspondences']['ORACLE_ACCOUNT'], self.year)
                #self.mxp_carte.get_card_transactions_international(self.account['account_correspondences']['ORACLE_ACCOUNT'], self.year)



    def process_transactions(self):

        print("process_transactions")

        if not self.accountant_trx.query("OP_TYPE == 'Carte'").empty:

            # mxp carte
            if not self.accountant_trx.query("(ACCOUNTANT_SOURCE == 'EQ') & (OP_TYPE == 'Carte') & (APP_SOURCE == 'MXP') & (IS_MANUELLE != 'Y')").empty:

                self.accountant_transactions_with_trx_code_of_mxp_carte = self.accountant_trx.query("(ACCOUNTANT_SOURCE == 'EQ') & (OP_TYPE == 'Carte') & (APP_SOURCE == 'MXP') & (IS_MANUELLE != 'Y')").copy(deep=True)

                # Remove duplicates from sub filtered 'accountant_transactions_with_trx_code_of_mxp_carte'
                self.accountant_transactions_with_trx_code_of_mxp_carte.drop_duplicates(subset=['EQ_ACCOUNT', 'TRANSACTION_REF', 'TRANSACTION_DATE'], inplace=True)

                self.accountant_transactions_with_trx_code_of_mxp_carte.loc[:, 'T24_ACCOUNT'] = self.accountant_transactions_with_trx_code_of_mxp_carte['T24_ACCOUNT'].astype(str).str.strip()
                self.accountant_transactions_with_trx_code_of_mxp_carte.loc[:, 'EQ_ACCOUNT'] = self.accountant_transactions_with_trx_code_of_mxp_carte['EQ_ACCOUNT'].astype(str).str.strip()
                self.accountant_transactions_with_trx_code_of_mxp_carte.loc[:, 'ORACLE_ACCOUNT'] = self.accountant_transactions_with_trx_code_of_mxp_carte['ORACLE_ACCOUNT'].astype(str).str.strip()
                self.accountant_transactions_with_trx_code_of_mxp_carte.loc[:, 'TRANSACTION_REF'] = self.accountant_transactions_with_trx_code_of_mxp_carte['TRANSACTION_REF'].astype(str).str.strip()              

                def get_transaction_nature(code):
                    if code in ['425', '426', '427', '428', '927']:
                        return 'ATM_Withdrawal'
                    elif code == '439':
                        return 'Card_Payment'
                    else:
                        return 'Unknown'  # Or some other default value
                    
                # extrat data are available
                if not self.mxp_carte.card_transactions.empty:                    

                    self.mxp_carte.card_transactions.sort_values(
                            by=['EQ_ACCOUNT', 'ORACLE_ACCOUNT', 'CARD_NUMBER', 'MXP_SOURCE', 'DATE_TRANSACTION', 'TRANSACTION_REF'],
                            inplace=True
                    )

                    self.mxp_carte.card_transactions.drop_duplicates(
                        subset=['EQ_ACCOUNT', 'ORACLE_ACCOUNT', 'CARD_NUMBER', 'MXP_SOURCE', 'DATE_TRANSACTION', 'TRANSACTION_REF'], 
                        keep='first',
                        inplace=True
                    )
                    
                    self.accountant_transactions_with_trx_code_and_mxp_carte = pd.merge(
                        left=self.accountant_transactions_with_trx_code_of_mxp_carte,
                        right=self.mxp_carte.card_transactions,
                        left_on=['EQ_ACCOUNT', 'ORACLE_ACCOUNT', 'TRANSACTION_REF'],
                        right_on=['EQ_ACCOUNT', 'ORACLE_ACCOUNT','TRANSACTION_REF'],
                        how='left',
                        indicator=True,
                        validate='one_to_one'
                    ).copy(deep=True)
                else:
                    self.accountant_transactions_with_trx_code_and_mxp_carte = self.accountant_transactions_with_trx_code_of_mxp_carte
                    self.accountant_transactions_with_trx_code_and_mxp_carte['_merge'] = 'left_only'
                
                self.accountant_transactions_with_trx_code_and_mxp_carte['TRANSACTION_NATURE'] = self.accountant_transactions_with_trx_code_and_mxp_carte['TRANSACTION_CODE_ATB'].apply(get_transaction_nature)
                self.accountant_transactions_with_trx_code_and_mxp_carte['CURRENCY_CODE_1'] = self.accountant_transactions_with_trx_code_and_mxp_carte['TRANSACTION_CURRENCY'] # eq accountant
                self.accountant_transactions_with_trx_code_and_mxp_carte['FOREIGN_AMOUNT_1'] = self.accountant_transactions_with_trx_code_and_mxp_carte['TRANSACTION_AMOUNT'].apply(lambda x: str(abs(float(x)))) # eq accountant
                
                #if self.accountant_transactions_with_trx_code_and_mxp_carte['TRANSACTION_CURRENCY'] != 'TND':
                #    self.accountant_transactions_with_trx_code_and_mxp_carte['AMOUNT_LOCAL'] = self.accountant_transactions_with_trx_code_and_mxp_carte['TRANSACTION_AMOUNT_LCY'].apply(lambda x: str(abs(float(x))))
                #else:
                #    self.accountant_transactions_with_trx_code_and_mxp_carte['AMOUNT_LOCAL'] = self.accountant_transactions_with_trx_code_and_mxp_carte['TRANSACTION_AMOUNT'].apply(lambda x: str(abs(float(x))))

                def compute_amount_local(row):

                    if row['TRANSACTION_CURRENCY'] != 'TND':
                        return str(float(row['TRANSACTION_AMOUNT_LCY']))
                    else:
                        return str(float(row['TRANSACTION_AMOUNT']))
                
                self.accountant_transactions_with_trx_code_and_mxp_carte['AMOUNT_LOCAL'] = (
                    self.accountant_transactions_with_trx_code_and_mxp_carte.apply(
                        compute_amount_local, axis=1
                    )
                )



                print("===================================")
                print("===================================")
                print(" 0 - carte")
                print(self.accountant_transactions_with_trx_code_and_mxp_carte['_merge'].unique())
                print("===================================")
                print("===================================")
                if (self.accountant_transactions_with_trx_code_and_mxp_carte['_merge'] == 'both').all(): # accountant & extrat
                    print("===================================")
                    print("===================================")
                    print(" case 1 - all both")
                    print("===================================")
                    print("===================================")
                    self.mxp_carte.card_transactions_to_process = self.accountant_transactions_with_trx_code_and_mxp_carte.copy(deep=True)
                    self.mxp_carte.process_transactions(self.account['account_detail'], self.account['account_type'], self.account['account_rp'], self.mxp_carte.account_related_cards)
                    self.stacked_df_carte = pd.concat([self.stacked_df_carte, self.mxp_carte.card_transactions_processed], ignore_index=True).copy(deep=True)

                    print("**************")
                    print(self.stacked_df_carte)
                    # used to check with the main accountant to determine which row is processed and which not
                    self.processed_accountant_carte = pd.concat([self.processed_accountant_carte, self.accountant_transactions_with_trx_code_and_mxp_carte[['ACCOUNTANT_SOURCE', 'T24_ACCOUNT', 'EQ_ACCOUNT', 'ORACLE_ACCOUNT', 'OP_TYPE', 'APP_SOURCE', 'APP_SOURCE_CODE', 'TRANSACTION_CODE_ATB', 'Categorie_de_transaction', 'TRANSACTION_REF', 'TRANSACTION_SEQ', 'TRANSACTION_DATE']]], ignore_index=True).copy(deep=True)

                elif (self.accountant_transactions_with_trx_code_and_mxp_carte['_merge'] == 'left_only').all():
                    print("===================================")
                    print("===================================")
                    print(" case 2 - all left only")
                    print("===================================")
                    print("===================================")
                    new_row = {
                        'Operation_Type': 'Carte',
                        'Accountant_TRX_Non_Matched': self.accountant_transactions_with_trx_code_and_mxp_carte,
                        'Accountant_TRX_Matched': pd.DataFrame(),
                        'App_TRX': self.mxp_carte.card_transactions
                    }
                    print(new_row)
                    new_row_df = pd.DataFrame([new_row])
                    self.accountant_vs_app_data_carte = pd.concat([self.accountant_vs_app_data_carte, new_row_df], ignore_index=True)
                    print("**************")
                    print(self.stacked_df_carte)
                else:
                    print("===================================")
                    print("===================================")
                    print(" case 3 - left and both")
                    print("===================================")
                    print("===================================")
                    self.mxp_carte.card_transactions_to_process = self.accountant_transactions_with_trx_code_and_mxp_carte[self.accountant_transactions_with_trx_code_and_mxp_carte['_merge'] == 'both'].copy(deep=True)
                    self.mxp_carte.process_transactions(self.account['account_detail'], self.account['account_type'], self.account['account_rp'], self.mxp_carte.account_related_cards)
                    self.stacked_df_carte = pd.concat([self.stacked_df_carte, self.mxp_carte.card_transactions_processed], ignore_index=True).copy(deep=True)
                    
                    print('card controller - card trx to process')
                    print(self.accountant_transactions_with_trx_code_and_mxp_carte[self.accountant_transactions_with_trx_code_and_mxp_carte['_merge'] == 'both'])
                    self.processed_accountant_carte = pd.concat([self.processed_accountant_carte, self.accountant_transactions_with_trx_code_and_mxp_carte.query("_merge == 'both'")[['ACCOUNTANT_SOURCE', 'T24_ACCOUNT', 'EQ_ACCOUNT', 'ORACLE_ACCOUNT', 'OP_TYPE', 'APP_SOURCE', 'APP_SOURCE_CODE', 'TRANSACTION_CODE_ATB', 'Categorie_de_transaction', 'TRANSACTION_REF', 'TRANSACTION_SEQ', 'TRANSACTION_DATE']]], ignore_index=True).copy(deep=True)
                    
                    new_row = {
                        'Operation_Type': 'Carte',
                        'Accountant_TRX_Non_Matched': self.accountant_transactions_with_trx_code_and_mxp_carte[self.accountant_transactions_with_trx_code_and_mxp_carte['_merge'] != 'both'],
                        'Accountant_TRX_Matched': self.accountant_transactions_with_trx_code_and_mxp_carte[self.accountant_transactions_with_trx_code_and_mxp_carte['_merge'] == 'both'],
                        'App_TRX': self.mxp_carte.card_transactions
                    }
                    new_row_df = pd.DataFrame([new_row])
                    self.accountant_vs_app_data_carte = pd.concat([self.accountant_vs_app_data_carte, new_row_df], ignore_index=True).copy(deep=True)
                    print("**************")
                    print(self.stacked_df_carte)
                
                accountant_transactions_count = len(self.accountant_transactions_with_trx_code_of_mxp_carte)
                app_transactions_count = len(self.mxp_carte.card_transactions)
                non_matched_rows_count = (self.accountant_transactions_with_trx_code_and_mxp_carte['_merge'] != 'both').sum()
                new_row = {
                    'Operation_Type': 'Carte',
                    'Accountant_Transactions_Count': accountant_transactions_count,
                    'App_Transactions_Count': app_transactions_count,
                    'Non_Matched_ops': non_matched_rows_count
                }
                # Convert the new row to a DataFrame
                new_row_df = pd.DataFrame([new_row])
                # Use pd.concat to add the new row
                self.accountant_vs_app_summary_carte = pd.concat([self.accountant_vs_app_summary_carte, new_row_df], ignore_index=True).copy(deep=True)


    def clear_cache(self):
        
        self.stacked_df_carte = pd.DataFrame()
        self.accountant_vs_app_data_carte = pd.DataFrame()
        self.accountant_vs_app_summary_carte = pd.DataFrame()

        # IBANK carte
        self.accountant_transactions_with_trx_code_of_mxp_carte = pd.DataFrame()
        self.accountant_transactions_with_trx_code_and_mxp_carte = pd.DataFrame()

        self.processed_accountant_carte = pd.DataFrame()

        self.mxp_carte.clear_cache()