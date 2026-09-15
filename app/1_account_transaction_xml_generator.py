import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
from datetime import datetime

import streamlit as st

from src.config import DB_CONFIG, TREANSACTION_CODE
from src.model.get_client import GetClient
from src.controller.transaction_router import TransactionRouter
from src.helpers.utils import write_transaction_details_to_xml
from src.helpers.balance_calculator import update_balances


def get_transaction(get_client, transaction_router, account_number, start_year, end_year, start_balance):

    if not account_number.isdigit() or len(account_number) != 13:
        st.warning('Le numéro du compte doit être un nombre de 13 chiffres.', icon="⚠️")
        return

    if account_number:
        st.write('Processing !')
        with st.spinner('Get Client Details...'):
            account_correspondences, account_details, customer_id, account_type, account_rp = get_client.get_client_details(account_number)
            print('account details')
            print(account_details)
            print('rp')
            print(account_rp)

            account = {
                'account_number': account_number,
                'account_correspondences': account_correspondences,
                'account_detail': account_details,
                'customer_id': customer_id,
                'account_type': account_type,
                'account_rp': account_rp
            }

        progress_placeholder_main = st.empty()

        # Main progress bar for years
        main_progress_bar = progress_placeholder_main.progress(0, text="Début du traitement des années. Veuillez patienter.")

        num_years = end_year - start_year + 1

        #transaction_router.card.account_related_cards = Dict[str, pd.DataFrame] = {}
        #transaction_router.account_related_cards = {}

        #transaction_router.clear_cache()

        for year in range(start_year, end_year + 1):

            st.write(f'Traitement des opérations pour l\'année : {year}')
            # 2026-01-09
            transaction_router.clear_cache()
            transaction_router.get_transactions(account, year, start_balance)

            #transaction_router.process_transactions(account)

            st.write('Total accountant ops = ', len(transaction_router.accountant_transactions_with_trx_code))
            st.dataframe(transaction_router.accountant_vs_app_summary)

            # Update the main progress bar
            main_progress_bar.progress((year - start_year + 1) * 100 // num_years, text=f"Année {year} traitée")

            # Convert 'transaction_date' to datetime format (if necessary)
            transaction_router.stacked_df['transaction_date'] = pd.to_datetime(transaction_router.stacked_df['transaction_date'])
            
            # Then sort as usual
            transaction_router.stacked_df = transaction_router.stacked_df.sort_values(by='transaction_date', ascending=False)

            # Construct filename with dynamic year
            file_name = f"{account_number}_{year}.xml"  # f-string for formatted filename
            output_path = f"output/{account_number}"

            print("================================ app - card - xml =======================================")
            print(transaction_router.stacked_df)
            print("=======================================================================")
            
            write_transaction_details_to_xml(transaction_router.stacked_df, output_path, file_name,"zaeazeazeaz","fgfgfgfgfgfgf")

            update_balances(file_name, output_path, start_balance)

            #file_name = f"{account_number}_{year}.xlsx"

            #full_file_path = os.path.join(output_path, file_name)
            
            print(transaction_router.accountant_vs_app_data.columns)
            # Iterate over the rows and save an Excel file for each record
            for index, row in transaction_router.accountant_vs_app_data.iterrows():
                operation_type = row['Operation_Type']  # Get the file name from Operation_Type
                accountant_data_non_matched = row['Accountant_TRX_Non_Matched']  # Get Accountant_Transactions DataFrame
                accountant_data_matched = row['Accountant_TRX_Matched']  # Get Accountant_Transactions DataFrame
                app_data = row['App_TRX']  # Get App_Transactions DataFrame

                print('***********************')
                print(operation_type)
                print(accountant_data_non_matched)
                print(accountant_data_matched)
                print(app_data)
                
                # File name based on Operation_Type
                file_name = f"{account_number}_{operation_type}_{year}.xlsx"
                full_file_path = os.path.join(output_path, file_name)

                
                # Write to an Excel file with two sheets
                with pd.ExcelWriter(full_file_path) as writer:
                    accountant_data_non_matched.to_excel(writer, sheet_name='Accountant_TRX_Non_Matched', index=False)
                    accountant_data_matched.to_excel(writer, sheet_name='Accountant_TRX_Matched', index=False)
                    app_data.to_excel(writer, sheet_name='App_TRX', index=False)

                operation_type = None
                accountant_data_non_matched = None
                accountant_data_matched = None
                app_data = None

            file_name = f"{account_number}_accountant_{year}.xlsx"
            full_file_path = os.path.join(output_path, file_name)

            #pd.merge(
            #    left=transaction_router.accountant[['T24_ACCOUNT', 'TRANSACTION_REF', 'TRANSACTION_SEQ', 'TRANSACTION_DATE', 'TRANSACTION_CODE_ATB', 'TRANSACTION_DESC_ATB', 'APP_SOURCE_CODE', 'TRANSACTION_AMOUNT']],
            #    right=transaction_router.processed_accountant[['T24_ACCOUNT', 'TRANSACTION_REF', 'TRANSACTION_SEQ', 'TRANSACTION_DATE', 'TRANSACTION_CODE_ATB', 'Categorie_de_transaction', 'APP_SOURCE_CODE', 'OP_TYPE']],
            #    on = ['T24_ACCOUNT', 'TRANSACTION_REF', 'TRANSACTION_SEQ', 'TRANSACTION_DATE', 'TRANSACTION_CODE_ATB', 'APP_SOURCE_CODE'],
            #    how='left',
            #    indicator=True
            #).to_excel(full_file_path, sheet_name='accountant', index=False)

            print('=================  transaction_router.accountant_transactions_with_trx_code  ========================')
            print(transaction_router.accountant_transactions_with_trx_code.info())
            print('=========================================')

            print('=================  transaction_router.processed_accountant  ========================')
            print(transaction_router.processed_accountant.info())
            print('=========================================')

            #if not transaction_router.accountant.empty and transaction_router.processed_accountant.empty:
            #print("hello")
            # Perform the merge
            merged_df = pd.DataFrame(columns=['ACCOUNTANT_SOURCE', 'T24_ACCOUNT', 'TRANSACTION_REF', 'TRANSACTION_SEQ', 'TRANSACTION_DATE', 'TRANSACTION_CODE_ATB', 'TRANSACTION_DESC_ATB_ACC', 'APP_SOURCE_CODE', 'TRANSACTION_AMOUNT', 'TRANSACTION_AMOUNT_LCY', 'TRANSACTION_CURRENCY', 'APP_SOURCE', 'OP_TYPE', 'Categorie_de_transaction'])

            if not transaction_router.accountant_transactions_with_trx_code.empty and not transaction_router.processed_accountant.empty:
                merged_df = pd.merge(
                    #left=transaction_router.accountant[['ACCOUNTANT_SOURCE', 'T24_ACCOUNT', 'TRANSACTION_REF', 'TRANSACTION_SEQ', 'TRANSACTION_DATE', 'TRANSACTION_CODE_ATB', 'APP_SOURCE_CODE', 'TRANSACTION_AMOUNT', 'TRANSACTION_AMOUNT_LCY','APP_SOURCE', 'OP_TYPE', 'Categorie_de_transaction']],
                    left=transaction_router.accountant_transactions_with_trx_code[['ACCOUNTANT_SOURCE', 'T24_ACCOUNT', 'TRANSACTION_REF', 'TRANSACTION_SEQ', 'TRANSACTION_DATE', 'TRANSACTION_CODE_ATB', 'TRANSACTION_DESC_ATB_ACC', 'APP_SOURCE_CODE', 'TRANSACTION_AMOUNT', 'TRANSACTION_AMOUNT_LCY', 'TRANSACTION_CURRENCY', 'APP_SOURCE', 'OP_TYPE', 'Categorie_de_transaction', 'IS_INTERFACE', 'IS_MANUELLE']],
                    right=transaction_router.processed_accountant[['ACCOUNTANT_SOURCE', 'T24_ACCOUNT', 'TRANSACTION_REF', 'TRANSACTION_CODE_ATB', 'APP_SOURCE_CODE', 'TRANSACTION_DATE']],
                    on=['ACCOUNTANT_SOURCE', 'T24_ACCOUNT', 'TRANSACTION_REF', 'TRANSACTION_CODE_ATB', 'APP_SOURCE_CODE', 'TRANSACTION_DATE'],#'TRANSACTION_DATE', 
                    how='left',
                    indicator=True
                )
            elif not transaction_router.accountant_transactions_with_trx_code.empty:
                    merged_df = transaction_router.accountant_transactions_with_trx_code[['ACCOUNTANT_SOURCE', 'T24_ACCOUNT', 'TRANSACTION_REF', 'TRANSACTION_SEQ', 'TRANSACTION_DATE', 'TRANSACTION_CODE_ATB', 'TRANSACTION_DESC_ATB_ACC', 'APP_SOURCE_CODE', 'TRANSACTION_AMOUNT', 'TRANSACTION_AMOUNT_LCY', 'TRANSACTION_CURRENCY', 'APP_SOURCE', 'OP_TYPE', 'Categorie_de_transaction', 'IS_INTERFACE', 'IS_MANUELLE']]
                    merged_df['_merge'] = 'left_only'

            if not merged_df.empty:
                # Rename the '_merge' column to 'RRR'
                merged_df.rename(columns={'_merge': 'processing_status'}, inplace=True)
                # Replace values in the 'RRR' column
                merged_df['processing_status'].replace({'left_only': 'not processed', 'both': 'processed'}, inplace=True)
                # Export to Excel
                merged_df.to_excel(full_file_path, sheet_name='accountant', index=False)
                transaction_router.clear_cache()

        # Indicate that processing is complete
        main_progress_bar.progress(100, text="Traitement terminé pour toutes les années")
        st.write("Tous les traitements sont terminés.")
        print('++++ extraction completed ++++')

    else:
        st.write('Veuillez entrer toutes les informations requises !')


            

def main():

    get_client = GetClient(DB_CONFIG)
    transaction_router = TransactionRouter(TREANSACTION_CODE, DB_CONFIG)


    st.write('Declarations Extractor')

    # User input for account number with a fixed length of 13 characters

    account_number = st.text_input(
        "Please enter the account number",
        max_chars=13,
        placeholder="5009000004100",
        key="account_number",
        help="Enter a 13-digit account number."
    )
    try:
        int_value = int(account_number)
        st.success(f"Valid account number: {int_value}")
    except ValueError:
        if account_number:
            st.error("Please enter a valid number")
    

    # Get the current year
    current_year = datetime.now().year

    # Calculate the min and max values for the year range
    min_year = current_year - 20
    max_year = current_year

    # Create columns for side-by-side layout
    col1, col2 = st.columns(2)

    with col1:
        # Start year input
        start_year = st.selectbox(
            "Please enter the start year",
            options=list(range(min_year, max_year + 1)),
            index=0  # Default value is the min_year
        )

        # Starting balance
        start_balance = st.number_input(
            "Please enter the starting balance",
            key="start_balance",
            step=0.001,
            format="%.3f",
            help="Enter the starting balance for the corresponding year"
        )
        try:
            float_value = float(start_balance)
            st.success(f"Valid starting balance: {float_value}")
        except ValueError:
            if start_balance:
                st.error("Please enter a valid starting balance")

    with col2:
        # End year input
        end_year = st.selectbox(
            "Please enter the end year",
            options=list(range(min_year, max_year + 1)),
            index=len(range(min_year, max_year + 1)) - 1  # Default value is the max_year
        )

    # Error messages
    error_messages = []
    
    # Check each condition and append relevant messages
    if len(account_number) != 13:
        error_messages.append("\nThe account number must be exactly 13 digits.")
    
    if start_year > end_year:
        error_messages.append("\nThe start year must be less than or equal to the end year.")
    
    if not start_balance:
        error_messages.append("\nThe starting balance cannot be null")

    # Display error messages if any
    if error_messages:
        st.warning("Please ensure that:\n" + "\n".join(error_messages))
    else:
        # Add a button to trigger the processing
        if st.button('Process Transactions'):
            #st.write(f"Processing transactions from {start_year} to {end_year} for account {account_number} with operations: {op_type}")
            get_transaction(get_client, transaction_router, account_number, start_year, end_year, start_balance)


# Run the main function
main()
