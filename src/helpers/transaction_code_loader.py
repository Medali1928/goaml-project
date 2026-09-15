import pandas as pd


class TransactionCodeLoader:
    @staticmethod
    def load(file_path: str, sheet_name: str) -> pd.DataFrame:
        """
        Loads transaction codes from an Excel file.

        Args:
            file_path (str): Path to the Excel file.
            sheet_name (str): Name of the sheet containing transaction data.

        Returns:
            pd.DataFrame: Processed DataFrame containing transaction codes.
        """
        try:
            # Read Excel file with the specified sheet and columns
            df = pd.read_excel(
                file_path,
                sheet_name=sheet_name,
                engine='openpyxl'
            )
            
            # Format TRANSACTION_CODE_ATB to ensure it's a zero-padded string
            #df['TRANSACTION_CODE_ATB'] = df['TRANSACTION_CODE_ATB'].astype(str).str.zfill(3)

            df['APP_SOURCE_CODE'] = df['APP_SOURCE_CODE'].str.strip()
            df['APP_SOURCE_CODE'] = df['APP_SOURCE_CODE'].str.upper()
            df['TRANSACTION_CODE_ATB'] = df['TRANSACTION_CODE_ATB'].astype(int).astype(str).str.zfill(3)

            # Drop duplicates based on specific columns, keeping the first occurrence
            #df.drop_duplicates(
            #    subset=['ACCOUNTANT_SOURCE', 'APP_SOURCE_CODE', 'TRANSACTION_CODE_ATB'],
            #    keep='first',  # Options: 'first', 'last', False (drops all duplicates)
            #    inplace=True
            #)
            #df = df.dropna(
            #    subset=['ACCOUNTANT_SOURCE', 'APP_SOURCE_CODE', 'TRANSACTION_CODE_ATB']
            #)
            
            return df
        except Exception as e:
            print(f"Error loading transaction codes: {e}")
            raise
