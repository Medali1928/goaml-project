import pandas as pd
from src.helpers.transaction_code_loader import TransactionCodeLoader
from src.helpers.logger_manager import LoggerManager
from src.controller.default_handler import load_defaults

from src.model.eq_accountant import EQAccountant
from src.model.t24_accountant import T24Accountant
from src.controller.caisse import Caisse
from src.controller.virement import Virement
from src.controller.cheque import Cheque
from src.controller.transfert import Transfert
from src.controller.carte import Carte
from src.controller.effet import Effet
from src.controller.unknown_transaction import UnknownTransaction



class TransactionRouter:

    def __init__(self, transaction_code: dict = None, db_config: dict = None, log_enabled: bool = True):

        self.logger_manager = LoggerManager(log_enabled)
        self.transaction_code = pd.DataFrame()

        if transaction_code:
            self.load_transaction_codes(transaction_code['file_path'], sheet_name=transaction_code['sheet_name'])
            print(self.transaction_code.columns)
        
        self.eq_accountant = EQAccountant(db_config)
        self.t24_accountant = T24Accountant(db_config)
        self.virement = Virement(db_config)
        self.transfert = Transfert(db_config)
        self.carte = Carte(db_config)
        self.cheque = Cheque(db_config)
        self.caisse = Caisse(db_config=db_config,)
        self.effet = Effet(db_config)
        self.unknown_transaction = UnknownTransaction(db_config)

    def _log(self, level, message, *args, **kwargs):
        """Logs a message using the logger manager if logging is enabled."""
        self.logger_manager.log(level, message, *args, **kwargs)
        
    def load_transaction_codes(
        self,
        file_path: str,
        sheet_name: str
    ) -> None:
        """
        Loads transaction codes using TransactionCodeLoader.

        Args:
            file_path (str): Path to the Excel file containing transaction codes.
            sheet_name (str): The sheet name in the Excel file.
        """
        try:
            self.transaction_code = TransactionCodeLoader.load(
                file_path, sheet_name
            )
            self._log("info", "Transaction codes loaded successfully.")
        except Exception as e:
            self._log("error", "Error loading transaction codes: %s", e)
            raise

    def get_transactions(self, account: dict, year : str, start_balance : float):
        
        self.unified_accountant = pd.DataFrame()
        if int(year) < 2026:
            self.eq_accountant.get_accountant_transactions(account['account_correspondences']['EQ_ACCOUNT'], year)
        if int(year) >= 2022:
            self.t24_accountant.get_accountant_transactions(account['account_correspondences']['T24_ACCOUNT'], year)

        if not self.eq_accountant.accountant_transactions.empty and not self.t24_accountant.accountant_transactions.empty:

            self.eq_accountant.accountant_transactions['APP_SOURCE_CODE'] = self.eq_accountant.accountant_transactions['APP_SOURCE_CODE'].str.strip()
            self.eq_accountant.accountant_transactions['APP_SOURCE_CODE'] = self.eq_accountant.accountant_transactions['APP_SOURCE_CODE'].str.upper()
            self.eq_accountant.accountant_transactions['TRANSACTION_CODE_ATB'] = self.eq_accountant.accountant_transactions['TRANSACTION_CODE_ATB'].astype(int).astype(str).str.zfill(3)

            self.unified_accountant = (
                pd.concat(
                    [
                        self.eq_accountant.accountant_transactions,#.loc[self.eq_accountant.accountant_transactions['APP_SOURCE_CODE'] != 'T24TL'],
                        self.t24_accountant.accountant_transactions#.loc[self.t24_accountant.accountant_transactions['APP_SOURCE_CODE'] == 'TT']
                    ],
                    ignore_index=True
                )
                .sort_values(by=['T24_ACCOUNT', 'APP_SOURCE_CODE', 'TRANSACTION_CODE_ATB', 'TRANSACTION_DATE', 'TRANSACTION_REF', 'TRANSACTION_SEQ'])
                .sort_values(by='ACCOUNTANT_SOURCE', key=lambda x: x.eq('EQ'), ascending=False)
                .drop_duplicates(
                    subset=['T24_ACCOUNT', 'APP_SOURCE_CODE', 'TRANSACTION_CODE_ATB', 'TRANSACTION_DATE', 'TRANSACTION_REF', 'TRANSACTION_SEQ'],
                    keep='first'
                )
                .copy(deep=True)  # Ensure fresh reference
            )

        elif not self.eq_accountant.accountant_transactions.empty:
            self.unified_accountant = pd.DataFrame()
            
            self.eq_accountant.accountant_transactions = (
                self.eq_accountant.accountant_transactions
                .sort_values(by=['EQ_ACCOUNT', 'APP_SOURCE_CODE', 'TRANSACTION_CODE_ATB', 'TRANSACTION_DATE', 'TRANSACTION_REF', 'TRANSACTION_SEQ'])
                .copy(deep=True)  # Ensure fresh reference after sorting
            )

            self.unified_accountant = (
                self.eq_accountant.accountant_transactions
                .drop_duplicates(subset=['EQ_ACCOUNT', 'APP_SOURCE_CODE', 'TRANSACTION_CODE_ATB', 'TRANSACTION_DATE', 'TRANSACTION_REF', 'TRANSACTION_SEQ'], keep='first')
                .copy(deep=True)  # Ensure fresh reference after dropping duplicates
            )
        elif not self.t24_accountant.accountant_transactions.empty:
            self.unified_accountant = (
                self.t24_accountant.accountant_transactions
                    #.loc[self.t24_accountant.accountant_transactions['APP_SOURCE_CODE'] == 'TT']
                    .sort_values(
                        by=[
                            'T24_ACCOUNT', 'APP_SOURCE_CODE', 'TRANSACTION_CODE_ATB',
                            'TRANSACTION_DATE', 'TRANSACTION_REF', 'TRANSACTION_SEQ'
                        ]
                    )
                    .drop_duplicates(
                        subset=[
                            'T24_ACCOUNT', 'APP_SOURCE_CODE', 'TRANSACTION_CODE_ATB',
                            'TRANSACTION_DATE', 'TRANSACTION_REF', 'TRANSACTION_SEQ'
                        ],
                        keep='first'
                    )
                    .copy(deep=True)  # Ensure fresh reference
            )

        # add accountant filters
        
        if not self.unified_accountant.empty:

            print('==================  1 - unified_accountant ==================')
            print(self.unified_accountant.info())
            print('=========================================================')
            self.accountant_transactions_with_trx_code = pd.merge(
                left=self.unified_accountant.copy(deep=True),
                right=self.transaction_code[['ACCOUNTANT_SOURCE', 'OP_TYPE', 'APP_SOURCE', 'APP_SOURCE_CODE', 'TRANSACTION_CODE_ATB', 'TRANSACTION_DESC_ATB', 'Categorie_de_transaction', 'TRANSACTION_DESC_GOAML', 'TRANSACTION_CODE_GOAML', 'FUND_CODE_1', 'FUND_CODE_2', 'IS_INTERFACE', 'IS_MANUELLE']].copy(deep=True),
                left_on=['ACCOUNTANT_SOURCE', 'APP_SOURCE_CODE', 'TRANSACTION_CODE_ATB'],
                right_on=['ACCOUNTANT_SOURCE', 'APP_SOURCE_CODE', 'TRANSACTION_CODE_ATB'],
                #left_on='TRANSACTION_CODE_ATB',
                #right_on='TRANSACTION_CODE_ATB',
                how='left',
                suffixes=('_ACC', '_F'), # accountant, param trx code file
                validate='many_to_one'
            ).copy(deep=True)
            
            print("Unknown transaction count:",self.accountant_transactions_with_trx_code['OP_TYPE'].isna().sum())

            # Fill missing goAML mapping values from param_file/default.txt instead of stopping generation.
            # The fallback is also exported so the user can complete accountant_trx.xlsx later.
            mapping_columns = ['TRANSACTION_CODE_GOAML', 'FUND_CODE_1', 'FUND_CODE_2']
            context_columns = [
                'ACCOUNTANT_SOURCE', 'APP_SOURCE_CODE', 'TRANSACTION_CODE_ATB',
                'TRANSACTION_DESC_ATB_ACC', 'TRANSACTION_DATE', 'TRANSACTION_REF', 'TRANSACTION_SEQ'
            ]
            defaults = load_defaults()
            fallback_values = {
                'TRANSACTION_CODE_GOAML': defaults.get('DEFAULT_TRANSACTION_CODE_GOAML', defaults.get('TRANSACTION_CODE_GOAML', 'B999')),
                'FUND_CODE_1': defaults.get('DEFAULT_FUND_CODE_1', defaults.get('FUND_CODE_1', 'A')),
                'FUND_CODE_2': defaults.get('DEFAULT_FUND_CODE_2', defaults.get('FUND_CODE_2', 'A')),
            }

            def _is_missing_mapping_value(value):
                if pd.isna(value):
                    return True
                value = str(value).strip()
                return value == '' or value.lower() in {'nan', 'none', 'null'}

            missing_mapping_mask = self.accountant_transactions_with_trx_code[mapping_columns].applymap(_is_missing_mapping_value).any(axis=1)
            self.accountant_transactions_with_trx_code['GOAML_MAPPING_FALLBACK_USED'] = 'N'

            if missing_mapping_mask.any():
                missing_mapping = self.accountant_transactions_with_trx_code.loc[
                    missing_mapping_mask,
                    [c for c in context_columns + ['OP_TYPE'] + mapping_columns if c in self.accountant_transactions_with_trx_code.columns]
                ].drop_duplicates().copy(deep=True)

                for col, fallback in fallback_values.items():
                    missing_mapping[f'DEFAULT_{col}_APPLIED'] = fallback
                    col_missing_mask = self.accountant_transactions_with_trx_code[col].apply(_is_missing_mapping_value)
                    self.accountant_transactions_with_trx_code.loc[col_missing_mask, col] = fallback

                self.accountant_transactions_with_trx_code.loc[missing_mapping_mask, 'GOAML_MAPPING_FALLBACK_USED'] = 'Y'

                # missing_mapping.to_excel(
                #     f"./output/{account['account_correspondences']['EQ_ACCOUNT']}/{account['account_correspondences']['EQ_ACCOUNT']}_missing_goaml_mapping_defaults_applied_{year}.xlsx",
                #     index=False
                # )
                self._log(
                    "warning",
                    "Missing goAML mapping for %s accountant row(s). Defaults applied from param_file/default.txt. Details exported to output/%s/%s_missing_goaml_mapping_defaults_applied_%s.xlsx",
                    len(missing_mapping), account['account_correspondences']['EQ_ACCOUNT'], account['account_correspondences']['EQ_ACCOUNT'], year
                )
            
			# final unification filter
            self.accountant_transactions_with_trx_code = self.accountant_transactions_with_trx_code.loc[self.accountant_transactions_with_trx_code['IS_INTERFACE'] != 'Y'].copy(deep=True)	

            print("écriture fichier comptable")
            try:
                self.accountant_transactions_with_trx_code.to_csv("C:\GOAML\comptable.csv", index=False) 
                print("DataFrame saved to comptable.csv successfully.")
            except OSError as e:
                print(f"File error: {e}")



            #self.accountant_transactions_with_trx_code.drop_duplicates(
            #    subset=['T24_ACCOUNT', 'APP_SOURCE_CODE', 'TRANSACTION_CODE_ATB', 'TRANSACTION_DATE', 'TRANSACTION_REF', 'TRANSACTION_SEQ'],
            #    keep='first',
            #    inplace=True
            #)
            

            self.accountant_transactions_with_trx_code['TRANSACTION_DESC_ATB_ACC'] = self.accountant_transactions_with_trx_code['TRANSACTION_DESC_ATB_ACC'].str.strip()
            print('==================  2 - accountant_transactions_with_trx_code ==================')
            print(self.accountant_transactions_with_trx_code.info())
            print('=========================================================')
           # Virement
            self.virement.account =  account
            self.virement.accountant_trx = self.accountant_transactions_with_trx_code.query(
                "OP_TYPE == 'Virement' and Categorie_de_transaction == 'code affectant directement le compte client (débit/crédit)'"
            )

            self.virement.year = year
            self.virement.get_transactions()
            self.virement.process_transactions()
            # 2026-01-12
            if not self.virement.stacked_df_virement.empty:
                #print("---------router------------")
                #print(self.virement.stacked_df_virement.empty)
                self.stacked_df = pd.concat([self.stacked_df, self.virement.stacked_df_virement], ignore_index=True).copy(deep=True)
                #print("***********************")
                #print(self.virement.accountant_vs_app_data_virement)
                self.accountant_vs_app_data = pd.concat([self.accountant_vs_app_data, self.virement.accountant_vs_app_data_virement], ignore_index=True).copy(deep=True)
                #print("***********************************")
                #print(self.virement.accountant_vs_app_summary_virement)
                self.accountant_vs_app_summary = pd.concat([self.accountant_vs_app_summary, self.virement.accountant_vs_app_summary_virement], ignore_index=True).copy(deep=True)
            
                self.processed_accountant = pd.concat([self.processed_accountant, self.virement.processed_accountant_virement], ignore_index=True).copy(deep=True)
            else:
                #print(self.virement.accountant_vs_app_data_virement)
                self.accountant_vs_app_data = pd.concat([self.accountant_vs_app_data, self.virement.accountant_vs_app_data_virement], ignore_index=True).copy(deep=True)
                #print("***********************************")
                #print(self.virement.accountant_vs_app_summary_virement)
                self.accountant_vs_app_summary = pd.concat([self.accountant_vs_app_summary, self.virement.accountant_vs_app_summary_virement], ignore_index=True).copy(deep=True)
                self.processed_accountant = pd.concat([self.processed_accountant, self.virement.processed_accountant_virement], ignore_index=True).copy(deep=True)
            # Transfert
            self.transfert.account =  account
            self.transfert.accountant_trx = self.accountant_transactions_with_trx_code.query(
                "OP_TYPE == 'Transfert' and Categorie_de_transaction == 'code affectant directement le compte client (débit/crédit)' and (APP_SOURCE == 'Clean Payment' or APP_SOURCE == 'TPH')"
            ).copy(deep=True)
            self.transfert.year = year
            self.transfert.get_transactions()
            self.transfert.process_transactions()
            if not self.transfert.stacked_df_transfert.empty:
                self.stacked_df = pd.concat([self.stacked_df, self.transfert.stacked_df_transfert], ignore_index=True).copy(deep=True)
                self.accountant_vs_app_data = pd.concat([self.accountant_vs_app_data, self.transfert.accountant_vs_app_data_transfert], ignore_index=True).copy(deep=True)
                self.accountant_vs_app_summary = pd.concat([self.accountant_vs_app_summary, self.transfert.accountant_vs_app_summary_transfert], ignore_index=True).copy(deep=True)
                
                self.processed_accountant = pd.concat([self.processed_accountant, self.transfert.processed_accountant_transfert], ignore_index=True).copy(deep=True)
            else:
                self.accountant_vs_app_data = pd.concat([self.accountant_vs_app_data, self.transfert.accountant_vs_app_data_transfert], ignore_index=True).copy(deep=True)
                self.accountant_vs_app_summary = pd.concat([self.accountant_vs_app_summary, self.transfert.accountant_vs_app_summary_transfert], ignore_index=True).copy(deep=True)
                
                self.processed_accountant = pd.concat([self.processed_accountant, self.transfert.processed_accountant_transfert], ignore_index=True).copy(deep=True)
                
            # Carte
            print("============================== transaction router - card =========================================")
            print("=======================================================================")
            self.carte.account =  account
            self.carte.accountant_trx = self.accountant_transactions_with_trx_code.query(
                "OP_TYPE == 'Carte' and Categorie_de_transaction == 'code affectant directement le compte client (débit/crédit)'"
            )
            #print('card router')
            #print(self.carte.accountant_trx)
            self.carte.year = year
            self.carte.get_transactions()
            self.carte.process_transactions()

            if not self.carte.stacked_df_carte.empty:
                print("=============================== transaction router - card - case 1========================================")
                print(self.carte.stacked_df_carte.empty)
                print(self.carte.stacked_df_carte)
                print("=======================================================================")
                self.stacked_df = pd.concat([self.stacked_df, self.carte.stacked_df_carte], ignore_index=True).copy(deep=True)
                self.accountant_vs_app_data = pd.concat([self.accountant_vs_app_data, self.carte.accountant_vs_app_data_carte], ignore_index=True).copy(deep=True)
                self.accountant_vs_app_summary = pd.concat([self.accountant_vs_app_summary, self.carte.accountant_vs_app_summary_carte], ignore_index=True).copy(deep=True)
                print("-------------------")
                print(self.carte.processed_accountant_carte)
                print("-------------------")
                self.processed_accountant = pd.concat([self.processed_accountant, self.carte.processed_accountant_carte], ignore_index=True).copy(deep=True)
            else:
                print("=============================== transaction router - card - case 2 - is empty ========================================")
                print(self.carte.stacked_df_carte.empty)
                print("=======================================================================")
                self.accountant_vs_app_data = pd.concat([self.accountant_vs_app_data, self.carte.accountant_vs_app_data_carte], ignore_index=True).copy(deep=True)
                self.accountant_vs_app_summary = pd.concat([self.accountant_vs_app_summary, self.carte.accountant_vs_app_summary_carte], ignore_index=True).copy(deep=True)
                
                self.processed_accountant = pd.concat([self.processed_accountant, self.carte.processed_accountant_carte], ignore_index=True).copy(deep=True)
            
            # Cheque
            self.cheque.account =  account
            self.cheque.accountant_trx = self.accountant_transactions_with_trx_code.query(
               "OP_TYPE == 'Cheque' and Categorie_de_transaction == 'code affectant directement le compte client (débit/crédit)'"
            )
            self.cheque.year = year
            self.cheque.get_transactions()
            self.cheque.process_transactions()
            if not self.cheque.stacked_df_cheque.empty:
               self.stacked_df = pd.concat([self.stacked_df, self.cheque.stacked_df_cheque], ignore_index=True).copy(deep=True)
               self.accountant_vs_app_data = pd.concat([self.accountant_vs_app_data, self.cheque.accountant_vs_app_data_cheque], ignore_index=True).copy(deep=True)
               self.accountant_vs_app_summary = pd.concat([self.accountant_vs_app_summary, self.cheque.accountant_vs_app_summary_cheque], ignore_index=True).copy(deep=True)
            
               self.processed_accountant = pd.concat([self.processed_accountant, self.cheque.processed_accountant_cheque], ignore_index=True).copy(deep=True)

            else:
               self.accountant_vs_app_data = pd.concat([self.accountant_vs_app_data, self.cheque.accountant_vs_app_data_cheque], ignore_index=True).copy(deep=True)
               self.accountant_vs_app_summary = pd.concat([self.accountant_vs_app_summary, self.cheque.accountant_vs_app_summary_cheque], ignore_index=True).copy(deep=True)

               self.processed_accountant = pd.concat([self.processed_accountant, self.cheque.processed_accountant_cheque], ignore_index=True).copy(deep=True)
            # Caisse
            self.caisse.accountant_trx = self.accountant_transactions_with_trx_code.query("APP_SOURCE_CODE == '@AAA' | APP_SOURCE_CODE == 'T24TL'").copy(deep=True)#.query("OP_TYPE == 'Caisse'")
            self.caisse.accountant_trx = self.accountant_transactions_with_trx_code.query("OP_TYPE == 'Caisse'").copy(deep=True)
            self.caisse.account =  account
            self.caisse.accountant_trx = self.accountant_transactions_with_trx_code.query(
                "OP_TYPE == 'Caisse' and Categorie_de_transaction == 'code affectant directement le compte client (débit/crédit)'"
            )
            self.caisse.year = year
            self.caisse.get_transactions()
            self.caisse.process_transactions()
            if not self.caisse.stacked_df_caisse.empty:
                self.stacked_df = pd.concat([self.stacked_df, self.caisse.stacked_df_caisse], ignore_index=True).copy(deep=True)
                self.accountant_vs_app_data = pd.concat([self.accountant_vs_app_data, self.caisse.accountant_vs_app_data_caisse], ignore_index=True).copy(deep=True)
                self.accountant_vs_app_summary = pd.concat([self.accountant_vs_app_summary, self.caisse.accountant_vs_app_summary_caisse], ignore_index=True).copy(deep=True)
            
                self.processed_accountant = pd.concat([self.processed_accountant, self.caisse.processed_accountant_caisse], ignore_index=True).copy(deep=True)
            else:
                self.accountant_vs_app_data = pd.concat([self.accountant_vs_app_data, self.caisse.accountant_vs_app_data_caisse], ignore_index=True).copy(deep=True)
                self.accountant_vs_app_summary = pd.concat([self.accountant_vs_app_summary, self.caisse.accountant_vs_app_summary_caisse], ignore_index=True).copy(deep=True)
                
                self.processed_accountant = pd.concat([self.processed_accountant, self.caisse.processed_accountant_caisse], ignore_index=True).copy(deep=True)
        	# effet
            self.effet.account =  account
            self.effet.accountant_trx = self.accountant_transactions_with_trx_code.query(
               "OP_TYPE == 'Effet' and Categorie_de_transaction == 'code affectant directement le compte client (débit/crédit)'"
            )
            self.effet.year = year
            self.effet.get_transactions()
            self.effet.process_transactions()
            if not self.effet.stacked_df_effet.empty:
               self.stacked_df = pd.concat([self.stacked_df, self.effet.stacked_df_effet], ignore_index=True).copy(deep=True)
               self.accountant_vs_app_data = pd.concat([self.accountant_vs_app_data, self.effet.accountant_vs_app_data_effet], ignore_index=True).copy(deep=True)
               self.accountant_vs_app_summary = pd.concat([self.accountant_vs_app_summary, self.effet.accountant_vs_app_summary_effet], ignore_index=True).copy(deep=True)
            
               self.processed_accountant = pd.concat([self.processed_accountant, self.effet.processed_accountant_effet], ignore_index=True).copy(deep=True)

            else:
               self.accountant_vs_app_data = pd.concat([self.accountant_vs_app_data, self.effet.accountant_vs_app_data_effet], ignore_index=True).copy(deep=True)
               self.accountant_vs_app_summary = pd.concat([self.accountant_vs_app_summary, self.effet.accountant_vs_app_summary_effet], ignore_index=True).copy(deep=True)

               self.processed_accountant = pd.concat([self.processed_accountant, self.effet.processed_accountant_effet], ignore_index=True).copy(deep=True)
			
			# Unknown transactions
            # Anything not selected by the specialised handlers above must still be exported.
            # This includes empty OP_TYPE values and non-empty OP_TYPE values that are not
            # Virement/Transfert/Carte/Cheque/Caisse/Effet, or rows excluded by a handler's
            # extra criteria such as category/app-source filters.
            direct_category = 'code affectant directement le compte client (débit/crédit)'
            op_type_norm = self.accountant_transactions_with_trx_code['OP_TYPE'].fillna('').astype(str).str.strip()
            category_norm = self.accountant_transactions_with_trx_code['Categorie_de_transaction'].fillna('').astype(str).str.strip()
            app_source_norm = self.accountant_transactions_with_trx_code['APP_SOURCE'].fillna('').astype(str).str.strip()

            direct_mask = category_norm.eq(direct_category)
            handled_mask = (
                (op_type_norm.eq('Virement') & direct_mask) |
                (op_type_norm.eq('Transfert') & direct_mask & app_source_norm.isin(['Clean Payment', 'TPH'])) |
                (op_type_norm.eq('Carte') & direct_mask) |
                (op_type_norm.eq('Cheque') & direct_mask) |
                (op_type_norm.eq('Caisse') & direct_mask) |
                (op_type_norm.eq('Effet') & direct_mask)
            )
            unknown_mask = ~handled_mask

            self.unknown_transaction.accountant_trx = (
                self.accountant_transactions_with_trx_code.loc[unknown_mask].copy(deep=True)
            )

            self._log(
                "info",
                "Unknown/default handler will process %s accountant row(s) not handled by specialised modules.",
                len(self.unknown_transaction.accountant_trx)
            )

            self.unknown_transaction.process_transactions(account['account_detail'])

            if not self.unknown_transaction.stacked_df_unknown.empty:

                self.stacked_df = pd.concat(
                    [
                        self.stacked_df,
                        self.unknown_transaction.stacked_df_unknown
                    ],
                    ignore_index=True
                ).copy(deep=True)

                self.processed_accountant = pd.concat(
                    [
                        self.processed_accountant,
                        self.unknown_transaction.processed_accountant_unknown
                    ],
                    ignore_index=True
                ).copy(deep=True)
			

    # called before fetching account's trx
    def clear_cache(self):

        self.eq_accountant.accountant_transactions = pd.DataFrame()
        self.accountant_transactions_with_trx_code = pd.DataFrame()
        self.stacked_df = pd.DataFrame(columns=['transaction_date', 'transaction_detail'])
        self.accountant_vs_app_summary = pd.DataFrame(columns=['Operation_Type', 'Accountant_Transactions_Count', 'App_Transactions_Count', 'Non_Matched_ops'])
        self.accountant_vs_app_data = pd.DataFrame(columns=['Operation_Type', 'Accountant_Transactions', 'App_Transactions'])

        self.accountant = pd.DataFrame()
        self.processed_accountant = pd.DataFrame()

        self.transfert.clear_cache()
        self.virement.clear_cache()
        self.caisse.clear_cache()
        self.carte.clear_cache()
        self.effet.clear_cache()
        self.unknown_transaction.clear_cache()
