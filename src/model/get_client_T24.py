import pandas as pd
from datetime import datetime
from src.db.connection import DatabaseConnection
from src.db.query_executor import QueryExecutor
from src.helpers.xmlStructure import XML
from src.helpers.utils import clean_dataframe, extract_xml_values, parse_xml_values_by_position, aggregate_legal_id_section
from src.helpers.logger_manager import LoggerManager  # Import the LoggerManager

class GetClientT24(DatabaseConnection):
    def __init__(self, db_config: dict, log_enabled=True):
        super().__init__(db_config['server'], db_config['database'], db_config['username'], db_config['password'])
        self.query_executor = QueryExecutor(self.connection)
        self.xml_generator = XML()
        self.logger_manager = LoggerManager(log_enabled)

    def _log(self, level, message, *args, **kwargs):
        """Log a message if logging is enabled using the logger manager."""
        self.logger_manager.log(level, message, *args, **kwargs)

    def get_client(self, account_number: str) -> tuple:
        """
        Retrieve client details based on the account number. Constructs XML data
        based on the account type and related information.

        Args:
            account (str): The account number to look up.

        Returns:
            tuple: A tuple containing the XML representation of account details, 
                customer ID, account type, and a DataFrame with related persons.
        """
        try:
            if self.account_status_lookup(account_number):
                df_account = self.get_account(account_number)
            else:
                df_account = self.get_account_closed(account_number)
            if df_account.empty:
                raise ValueError(f"No account found with the number: {account_number}")
            
            current_time = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
            df_account['DATE_BALANCE'] = current_time

            account_type = df_account.CUST_TYPE[0]

            if account_type in {'PPH', 'PRO', None}: # 2026-01-12
                handler = self._handle_pph_account
            elif account_type == 'PM':
                handler = self._handle_pm_account
            else:
                handler = self._handle_unknown_account

            return handler(df_account)

        except ValueError as ve:
            self._log('warning', "Value error: %s", ve)
            raise
        except Exception as e:
            self._log('error', "Error retrieving client details for account %s: %s", account_number, e)
            raise RuntimeError(f"Failed to retrieve client details for account {account_number}: {e}")

    def _handle_pph_account(self, df_account: pd.DataFrame) -> tuple:
        
        # fix - AA_ARR_CUSTOMER
        df_arrangement = self.get_arrangement(df_account.ARRANGEMENT_ID[0])

        df_arrangement[["REC_ARRANGEMENT_ID", "REC_DATE", "REC_DATE_IDX"]] = \
        df_arrangement["RECID"].str.extract(r"^(.*?)-CUSTOMER-(\d+)\.(\d+)$")
    
    
        df_arrangement.sort_values(by=["REC_DATE", "REC_DATE_IDX"], ascending=False) \
            .drop_duplicates(subset="ARRANGEMENT_ID", keep="first") \
            .reset_index(drop=True)

        #df_arrangement["RECID_IDX"] = df_arrangement["RECID"].str.rsplit(".", n=1).str[-1].astype(int)
        #df_arrangement = df_arrangement.loc[df_arrangement.groupby("ARRANGEMENT_ID")["RECID_IDX"].idxmax()]
#
        #print("======================")
        #print("======================")
        #print("======================")
        #print(df_arrangement)
        #print(df_arrangement.shape)
        #print("======================")
        #print("======================")
        #print("======================")
        #print(df_arrangement)
        #print("***************************")

        # Apply the parsing logic with position alignment
        result = []
        for _, row in df_arrangement.iterrows():
            arrangement_id = row["ARRANGEMENT_ID"]
            l_acct_type = row["L_ACCT_TYPE"]
            
            # Extract positions and values
            customer_data = parse_xml_values_by_position(row["CUSTOMER_3"])  # Now returns [(position, value), ...]
            role_data = parse_xml_values_by_position(row["CUSTOMER_ROLE_4"])  # Same format
            
            # Convert to dictionaries for easy alignment by position
            customer_dict = {pos: val for pos, val in customer_data}
            role_dict = {pos: val for pos, val in role_data}
            
            # Align by position
            all_positions = sorted(set(customer_dict.keys()).union(role_dict.keys()))
            for pos in all_positions:
                customer_id = customer_dict.get(pos, None)  # Use None if position is missing
                role = role_dict.get(pos, None)
                result.append({"ARRANGEMENT_ID": arrangement_id, "CUSTOMER_ID": customer_id, "CUSTOMER_ROLE": role, "L_ACCT_TYPE": l_acct_type})

        # Create the final DataFrame
        df_arrangement_processed = pd.DataFrame(result)

        print(df_arrangement_processed)

        # Check titulaire + tiers
        if len(df_arrangement_processed) == 1 and df_arrangement_processed['CUSTOMER_ROLE'].iloc[0] in ['OWNER', 'LEGAL.OWNER']:

            print(f"The DataFrame has only one record, and CUSTOMER_ROLE is {df_arrangement_processed['CUSTOMER_ROLE'].iloc[0]}.")
            # T24_CUSTOMER_DECOMPOSED_LEGAL_DETAILS
            df_pph = self.get_PPH(df_arrangement_processed['CUSTOMER_ID'].iloc[0], "CUSTOMER_CODE").assign(ROLE_ACCOUNT='TICPT')
            #pph_xml = "\n".join([self.xml_generator.create_xml_account_related_persons(row) for _, row in df_pph.iterrows()])

            # TO DO : if df_account.loc[0, 'MANDATE_RECORD'] not Null
            # Get mandates
            df_mandates = None
            df_mandates = self.get_account_mandates(df_account.loc[0, 'MANDATE_RECORD'])
            if not df_mandates.empty:
                # Apply the parsing logic with position alignment
                result = []
                for _, row in df_mandates.iterrows():
                    mandate_id = row["MANDATE_ID"]
                    signatory_group = row["SIGNATORY_GROUP"]
                    
                    # Extract positions and values
                    customer_data = parse_xml_values_by_position(row["SIGNATORY_CUSTOMER_2"])
                    start_date_data = parse_xml_values_by_position(row["START_DATE_3"])
                    end_date_data = parse_xml_values_by_position(row["END_DATE_4"])
                    
                    # Convert to dictionaries for easy alignment by position
                    customer_dict = {pos: val for pos, val in customer_data}
                    start_date_dict = {pos: val for pos, val in start_date_data}
                    end_date_dict = {pos: val for pos, val in end_date_data}
                    
                    # Align by position
                    all_positions = sorted(
                        set(customer_dict.keys())
                        .union(start_date_dict.keys())
                        .union(end_date_dict.keys())
                    )

                    for pos in all_positions:
                        customer_id = customer_dict.get(pos, None)  # Use None if position is missing
                        start_date = start_date_dict.get(pos, None)
                        end_date = end_date_dict.get(pos, None)
                        result.append({"MANDATE_ID": mandate_id, "SIGNATORY_GROUP": signatory_group, "CUSTOMER_ID": customer_id, "START_DATE": start_date, "END_DATE": end_date})

                # Create the final DataFrame
                df_mandates_processed = pd.DataFrame(result)
                print('+++++++++ mandates +++++++++')
                print(df_mandates_processed)

                # Convert START_DATE and END_DATE to datetime
                df_mandates_processed['START_DATE'] = pd.to_datetime(df_mandates_processed['START_DATE'], format='%Y%m%d')
                df_mandates_processed['END_DATE'] = pd.to_datetime(df_mandates_processed['END_DATE'], format='%Y%m%d')

                # Get the current date
                current_date = datetime.now()

                # Filter rows
                filtered_df_mandates_processed = df_mandates_processed[(df_mandates_processed['START_DATE'] <= current_date) & (df_mandates_processed['END_DATE'] >= current_date)]
                if not filtered_df_mandates_processed.empty:
                    df_pph = pd.concat([df_pph, self.get_PPH(filtered_df_mandates_processed['CUSTOMER_ID'].iloc[0], "CUSTOMER_CODE").assign(ROLE_ACCOUNT='MAND')], ignore_index=True)
            
            # Identification type Master
            # D     Autre
            # 3SEJ  Carte de séjour 
            # B     CIN
            # C     Passeport
            # A     Permis de conduire 

            # new fix # legal id 
            df_pph = aggregate_legal_id_section(df_pph) 
            # 2026-01-07
            df_pph['ACCOUNT_TYPE'] = 'CST'

            pph_xml = "\n".join([self.xml_generator.create_xml_account_related_persons(row) for _, row in df_pph.iterrows()])
        
            account_xml = "\n".join([self.xml_generator.create_xml_account(row, pph_xml) 
                                    for _, row in df_account.iterrows()])
            account_xml = account_xml.replace('PL_ENTITY', '')

        if len(df_arrangement_processed) > 1 and df_arrangement_processed['CUSTOMER_ROLE'].iloc[0] == 'OWNER' and df_arrangement_processed['CUSTOMER_ROLE'].iloc[1] == 'JOINT.OWNER':
            print(df_arrangement_processed)
            # Mapping - 5.15 Account Person Role Type
            # Titulaire d'un compte joint à double signatures   - TICJD - L_ACCT_TYPE = 1
            # Titulaire d'un compte joint à une seule signature - TICJU - L_ACCT_TYPE = 2
            account_person_role = {
                '1': 'TICJD',
                '2': 'TICJU'
            }

            df_pph = pd.concat(
                [
                    self.get_PPH(row['CUSTOMER_ID'], "CUSTOMER_CODE").assign(ROLE_ACCOUNT=account_person_role[row['L_ACCT_TYPE']]) 
                    for _, row in df_arrangement_processed.iterrows()
                ],
                ignore_index=True
            )

            # new fix
            df_pph = aggregate_legal_id_section(df_pph)
            # 2026-01-07
            df_pph['ACCOUNT_TYPE'] = 'CJ'
            print("==============================")
            print(df_pph)
            pph_xml = "\n".join([self.xml_generator.create_xml_account_related_persons(row) for _, row in df_pph.iterrows()])
        
            account_xml = "\n".join([self.xml_generator.create_xml_account(row, pph_xml) 
                                    for _, row in df_account.iterrows()])
            account_xml = account_xml.replace('PL_ENTITY', '')

        account_correspondences = {
            'T24_ACCOUNT': df_account['T24_ACCOUNT'].iloc[0],
            'EQ_ACCOUNT': df_account['EQ_ACCOUNT'].iloc[0],
            'ORACLE_ACCOUNT': df_account['ORACLE_ACCOUNT'].iloc[0]
        }

        return account_correspondences, account_xml, df_account.CUSTOMER_ID[0], df_account.CUST_TYPE[0], df_pph
    
    def get_arrangement(self, arrangement_id: str) -> pd.DataFrame:
        
        #query = f"""
        #SELECT
        #    RECID AS ARRANGEMENT_ID,
        #    CUSTOMER_1,
        #    CUSTOMER_ROLE_2
        #FROM [MISDW].[GO_AML].[T24_FATB_AA_ARRANGEMENT]
        #WHERE RECID = '{arrangement_id}'
        #"""

        query = f"""
        SELECT
            RECID,
            LEFT(RECID, CHARINDEX('-', RECID) - 1) AS ARRANGEMENT_ID,
            CUSTOMER_3,
            CUSTOMER_ROLE_4,
            L_ACCT_TYPE
        FROM [MISDW].[GO_AML].[T24_FATB_AA_ARR_CUSTOMER]
        WHERE
            LEFT(RECID, CHARINDEX('-', RECID) - 1) = '{arrangement_id}'
        """

        try:
            self.connect()
            # Log the start of the query execution
            self._log('info', "Executing query to retrieve arrangement information for arrangement id : %s", arrangement_id)
            df = self.query_executor.retry_query_execution(query, self.connection, max_attempts=1)

            if not df.empty:
                self._log('info', "Successfully retrieved account information for arrangement id : %s", arrangement_id)
                return clean_dataframe(df.head(1))
            else:
                self._log('warning', "No data found for arrangement id : %s", arrangement_id)

        except Exception as e:
            self._log('error', "Error retrieving account information for arrangement id %s: %s", arrangement_id, e)
            raise RuntimeError(f"Failed to retrieve account information for arrangement id {arrangement_id}: {e}")
        finally:
            self.disconnect()

        return pd.DataFrame()  # Return an empty DataFrame if no data is found
    
    def get_account_mandates(self, acc_mandate_id: str) -> pd.DataFrame:

        query = f"""
        SELECT
            EB_MANDATE.MANDATE_ID,
            EB_MANDATE.SIGNATORY_GROUP,
            SIGNATORY_G.SIGNATORY_CUSTOMER_2,
            SIGNATORY_G.START_DATE_3,
            SIGNATORY_G.END_DATE_4
        FROM [MISDW].[GO_AML].[T24_EB_MANDATE] AS EB_MANDATE
        LEFT JOIN [MISDW].[GO_AML].[T24_EB_SIGNATORY_G001] AS SIGNATORY_G ON SIGNATORY_G.SIG_GROUP_ID = EB_MANDATE.SIGNATORY_GROUP
        WHERE
            EB_MANDATE.MANDATE_ID = '{acc_mandate_id}'
        """

        try:
            self.connect()
            # Log the start of the query execution
            self._log('info', "Executing query to retrieve mandates information for account mandate id : %s", acc_mandate_id)
            df = self.query_executor.retry_query_execution(query, self.connection, max_attempts=1)

            if not df.empty:
                self._log('info', "Successfully retrieved mandates information for account mandate id : %s", acc_mandate_id)
                return clean_dataframe(df.head(1))
            else:
                self._log('warning', "No data found for account mandate id : %s", acc_mandate_id)

        except Exception as e:
            self._log('error', "Error retrieving account information for account mandate id %s: %s", acc_mandate_id, e)
            raise RuntimeError(f"Failed to retrieve account information for account mandate id {acc_mandate_id}: {e}")
        finally:
            self.disconnect()

        return pd.DataFrame()  # Return an empty DataFrame if no data is found
    
    def get_related_third_party(self, customer_id: str) -> pd.DataFrame:

        query = f"""
        SELECT
            RELATION_CUSTOMER.CUSTOMER,
            RELATION_CUSTOMER.OF_CUSTOMER_2,
            RELATION_CUSTOMER.IS_RELATION_1,
            CUSTOMER_ROLE.ROLE_14
        FROM [MISDW].[GO_AML].[T24_FBNK_RELATION_CUSTOMER] AS RELATION_CUSTOMER
        LEFT JOIN [MISDW].[GO_AML].[T24_FBNK_CUSTOMER_ROLE] AS CUSTOMER_ROLE ON RELATION_CUSTOMER.CUSTOMER = CUSTOMER_ROLE.RECID
        WHERE RELATION_CUSTOMER.CUSTOMER = '{customer_id}'
        """

        try:
            self.connect()
            # Log the start of the query execution
            self._log('info', "Executing query to retrieve related third party information for customer id : %s", customer_id)
            df = self.query_executor.retry_query_execution(query, self.connection, max_attempts=1)

            if not df.empty:
                self._log('info', "Successfully retrieved related third party information for customer id : %s", customer_id)
                return clean_dataframe(df.head(1))
            else:
                self._log('warning', "No data found for customer id : %s", customer_id)

        except Exception as e:
            self._log('error', "Error retrieving account information for customer id %s: %s", customer_id, e)
            raise RuntimeError(f"Failed to retrieve account information for customer id {customer_id}: {e}")
        finally:
            self.disconnect()

        return pd.DataFrame()  # Return an empty DataFrame if no data is found
    

    def _handle_pm_account(self, df_account: pd.DataFrame) -> tuple:
        """
        Handle the retrieval of client details for 'PM' type accounts.

        Args:
            df_account (pd.DataFrame): DataFrame containing account information.

        Returns:
            tuple: XML data, customer ID, account type, and DataFrame with related persons.
        """
        df_pm = pd.DataFrame()
        df_related_third_party = pd.DataFrame()
        df_related_third_party_processed = pd.DataFrame()

        #df_pm_related_persons_details = pd.DataFrame()
        # fix - 01-10-2025
        df_pm_related_persons_details = pd.DataFrame(
            columns=[
                'CUSTOMER_ID', 'CUSTOMER_TYPE', 'GENDER', 'FIRST_NAME', 'LAST_NAME',
                'BIRTHDATE', 'BIRTH_PLACE', 'COUNTRY_OF_BIRTH', 'NATIONALITY', 'NATIONALITY_2', 'RESIDENCE', 'ADDRESS_TYPE',
                'ADDRESS', 'TOWN', 'CITY', 'ZIP', 'COUNTRY_CODE', 'OCCUPATION',
                'RELATED_PERSON_RELATION_CODE_ATB', 'RELATED_PERSON_ROLE_CODE_ATB',
                'ROLE_ENTITY', 'ROLE_ACCOUNT', 'IDENTIFICATIONS_ID_SECTION', 'SOURCE'
            ]
        )

        df_pm = self.get_account_related_PM(df_account.CUSTOMER_ID[0])

        df_related_third_party = self.get_related_third_party(df_account.CUSTOMER_ID[0])

        if not df_related_third_party.empty:
            # Apply the parsing logic with position alignment
            result = []
            for _, row in df_related_third_party.iterrows():
                pm_id = row["CUSTOMER"]
                
                # Extract positions and values
                third_party_data = parse_xml_values_by_position(row["OF_CUSTOMER_2"])  # Now returns [(position, value), ...]
                relation_data = parse_xml_values_by_position(row["IS_RELATION_1"])  # Same format
                role_data = parse_xml_values_by_position(row["ROLE_14"])
                
                # Convert to dictionaries for easy alignment by position
                third_party_dict = {pos: val for pos, val in third_party_data}
                relation_dict = {pos: val for pos, val in relation_data}
                role_dict = {pos: val for pos, val in role_data}
                
                # Align by position
                all_positions = sorted(set(third_party_dict.keys()).union(relation_dict.keys(), role_dict.keys()))
                
                for pos in all_positions:
                    third_party = third_party_dict.get(pos, None)  # Use None if position is missing
                    relation = relation_dict.get(pos, None)
                    role = role_dict.get(pos, None)
                    
                    # Append the aligned data into the result list
                    result.append({
                        "PM_ID": pm_id,
                        "RELATED_PERSON_ID": third_party,
                        "RELATED_PERSON_RELATION": relation,
                        "RELATED_PERSON_ROLE": role
                    })
            
            # Create the final DataFrame from the result list
            df_related_third_party_processed = pd.DataFrame(result)
            print('********************************')
            print("df_related_third_party_processed")
            print(df_related_third_party_processed)
            print('********************************')
            df_pm_related_persons_details = self.get_PM_related_persons_l2(df_related_third_party_processed)
            if not df_pm_related_persons_details.empty:
                # Remove signaotries
                df_pm_related_persons_details = df_pm_related_persons_details[~df_pm_related_persons_details['RELATED_PERSON_RELATION_CODE_ATB'].isin(['201', '601', '309'])] # Mandataire, Mandant, Signataire
                df_pm_related_persons_details['ROLE_ACCOUNT'] = 'MAND'
                print("phase 1")
                print(df_pm_related_persons_details)
                df_pm_related_persons_details["SOURCE"] = "TIER"

        # Get mandates
        df_mandates = pd.DataFrame()
        df_mandates_processed = pd.DataFrame()

        df_mandates = self.get_account_mandates(df_account.loc[0, 'MANDATE_RECORD'])

        if not df_mandates.empty:
            # Apply the parsing logic with position alignment
            result = []
            for _, row in df_mandates.iterrows():
                mandate_id = row["MANDATE_ID"]
                signatory_group = row["SIGNATORY_GROUP"]
                    
                # Extract positions and values
                customer_data = parse_xml_values_by_position(row["SIGNATORY_CUSTOMER_2"])
                start_date_data = parse_xml_values_by_position(row["START_DATE_3"])
                end_date_data = parse_xml_values_by_position(row["END_DATE_4"])
                    
                # Convert to dictionaries for easy alignment by position
                customer_dict = {pos: val for pos, val in customer_data}
                start_date_dict = {pos: val for pos, val in start_date_data}
                end_date_dict = {pos: val for pos, val in end_date_data}
                    
                # Align by position
                all_positions = sorted(
                    set(customer_dict.keys())
                    .union(start_date_dict.keys())
                    .union(end_date_dict.keys())
                )

                for pos in all_positions:
                    customer_id = customer_dict.get(pos, None)  # Use None if position is missing
                    start_date = start_date_dict.get(pos, None)
                    end_date = end_date_dict.get(pos, None)
                    result.append({"MANDATE_ID": mandate_id, "SIGNATORY_GROUP": signatory_group, "CUSTOMER_ID": customer_id, "START_DATE": start_date, "END_DATE": end_date})

            # Create the final DataFrame
            df_mandates_processed = pd.DataFrame(result)

            # Convert START_DATE and END_DATE to datetime
            df_mandates_processed['START_DATE'] = pd.to_datetime(df_mandates_processed['START_DATE'], format='%Y%m%d')
            df_mandates_processed['END_DATE'] = pd.to_datetime(df_mandates_processed['END_DATE'], format='%Y%m%d')

            # Get the current date
            current_date = datetime.now()

            # Filter rows
            filtered_df_mandates_processed = df_mandates_processed[(df_mandates_processed['START_DATE'] <= current_date) & (df_mandates_processed['END_DATE'] >= current_date)]
            print('************ filtered_df_mandates_processed ****************')
            print(filtered_df_mandates_processed)
            
            if not filtered_df_mandates_processed.empty:
                df_related_third_party_signatory_g = self.get_PPH(filtered_df_mandates_processed['CUSTOMER_ID'].iloc[0], "CUSTOMER_CODE").assign(RELATED_PERSON_ROLE_CODE_ATB='SIGNATAIRE', ROLE_ENTITY='RL')
                print("phase 2")
                print(df_related_third_party_signatory_g)
                # Concatenate
                print("phase 3")
                print("df_related_third_party_signatory_g.columns")
                print(df_related_third_party_signatory_g.columns)
                df_related_third_party_signatory_g["SOURCE"] = "SIG"
                print("df_pm_related_persons_details.columns")
                print(df_pm_related_persons_details.columns)
                df_pm_related_persons_details = pd.concat([df_pm_related_persons_details, df_related_third_party_signatory_g], ignore_index=True)
                print("phase 4 - concat")
                print("df_pm_related_persons_details.columns")
                print(df_pm_related_persons_details.columns)
                print(df_pm_related_persons_details)

        print('********************************')
        print("BEFORE - df_pm_related_persons_details")
        print(df_pm_related_persons_details.shape)
        print(df_pm_related_persons_details)
        print('********************************')

        # 2026-01-07
        df_pm_related_persons_details['ACCOUNT_TYPE'] = 'CPM'

        if not df_pm_related_persons_details.empty:
            df_pm_related_persons_details = aggregate_legal_id_section(df_pm_related_persons_details)
            df_pm_related_persons_details['ROLE_ACCOUNT'] = 'MAND'
            print('********************************')
            print("AFTER - df_pm_related_persons_details")
            print(df_pm_related_persons_details.shape)
            print(df_pm_related_persons_details)
            print('********************************')

            #xml_pm_related_persons = "\n".join(
            #    df_pm_related_persons_details.apply(self.xml_generator.create_xml_entity_related_person, axis=1))
            print("======== 123 ========")
            print(df_pm_related_persons_details.columns)
            print(df_pm_related_persons_details.head(1))
            # 27/10/2025
            xml_pm_related_persons = "\n".join([
                self.xml_generator.create_xml_entity_related_person(
                    row,
                    comments=f"CUSTOMER_ID = {row.CUSTOMER_ID}, "
                            f"RELATED_PERSON_RELATION_CODE_ATB = {row.RELATED_PERSON_RELATION_CODE_ATB}, "
                            f"RELATED_PERSON_ROLE_CODE_ATB = {row.RELATED_PERSON_ROLE_CODE_ATB}, "
                            f"ROLE_ENTITY = {row.ROLE_ENTITY}, ROLE_ACCOUNT = {row.ROLE_ACCOUNT}"
                )
                for _, row in df_pm_related_persons_details.iterrows()
            ])
        else:
            xml_pm_related_persons = 'PM has no related persons'
        
        xml_pm = self.xml_generator.create_xml_entity(df_pm.iloc[0], xml_pm_related_persons)

        #xml_pph = "\n".join([self.xml_generator.create_xml_account_related_persons(row) 
        #                     for _, row in df_pm_related_persons_details.iterrows()])

        xml_pph = "\n".join([
            self.xml_generator.create_xml_account_related_persons(
                row,
                comments=f"CUSTOMER_ID = {row.CUSTOMER_ID}, "
                        f"RELATED_PERSON_RELATION_CODE_ATB = {row.RELATED_PERSON_RELATION_CODE_ATB}, "
                        f"RELATED_PERSON_ROLE_CODE_ATB = {row.RELATED_PERSON_ROLE_CODE_ATB}, "
                        f"ROLE_ENTITY = {row.ROLE_ENTITY}, ROLE_ACCOUNT = {row.ROLE_ACCOUNT}"
            )
            for _, row in df_pm_related_persons_details.iterrows()
        ])



        xml_account = "\n".join([self.xml_generator.create_xml_account(row, xml_pph) 
                                 for _, row in df_account.iterrows()])
        xml_account = xml_account.replace('PL_ENTITY', xml_pm.replace('IB_', 't_'))

        account_correspondences = {
            'T24_ACCOUNT': df_account['T24_ACCOUNT'].iloc[0],
            'EQ_ACCOUNT': df_account['EQ_ACCOUNT'].iloc[0],
            'ORACLE_ACCOUNT': df_account['ORACLE_ACCOUNT'].iloc[0]
        }

        return account_correspondences, xml_account, df_account.CUSTOMER_ID[0], df_account.CUST_TYPE[0], df_pm_related_persons_details
    
        

#Index(['CUSTOMER_TYPE', 'CUSTOMER_ID', 'GENDER', 'FIRST_NAME', 'LAST_NAME',
#       'BIRTHDATE', 'BIRTH_PLACE', 'NATIONALITY', 'RESIDENCE', 'ADDRESS_TYPE',
#       'ADDRESS', 'TOWN', 'CITY', 'ZIP', 'COUNTRY_CODE', 'OCCUPATION',
#       'RELATED_PERSON_ROLE_CODE_ATB', 'ROLE_ENTITY',
#       'IDENTIFICATIONS_ID_SECTION', 'ROLE_ACCOUNT'],
#      dtype='object')
#
#
#RELATED_PERSON_RELATION_CODE_ATB
#
#======== 123 ========
#Index(['CUSTOMER_ID', 'CUSTOMER_TYPE', 'GENDER', 'FIRST_NAME', 'LAST_NAME',
#       'BIRTHDATE', 'BIRTH_PLACE', 'NATIONALITY', 'RESIDENCE', 'ADDRESS_TYPE',
#       'ADDRESS', 'TOWN', 'CITY', 'ZIP', 'COUNTRY_CODE', 'OCCUPATION',
#       'RELATED_PERSON_RELATION_CODE_ATB', 'RELATED_PERSON_ROLE_CODE_ATB',
#       'ROLE_ENTITY', 'ROLE_ACCOUNT', 'IDENTIFICATIONS_ID_SECTION'],
#      dtype='object')
#
#
#
#
#        #df_pm_related_persons_details = pd.DataFrame(
#        #    columns=[
#        #        'CUSTOMER_ID', 'CUSTOMER_TYPE', 'GENDER', 'FIRST_NAME', 'LAST_NAME',
#        #        'BIRTHDATE', 'BIRTH_PLACE', 'NATIONALITY', 'RESIDENCE', 'ADDRESS_TYPE',
#        #        'ADDRESS', 'TOWN', 'CITY', 'ZIP', 'COUNTRY_CODE', 'OCCUPATION',
#        #        'RELATED_PERSON_RELATION_CODE_ATB', 'RELATED_PERSON_ROLE_CODE_ATB',
#        #        'ROLE_ENTITY', 'ROLE_ACCOUNT', 'IDENTIFICATIONS_ID_SECTION'
#        #    ]
#        #)

        """
        df_pm_related_persons_id = self.get_PM_related_persons_l1(df_account.CUSTOMER_ID[0])
        df_pm_related_persons_details = self.get_PM_related_persons_l2(df_pm_related_persons_id)

        xml_pm_related_persons = "\n".join(
            df_pm_related_persons_details.apply(self.xml_generator.create_xml_entity_related_person, axis=1))
        xml_pm = self.xml_generator.create_xml_entity(df_pm.iloc[0], xml_pm_related_persons)

        xml_pph = "\n".join([self.xml_generator.create_xml_account_related_persons(row) 
                             for _, row in df_pm_related_persons_details.iterrows()])
        xml_account = "\n".join([self.xml_generator.create_xml_account(row, xml_pph) 
                                 for _, row in df_account.iterrows()])
        xml_account = xml_account.replace('PL_ENTITY', xml_pm.replace('IB_', 't_'))

        account_correspondences = {
            'T24_ACCOUNT': df_account['T24_ACCOUNT'].iloc[0],
            'EQ_ACCOUNT': df_account['EQ_ACCOUNT'].iloc[0],
            'ORACLE_ACCOUNT': df_account['ORACLE_ACCOUNT'].iloc[0]
        }

        return account_correspondences, xml_account, df_account.CUSTOMER_ID[0], df_account.CUST_TYPE[0], df_pm_related_persons_details
        """

    def _handle_unknown_account(self, df_account: pd.DataFrame):
        """
        Handle unknown account types.
        """
        account_type = df_account.CUST_TYPE[0]
        self._log('warning', "Unknown Account Class: %s", account_type)
        raise ValueError(f"Unsupported account type: {account_type}")
    
    def account_status_lookup(self, account_number):

        query = f"""
        SELECT
            CASE 
                WHEN COUNT(*) > 0 THEN 'IS_CLOSED'
                WHEN COUNT(*) = 0 THEN 'IS_ACTIVE'
            END AS STATUS
        FROM [MISDW].[TRG].[T24_FATB_ACCOUNT_CLOSED] AS T24_ACCOUNT_CLOSED
        LEFT JOIN [MISDW].[TRG].[T24_FATB_ALTERNATE_ACCO000] AS ALTERNATE_ACCOUNT ON T24_ACCOUNT_CLOSED.ACCOUNT_NO = ALTERNATE_ACCOUNT.GLOBUS_ACCT_NUMBER
        WHERE ALTERNATE_ACCOUNT.ALTERNATIVE_NUMBER = '{account_number}'
        """

        try:
            self.connect()
            self._log('info', "Executing account status lookup for account: %s", account_number)

            df = self.query_executor.retry_query_execution(query, self.connection, max_attempts=1)

            if not df.empty:
                status = df.iloc[0]['STATUS']
                is_active = status == 'IS_ACTIVE'
                self._log('info', "Account %s is %s", account_number, status)
                return is_active

            self._log('warning', "No data found for account number: %s", account_number)
        
        except Exception as e:
            self._log('error', "Error retrieving account information for account number %s: %s", account_number, e)
            raise RuntimeError(f"Failed to retrieve account information for account number {account_number}: {e}")
        
        finally:
            self.disconnect()

        return False  # Default to False if no data is found or an error occurs
    
    def get_account(self, account_number: str) -> pd.DataFrame:
        """
        Retrieve account information from the database using the given account number.

        Args:
            account_number (str): The account number to look up.

        Returns:
            pd.DataFrame: DataFrame containing account details.
        """
        query = f"""
                SELECT
					T24_ACCOUNT.ACCOUNT_NUMBER AS T24_ACCOUNT,
                    ALTERNATE_ACCOUNT.ALTERNATIVE_NUMBER AS EQ_ACCOUNT,
					EQ_ORACLE.NEEAN AS ORACLE_ACCOUNT,
                    T24_ACCOUNT.ARRANGEMENT_ID AS ARRANGEMENT_ID,
                    T24_ACCOUNT.MANDATE_RECORD,
                    T24_CUSTOMER.L_NATURE_CLIENT AS CUST_TYPE,
                    T24_CUSTOMER.CUSTOMER_NO AS CUSTOMER_ID,
                    T24_ACCOUNT.ALT_ACCT_ID AS RIB,
                    CASE
                        WHEN T24_ACCOUNT.CURRENCY = 'TDC' THEN 'TND'
                        ELSE T24_ACCOUNT.CURRENCY
                    END AS CURRENCY_DESC,
                    --T24_ACCOUNT.CURRENCY AS CURRENCY_DESC,
                    --T24_ACCOUNT.SHORT_TITLE AS ACCOUNT_NAME,
					'T24 - ' + T24_CUSTOMER.NAME_1 AS ACCOUNT_NAME,
                    T24_ACCOUNT.CATEGORY AS ACOUNT_TYPE_CODE_ATB,
                    ACCOUNT_TYPE.Description_ATB AS ACOUNT_TYPE_DESC_ATB,
                    ACCOUNT_TYPE.ACCOUNT_TYPE_goAML AS ACOUNT_TYPE_CODE_goAML,
                    --EQ_ACCOUNT.EQA_BALANCE_CCY AS BALANCE,
                    T24_ACCOUNT.WORKING_BALANCE AS BALANCE,
                    T24_ACCOUNT.OPENING_DATE,
                    CASE
                        --WHEN T24_ACCOUNT.OPENING_DATE = 0 THEN '0000-00-00T00:00:00'
                        WHEN ISDATE(CONVERT(VARCHAR, TRY_CONVERT(INT, T24_ACCOUNT.OPENING_DATE))) = 1 THEN
                            CONVERT(VARCHAR, CONVERT(DATE, CONVERT(VARCHAR, TRY_CONVERT(INT, T24_ACCOUNT.OPENING_DATE))), 23) + 'T00:00:00'
                        ELSE NULL
                    END AS OPENING_DATE_FORMATTED,
                    NULL AS ACCT_CLOSE_DATE,
                    NULL AS CLOSED_DATE_FORMATTED,
                    'A' AS STATUS,
                    'T24' AS SOURCE
                FROM [MISDW].[TRG].[T24_FATB_ACCOUNT] AS T24_ACCOUNT
                LEFT JOIN [MISDW].[TRG].[T24_FBNK_CUSTOMER] AS T24_CUSTOMER ON T24_CUSTOMER.CUSTOMER_CODE = T24_ACCOUNT.CUSTOMER_NO
                LEFT JOIN [MISDW].[TRG].[T24_FATB_ALTERNATE_ACCO000] AS ALTERNATE_ACCOUNT ON T24_ACCOUNT.ACCOUNT_NUMBER = ALTERNATE_ACCOUNT.GLOBUS_ACCT_NUMBER
				LEFT JOIN [MISDW].[TRG].[EQA_ACC_EXTERNAL_ACCOUNT_NUMBER] AS EQ_ORACLE ON EQ_ORACLE.NEAB + EQ_ORACLE.NEAN + EQ_ORACLE.NEAS = ALTERNATIVE_NUMBER
				LEFT JOIN [MISDW].[GO_AML].[EQA_ACCOUNT_DAILY] AS EQ_ACCOUNT ON EQ_ACCOUNT.BRN_ACC + EQ_ACCOUNT.BN + EQ_ACCOUNT.SFX_ACC = ALTERNATE_ACCOUNT.ALTERNATIVE_NUMBER
                LEFT JOIN [MISDW].[GO_AML].[ACCOUNT_TYPE_EQ_T24] ON ACCOUNT_TYPE_EQ_T24.ACCOUNT_TYPE_T24 = T24_ACCOUNT.CATEGORY
                LEFT JOIN [MISDW].[GO_AML].[ACCOUNT_TYPE] ON ACCOUNT_TYPE.ACCOUNT_TYPE_ATB = ACCOUNT_TYPE_EQ_T24.ACCOUNT_TYPE_EQ
				WHERE
                    LEFT(ALTERNATE_ACCOUNT.ALTERNATIVE_NUMBER, 1) IN ('5', '6')
					AND CAST(LEFT(ALTERNATE_ACCOUNT.ALTERNATIVE_NUMBER, 3) AS INT) BETWEEN 500 AND 599
					AND ALTERNATE_ACCOUNT.ALTERNATIVE_NUMBER = '{account_number}'
            """

        try:
            self.connect()
            # Log the start of the query execution
            self._log('info', "Executing query to retrieve account information for account number: %s", account_number)
            df = self.query_executor.retry_query_execution(query, self.connection, max_attempts=1)

            if not df.empty:
                self._log('info', "Successfully retrieved account information for account number: %s", account_number)
                return clean_dataframe(df.head(1))
            else:
                self._log('warning', "No data found for account number: %s", account_number)

        except Exception as e:
            self._log('error', "Error retrieving account information for account number %s: %s", account_number, e)
            raise RuntimeError(f"Failed to retrieve account information for account number {account_number}: {e}")
        finally:
            self.disconnect()

        return pd.DataFrame()  # Return an empty DataFrame if no data is found
    

    def get_account_closed(self, account_number: str) -> pd.DataFrame:

        query = f"""
        SELECT TOP 1
            T24_ACCOUNT_CLOSED.ACCOUNT_NO AS T24_ACCOUNT,
            ALTERNATE_ACCOUNT.ALTERNATIVE_NUMBER AS EQ_ACCOUNT,
            EQ_ORACLE.NEEAN AS ORACLE_ACCOUNT,
            ACCOUNT_HIS.ARRANGEMENT_ID AS ARRANGEMENT_ID,
            ACCOUNT_HIS.MANDATE_RECORD AS MANDATE_RECORD,
            T24_CUSTOMER.L_NATURE_CLIENT AS CUST_TYPE,
            T24_CUSTOMER.CUSTOMER_NO AS CUSTOMER_ID,
            ACCOUNT_HIS.ALT_ACCT_ID AS RIB,
            CASE
                WHEN ACCOUNT_HIS.CURRENCY = 'TDC' THEN 'TND'
                ELSE ACCOUNT_HIS.CURRENCY
            END AS CURRENCY_DESC,
            'T24 - ' + T24_CUSTOMER.NAME_1 AS ACCOUNT_NAME,
            ACCOUNT_HIS.CATEGORY AS ACOUNT_TYPE_CODE_ATB,
            ACCOUNT_TYPE.Description_ATB AS ACOUNT_TYPE_DESC_ATB,
            ACCOUNT_TYPE.ACCOUNT_TYPE_goAML AS ACOUNT_TYPE_CODE_goAML,
            EQ_ACCOUNT.EQA_BALANCE_CCY AS BALANCE,
            CASE
                --WHEN ACCOUNT_HIS.OPENING_DATE = 0 THEN '0000-00-00T00:00:00'
                WHEN ISDATE(CONVERT(VARCHAR, TRY_CONVERT(INT, ACCOUNT_HIS.OPENING_DATE))) = 1 THEN CONVERT(VARCHAR, CONVERT(DATE, CONVERT(VARCHAR, TRY_CONVERT(INT, ACCOUNT_HIS.OPENING_DATE))), 23) + 'T00:00:00'
                ELSE NULL
            END AS OPENING_DATE_FORMATTED,
            CASE
                --WHEN T24_ACCOUNT_CLOSED.ACCT_CLOSE_DATE = 0 THEN '0000-00-00T00:00:00'
                WHEN ISDATE(CONVERT(VARCHAR, TRY_CONVERT(INT, T24_ACCOUNT_CLOSED.ACCT_CLOSE_DATE))) = 1 THEN CONVERT(VARCHAR, CONVERT(DATE, CONVERT(VARCHAR, TRY_CONVERT(INT, T24_ACCOUNT_CLOSED.ACCT_CLOSE_DATE))), 23) + 'T00:00:00'
                ELSE NULL
            END AS CLOSED_DATE_FORMATTED,
            'CLOT' AS STATUS
        FROM [MISDW].[TRG].[T24_FATB_ACCOUNT_CLOSED] AS T24_ACCOUNT_CLOSED
        LEFT JOIN [MISDW].[TRG].[T24_FATB_ACCOUNT#HIS] AS ACCOUNT_HIS ON LEFT(ACCOUNT_HIS.ACCOUNT_NUMBER, CHARINDEX(';', ACCOUNT_HIS.ACCOUNT_NUMBER + ';') - 1) = T24_ACCOUNT_CLOSED.ACCOUNT_NO
        LEFT JOIN [MISDW].[TRG].[T24_FATB_ALTERNATE_ACCO000] AS ALTERNATE_ACCOUNT ON T24_ACCOUNT_CLOSED.ACCOUNT_NO = ALTERNATE_ACCOUNT.GLOBUS_ACCT_NUMBER
        LEFT JOIN [MISDW].[TRG].[EQA_ACC_EXTERNAL_ACCOUNT_NUMBER] AS EQ_ORACLE ON EQ_ORACLE.NEAB + EQ_ORACLE.NEAN + EQ_ORACLE.NEAS = ALTERNATE_ACCOUNT.ALTERNATIVE_NUMBER
        LEFT JOIN [MISDW].[GO_AML].[EQA_ACCOUNT_DAILY] AS EQ_ACCOUNT ON EQ_ACCOUNT.BRN_ACC + EQ_ACCOUNT.BN + EQ_ACCOUNT.SFX_ACC = ALTERNATE_ACCOUNT.ALTERNATIVE_NUMBER
        LEFT JOIN [MISDW].[TRG].[T24_FBNK_CUSTOMER] AS T24_CUSTOMER ON T24_CUSTOMER.CUSTOMER_CODE = T24_ACCOUNT_CLOSED.CUSTOMER_ID
        LEFT JOIN [MISDW].[GO_AML].[ACCOUNT_TYPE_EQ_T24] ON ACCOUNT_TYPE_EQ_T24.ACCOUNT_TYPE_T24 = ACCOUNT_HIS.CATEGORY
        LEFT JOIN [MISDW].[GO_AML].[ACCOUNT_TYPE] ON ACCOUNT_TYPE.ACCOUNT_TYPE_ATB = ACCOUNT_TYPE_EQ_T24.ACCOUNT_TYPE_EQ
        WHERE
            ALTERNATE_ACCOUNT.ALTERNATIVE_NUMBER = '{account_number}'
            AND ACCOUNT_HIS.CLOSURE_DATE IS NOT NULL
        ORDER BY HISTORY_NUMBER DESC;
        """

        try:
            self.connect()
            # Log the start of the query execution
            self._log('info', "Executing query to retrieve account information for account number: %s", account_number)
            df = self.query_executor.retry_query_execution(query, self.connection, max_attempts=1)

            if not df.empty:
                self._log('info', "Successfully retrieved account information for account number: %s", account_number)
                return clean_dataframe(df.head(1))
            else:
                self._log('warning', "No data found for account number: %s", account_number)

        except Exception as e:
            self._log('error', "Error retrieving account information for account number %s: %s", account_number, e)
            raise RuntimeError(f"Failed to retrieve account information for account number {account_number}: {e}")
        finally:
            self.disconnect()

        return pd.DataFrame()  # Return an empty DataFrame if no data is found
   
    def is_joint_account(self, arrangement_id: str) -> pd.DataFrame:
        """
        Determine if an account is a joint account and retrieve related customer details.

        Args:
            arrangement_id (str): The unique identifier for the arrangement.

        Returns:
            pd.DataFrame: DataFrame containing joint account status and related customer details.
        """
        try:
            self.connect()
            # Log the start of the query execution
            self._log('info', "Executing query to determine joint account status for arrangement ID: %s", arrangement_id)

            query = f"""
                SELECT
                    CASE
                        WHEN ARRANGEMENT.CUSTOMER_ROLE_2 IS NOT NULL AND ARRANGEMENT.CUSTOMER_ROLE_2 <> '' AND ARRANGEMENT.CUSTOMER_ROLE_2 = '<c2>OWNER</c2>' THEN 'NO'
                        ELSE 'YES'
                    END AS IS_JOINT_ACCOUNT,
                    ARRANGEMENT.CUSTOMER_1 AS RELATED_PERSONS,
                    ARRANGEMENT.CUSTOMER_ROLE_2 AS RELATED_PERSONS_ROLE
                FROM [MISDW].[GO_AML].[T24_FATB_AA_ARRANGEMENT] AS ARRANGEMENT
                WHERE RECID = '{arrangement_id}'
            """

            df = self.query_executor.retry_query_execution(query, self.connection)

            if not df.empty:
                self._log('info', "Successfully retrieved joint account status for arrangement ID: %s", arrangement_id)
                return clean_dataframe(df)
            else:
                self._log('warning', "No data found for arrangement ID: %s", arrangement_id)

        except Exception as e:
            self._log('error', "Error while checking joint account status for arrangement ID %s: %s", arrangement_id, e)
            # Reraise the exception after logging it
            raise RuntimeError(f"Failed to retrieve joint account information for arrangement ID {arrangement_id}: {e}")
        
        finally:
            self.disconnect()

        # Return an empty DataFrame only after handling all exceptions
        return pd.DataFrame()  # Return empty DataFrame if no data is found

    #def get_account_related_PPH(self, df: pd.DataFrame) -> pd.DataFrame:
    #    """
    #    Get related PPH customer details based on account information.
#
    #    Args:
    #        df (pd.DataFrame): DataFrame containing account information with related persons.
#
    #    Returns:
    #        pd.DataFrame: DataFrame with PPH-related customer details.
    #    """
    #    try:
    #        # Log the start of the process
    #        self._log('info', "Starting to get account-related PPH for account with related persons details.")
#
    #        # Extract related customer IDs and roles
    #        related_cust_id = extract_xml_values(df.at[0, 'RELATED_PERSONS'])
    #        related_cust_role = extract_xml_values(df.at[0, 'RELATED_PERSONS_ROLE'])
#
    #        # Log the extracted values
    #        self._log('info', "Extracted related customer IDs and roles: %s, %s", related_cust_id, related_cust_role)
#
    #        # Create a DataFrame with unique related persons and roles
    #        df_l1 = pd.DataFrame({
    #            'RELATED_PERSONS_ID': related_cust_id,
    #            'RELATED_PERSONS_ROLE': related_cust_role
    #        }).drop_duplicates()
#
    #        # Log the DataFrame structure
    #        self._log('info', "Created DataFrame with unique related persons and roles: %s", df_l1.head())
#
    #        # If not a joint account, return PPH for the first related person
    #        if df.at[0, 'IS_JOINT_ACCOUNT'] != 'YES':
    #            self._log('info', "The account is not a joint account. Retrieving PPH for the first related person.")
    #            return self.get_PPH(df_l1.iloc[0]['RELATED_PERSONS_ID'], "CUSTOMER_CODE").assign(ROLE_ACCOUNT='TICPT') 
#
    #        # For joint accounts, aggregate PPH for all related persons
    #        """
    #        self._log('info', "The account is a joint account. Aggregating PPH for all related persons.")
    #        df_PPH = pd.concat(
    #            [self.get_PPH(row['RELATED_PERSONS_ID']) for _, row in df_l1.iterrows()],
    #            ignore_index=True
    #        )
    #        """
    #        #"""
    #        df_PPH = pd.concat(
    #            [
    #                self.get_PPH(row['RELATED_PERSONS_ID'], "CUSTOMER_CODE").assign(ROLE_ACCOUNT='TICJU') 
    #                for _, row in df_l1.iterrows()
    #            ],
    #            ignore_index=True
    #        )
    #        #"""
    #        self._log('info', "Aggregated PPH DataFrame created for joint account.")
#
    #        return df_PPH
#
    #    except Exception as e:
    #        # Log any exceptions that occur during execution
    #        self._log('error', "Error while getting account-related PPH for account with ID %s: %s", df.at[0, 'RELATED_PERSONS'], e)
    #        raise RuntimeError(f"Failed to retrieve account-related PPH: {e}")
    
    def get_PPH(self, customer_id: str, filter_by: str) -> pd.DataFrame:
        """
        Retrieve detailed PPH customer data from the database using the customer ID.

        Args:
            customer_id (str): The unique identifier for the customer.

        Returns:
            pd.DataFrame: DataFrame containing PPH customer details.
        """
        if filter_by not in ("CUSTOMER_CODE", "LEGAL_ID"):
            raise ValueError("filter_by must be either 'CUSTOMER_CODE' or 'LEGAL_ID'")
        try:
            self._log('info', "Starting to retrieve PPH data for customer ID %s", customer_id)

            self.connect()
            
            query = f"""
            -- T24 - CUSTOMERS - PPH
            SELECT
                L_NATURE_CLIENT AS CUSTOMER_TYPE,
                --CUSTOMER_NO AS CUSTOMER_ID,
                CUSTOMER_CODE AS CUSTOMER_ID,
                CASE
                    WHEN GENDER IS NULL OR GENDER = '' THEN 'N.A'
                    WHEN GENDER = 'MALE' THEN 'M'
                    WHEN GENDER = 'FEMALE' THEN 'F'
                END AS GENDER,
                GIVEN_NAMES AS FIRST_NAME,
                FAMILY_NAME AS LAST_NAME,
                CASE
                        WHEN ISDATE(CONVERT(VARCHAR, TRY_CONVERT(INT, DATE_OF_BIRTH))) = 1 THEN CONVERT(VARCHAR, CONVERT(DATE, CONVERT(VARCHAR, TRY_CONVERT(INT, DATE_OF_BIRTH))), 23) + 'T00:00:00'
                        ELSE 'N.A'
                    END AS BIRTHDATE,
                CASE  
				    WHEN COALESCE(L_PLACE_OF_BIRT, '') = '' THEN 'N.A'  
				    ELSE NULLIF(L_PLACE_OF_BIRT, '')
				END AS BIRTH_PLACE,
                CUST_BIRTH_COUNTRY AS COUNTRY_OF_BIRTH,
                LEGAL_DOC_NAME,
                LEGAL_ID, --Numéro de la carte d’identité nationale CIN / Numéro passeport
                LEGAL_ISS_AUTH, --Pays d'émission du passeport
                CONVERT(NVARCHAR, CONVERT(DATE, LEGAL_ISS_DATE, 112), 120) + 'T00:00:00' AS LEGAL_ISS_DATE,
                CONVERT(NVARCHAR, CONVERT(DATE, LEGAL_EXP_DATE, 112), 120) + 'T00:00:00' AS LEGAL_EXP_DATE,
                NATIONALITY,
                OTHER_NATIONILITY AS NATIONALITY_2,
                RESIDENCE,
                '1' AS ADDRESS_TYPE,
                COALESCE(NULLIF(STREET, ''), 'N.A') AS ADDRESS,
                COALESCE(NULLIF(ADDRESS_ITEM1, ''), 'N.A') AS TOWN,
                COALESCE(NULLIF(ADDRESS, ''), 'N.A') AS CITY,
                COALESCE(NULLIF(POST_CODE, ''), 'N.A') AS ZIP,
                --CASE
				--    WHEN COALESCE(COUNTRY, '') = '' 
				--         AND COALESCE(TOWN_COUNTRY, '') = '' 
				--         AND COALESCE(ADDRESS_ITEM1, '') = '' 
				--         AND COALESCE(ADDRESS_ITEM2, '') = '' 
				--         AND COALESCE(STREET, '') = ''  
				--         AND COALESCE(ADDRESS, '') = ''
				--        THEN 'N.A'
				--    ELSE CONCAT_WS(' - ',
				--         NULLIF(COUNTRY, ''),
				--         NULLIF(TOWN_COUNTRY, ''),
				--         NULLIF(ADDRESS_ITEM1, ''),
				--         NULLIF(ADDRESS_ITEM2, ''),
				--         NULLIF(STREET, ''),
				--         NULLIF(ADDRESS, ''))
				--END AS ADDRESS,
                COALESCE(NULLIF(COUNTRY, ''), 'N.A') AS COUNTRY_CODE,
                COALESCE(NULLIF(T24_OCCUPATION.LIBELLE, ''), 'N.A') AS OCCUPATION
                --'TICPT' AS ROLE_ACCOUNT
            --FROM [MISDW].[TRG].[T24_FBNK_CUSTOMER]
            FROM [MISDW].[GO_AML].[T24_CUSTOMER_DECOMPOSED_LEGAL_DETAILS]
            LEFT JOIN [MISDW].[GO_AML].[T24_OCCUPATION] AS T24_OCCUPATION ON RIGHT('0000' + T24_OCCUPATION.CODE, 4) = RIGHT('0000' + OCCUPATION, 4)
            WHERE
                {filter_by} = '{customer_id}'
            """

            # Log the query being executed (optional: be cautious with sensitive data)
            self._log('debug', "Executing query to retrieve PPH data: %s", query)

            # Using retry mechanism with self.query_executor
            df = self.query_executor.retry_query_execution(query, self.connection, max_attempts=1)

            if not df.empty:
                self._log('info', "Retrieved PPH data successfully for customer ID %s", customer_id)
                return clean_dataframe(df)
            
            # Log a warning if the DataFrame is empty
            self._log('warning', "No PPH data found for customer ID %s", customer_id)

        except Exception as e:
            # Log any exceptions that occur during execution
            self._log('error', "Error while retrieving PPH data for customer ID %s: %s", customer_id, e)
            raise RuntimeError(f"Failed to retrieve PPH data for customer ID {customer_id}: {e}")
        
        finally:
            self.disconnect()

        # This return is unreachable due to the `return` inside the `if` statement.
        # However, it's kept here for safety as per the method's logic.
        return pd.DataFrame()  # Return empty DataFrame if no data is found

    def get_account_related_PM(self, customer_id: str) -> pd.DataFrame:
        """
        Retrieve PM-related information for a given customer.

        Args:
            customer_id (str): The unique identifier for the customer.

        Returns:
            pd.DataFrame: DataFrame containing the PM-related customer details.
        """
        try:
            self._log('info', "Starting to retrieve PM data for customer ID %s", customer_id)
            self.connect()
            
            query = f"""
            -- T24 - CUSTOMERS - PM
            SELECT
                NAME_1 AS NAME,
                'N.A' AS LEGAL_FORM_DESC_ATB,
                L_FORM_JURID AS LEGAL_FORM_CODE_ATB,
                FJ.code_goAML AS LEGAL_FORM_CODE_goAML,
                INDUSTRY.DESCRIPTION AS BUSINESS_DESC,
                CASE
                    WHEN CUSTOMER.L_SIT_JUR = 2 THEN 'A'
                    ELSE 'I'
                END AS ENTITY_STATUS,
                LEGAL_DOC_NAME,
                LEGAL_ID, 
                '2' AS ADDRESS_TYPE,
                COALESCE(NULLIF(STREET, ''), 'N.A') AS ADDRESS,
                COALESCE(NULLIF(ADDRESS_ITEM1, ''), 'N.A') AS TOWN,
                COALESCE(NULLIF(ADDRESS, ''), 'N.A') AS CITY,
                COALESCE(NULLIF(POST_CODE, ''), 'N.A') AS ZIP,
                --CASE
				--    WHEN COALESCE(COUNTRY, '') = '' 
				--         AND COALESCE(TOWN_COUNTRY, '') = '' 
				--         AND COALESCE(ADDRESS_ITEM1, '') = '' 
				--         AND COALESCE(ADDRESS_ITEM2, '') = '' 
				--         AND COALESCE(STREET, '') = ''  
				--         AND COALESCE(ADDRESS, '') = ''
				--        THEN 'N.A'
				--    ELSE CONCAT_WS(' - ',
				--         NULLIF(COUNTRY, ''),
				--         NULLIF(TOWN_COUNTRY, ''),
				--         NULLIF(ADDRESS_ITEM1, ''),
				--         NULLIF(ADDRESS_ITEM2, ''),
				--         NULLIF(STREET, ''),
				--         NULLIF(ADDRESS, ''))
				--END AS ADDRESS,
                COUNTRY AS INCORPORATION_COUNTRY_CODE,
                CASE
                    WHEN ISDATE(CONVERT(VARCHAR, TRY_CONVERT(INT, BIRTH_INCORP_DATE))) = 1 THEN CONVERT(VARCHAR, CONVERT(DATE, CONVERT(VARCHAR, TRY_CONVERT(INT, BIRTH_INCORP_DATE))), 23) + 'T00:00:00'
                    ELSE 'N.A'
                END AS INCORPORATION_DATE,
                'MF' AS ENTITY_IDENTIFIER_TYPE,
                CUSTOMER.LEGAL_ID AS ENTITY_IDENTIFIER_ID,
                CUSTOMER.COUNTRY AS ENTITY_ISSUE_COUNTRY
            FROM [MISDW].[GO_AML].[T24_CUSTOMER_DECOMPOSED_LEGAL_DETAILS] AS CUSTOMER
            LEFT JOIN [MISDW].[GO_AML].[FORME_JURIDIQUE] AS FJ ON FORMAT(CAST(FJ.ID_FORMJ AS INT), '00') = FORMAT(CAST(CUSTOMER.L_FORM_JURID AS INT), '00')
            LEFT JOIN [MISDW].[TRG].[T24_FBNK_INDUSTRY] AS INDUSTRY ON RIGHT(REPLICATE('0', 4) + INDUSTRY.INDUSTRY_CODE, 4) = RIGHT(REPLICATE('0', 4) + CUSTOMER.INDUSTRY, 4)
            WHERE CUSTOMER_CODE = '{customer_id}'
            """

            # Log the query being executed (use with caution if sensitive data is involved)
            self._log('debug', "Executing query to retrieve PM data: %s", query)

            # Using retry mechanism with self.query_executor
            df = self.query_executor.retry_query_execution(query, self.connection, max_attempts=1)

            if not df.empty:
                self._log('info', "Retrieved PM data successfully for customer ID %s", customer_id)
                return clean_dataframe(df)
            
            # Log a warning if the DataFrame is empty
            self._log('warning', "Failed to retrieve PM data for customer ID %s after retries", customer_id)

        except Exception as e:
            # Log any exceptions that occur during execution
            self._log('error', "Error while retrieving PM data for customer ID %s: %s", customer_id, e)
            raise RuntimeError(f"Failed to retrieve PM data for customer ID {customer_id}: {e}")

        finally:
            self.disconnect()

        # This return is unreachable due to the `return` inside the `if` statement.
        # However, it's kept here for safety as per the method's logic.
        return pd.DataFrame()  # Return empty DataFrame if no data is found

    def get_PM_related_persons_l1(self, pm_id: str) -> pd.DataFrame:
        """
        Retrieve the Level 1 PM-related person data for a given PM ID.

        Args:
            pm_id (str): The unique identifier for the PM.

        Returns:
            pd.DataFrame: DataFrame containing the PM-related person details.
        """
        try:
            self._log('info', "Starting to retrieve PM related person data for PM ID %s", pm_id)
            self.connect()

            query = f"""
            WITH ParsedData AS (
                SELECT
                    T24_CUSTOMER.L_NATURE_CLIENT AS CUST_TYPE,
                    RELATION_CUSTOMER.CUSTOMER AS PM_ID,
                    -- Handle position for missing 'm' attribute
                    CASE 
                        WHEN RelatedPersonNodes.Position IS NULL THEN 1
                        ELSE RelatedPersonNodes.Position 
                    END AS Position,
                    RelatedPersonNodes.Cleaned_Related_Person_ID AS RELATED_PERSON_ID,
                    RelationNodes.Cleaned_Relation AS RELATED_PERSON_RELATION,
                    RoleNodes.Cleaned_Role AS RELATED_PERSON_ROLE,
                    T24_CUSTOMER.L_NATURE_CLIENT
                FROM 
                    [MISDW].[GO_AML].[T24_FBNK_RELATION_CUSTOMER] AS RELATION_CUSTOMER
                JOIN 
                    [MISDW].[TRG].[T24_FBNK_CUSTOMER] AS T24_CUSTOMER
                    ON RELATION_CUSTOMER.CUSTOMER = T24_CUSTOMER.CUSTOMER_NO
                JOIN 
                    [MISDW].[GO_AML].[T24_FBNK_CUSTOMER_ROLE] AS CUSTOMER_ROLE
                    ON RELATION_CUSTOMER.CUSTOMER = CUSTOMER_ROLE.RECID
                -- Process RelatedPersonNodes (OF_CUSTOMER_2)
                CROSS APPLY (
                    SELECT 
                        x.value('.', 'VARCHAR(MAX)') AS Cleaned_Related_Person_ID,
                        CASE 
                            WHEN x.value('(@m)', 'INT') IS NULL THEN 1
                            ELSE x.value('(@m)', 'INT')
                        END AS Position
                    FROM 
                        (SELECT CAST('<root>' + RELATION_CUSTOMER.OF_CUSTOMER_2 + '</root>' AS XML)) AS Data(xml_data)
                    CROSS APPLY 
                        Data.xml_data.nodes('/root/c2') AS XML_Nodes(x)
                ) AS RelatedPersonNodes
                -- Process RelationNodes (IS_RELATION_1)
                CROSS APPLY (
                    SELECT 
                        x.value('.', 'VARCHAR(MAX)') AS Cleaned_Relation,
                        CASE 
                            WHEN x.value('(@m)', 'INT') IS NULL THEN 1
                            ELSE x.value('(@m)', 'INT')
                        END AS Position
                    FROM 
                        (SELECT CAST('<root>' + RELATION_CUSTOMER.IS_RELATION_1 + '</root>' AS XML)) AS Data(xml_data)
                    CROSS APPLY 
                        Data.xml_data.nodes('/root/c1') AS XML_Nodes(x)
                ) AS RelationNodes
                -- Process RoleNodes (ROLE_14)
                CROSS APPLY (
                    SELECT 
                        x.value('.', 'VARCHAR(MAX)') AS Cleaned_Role,
                        CASE 
                            WHEN x.value('(@m)', 'INT') IS NULL THEN 1
                            ELSE x.value('(@m)', 'INT')
                        END AS Position
                    FROM 
                        (SELECT CAST('<root>' + CUSTOMER_ROLE.ROLE_14 + '</root>' AS XML)) AS Data(xml_data)
                    CROSS APPLY 
                        Data.xml_data.nodes('/root/c14') AS XML_Nodes(x)
                ) AS RoleNodes
                -- Ensure positions match across all three nodes
                WHERE 
                    RelatedPersonNodes.Position = RelationNodes.Position
                    AND RelatedPersonNodes.Position = RoleNodes.Position
            )
            SELECT 
                CUST_TYPE, PM_ID, RELATED_PERSON_ID, RELATED_PERSON_RELATION, RELATED_PERSON_ROLE
            FROM ParsedData
            WHERE 
                L_NATURE_CLIENT = 'PM' 
                AND PM_ID = '{pm_id}'
            """
            
            # Log the query being executed (use with caution if sensitive data is involved)
            self._log('debug', "Executing query to retrieve PM related person data: %s", query)

            # Using retry mechanism with self.query_executor
            df = self.query_executor.retry_query_execution(query, self.connection, max_attempts=1)

            if not df.empty:
                self._log('info', "Retrieved PM related person data successfully for PM ID %s", pm_id)
                return clean_dataframe(df)

            # Log a warning if the DataFrame is empty
            self._log('warning', "No PM related person data found for PM ID %s after retries", pm_id)

        except Exception as e:
            # Log any exceptions that occur during execution
            self._log('error', "Error while retrieving PM related person data for PM ID %s: %s", pm_id, e)
            raise RuntimeError(f"Failed to retrieve PM related person data for PM ID {pm_id}: {e}")

        finally:
            self.disconnect()

        return pd.DataFrame()  # Return an empty DataFrame if no data is found
            
    def get_PM_related_persons_l2(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Retrieve additional PM-related person details based on Level 1 results.

        Args:
            df (pd.DataFrame): DataFrame containing Level 1 PM-related person details.

        Returns:
            pd.DataFrame: DataFrame containing expanded PM-related person details.
        """
        role_mapping = {
            '302': 'ACTI',
            '305': 'MCA',
            '306': 'ETBE',
            '307': 'RL'
        }
        final_df = pd.DataFrame()

        try:
            self._log('info', "Starting to retrieve PM-related person details based on Level 1 results.")
            self.connect()

            for _, row in df.iterrows():
                print('===== in get_PM_related_persons_l2 =====')
                print("RELATED_PERSON_RELATION --- RELATED_PERSON_ROLE")
                print(row.RELATED_PERSON_RELATION, row.RELATED_PERSON_ROLE)
                role_entity = role_mapping.get(row.RELATED_PERSON_ROLE, f'CUSTOMER_ID : {row.RELATED_PERSON_ID} N.A - ROLE_CODE_goAML')
                
                # Log the process for each row iteration
                self._log('info', "Processing row for RELATED_PERSON_ID %s with RELATED_PERSON_ROLE %s", row.RELATED_PERSON_ID, row.RELATED_PERSON_ROLE)
                
                query = f"""
                SELECT
                    CUSTOMER_CODE AS CUSTOMER_ID,
                	L_NATURE_CLIENT AS CUSTOMER_TYPE,
                    CASE
                        WHEN GENDER IS NULL OR GENDER = '' THEN 'N.A'
                        WHEN GENDER = 'MALE' THEN 'M'
                        WHEN GENDER = 'FEMALE' THEN 'F'
                    END AS GENDER,
                    GIVEN_NAMES AS FIRST_NAME,
                    FAMILY_NAME AS LAST_NAME,
                    CASE
                        WHEN ISDATE(CONVERT(VARCHAR, TRY_CONVERT(INT, DATE_OF_BIRTH))) = 1 THEN CONVERT(VARCHAR, CONVERT(DATE, CONVERT(VARCHAR, TRY_CONVERT(INT, DATE_OF_BIRTH))), 23) + 'T00:00:00'
                        ELSE 'N.A'
                    END AS BIRTHDATE,
                    CASE  
                        WHEN COALESCE(L_PLACE_OF_BIRT, '') = '' THEN 'N.A'  
                        ELSE NULLIF(L_PLACE_OF_BIRT, '')
                    END AS BIRTH_PLACE,
                    CUST_BIRTH_COUNTRY AS COUNTRY_OF_BIRTH,
                    LEGAL_DOC_NAME,
                    LEGAL_ID, --Numéro de la carte d’identité nationale CIN / Numéro passeport
                    LEGAL_ISS_AUTH, --Pays d'émission du passeport
                    CONVERT(NVARCHAR, CONVERT(DATE, LEGAL_ISS_DATE, 112), 120) + 'T00:00:00' AS LEGAL_ISS_DATE,
                    CONVERT(NVARCHAR, CONVERT(DATE, LEGAL_EXP_DATE, 112), 120) + 'T00:00:00' AS LEGAL_EXP_DATE,
                    NATIONALITY,
                    OTHER_NATIONILITY AS NATIONALITY_2,
                    RESIDENCE,
                    '1' AS ADDRESS_TYPE,
                    COALESCE(NULLIF(STREET, ''), 'N.A') AS ADDRESS,
                    COALESCE(NULLIF(ADDRESS_ITEM1, ''), 'N.A') AS TOWN,
                    COALESCE(NULLIF(ADDRESS, ''), 'N.A') AS CITY,
                    COALESCE(NULLIF(POST_CODE, ''), 'N.A') AS ZIP,
	                --CASE
					--    WHEN COALESCE(COUNTRY, '') = '' 
					--         AND COALESCE(TOWN_COUNTRY, '') = '' 
					--         AND COALESCE(ADDRESS_ITEM1, '') = '' 
					--         AND COALESCE(ADDRESS_ITEM2, '') = '' 
					--         AND COALESCE(STREET, '') = ''  
					--         AND COALESCE(ADDRESS, '') = ''
					--        THEN 'N.A'
					--    ELSE CONCAT_WS(' - ',
					--         NULLIF(COUNTRY, ''),
					--         NULLIF(TOWN_COUNTRY, ''),
					--         NULLIF(ADDRESS_ITEM1, ''),
					--         NULLIF(ADDRESS_ITEM2, ''),
					--         NULLIF(STREET, ''),
					--         NULLIF(ADDRESS, ''))
					--END AS ADDRESS,
                    COALESCE(NULLIF(COUNTRY, ''), 'N.A') AS COUNTRY_CODE,
                	COALESCE(NULLIF(T24_OCCUPATION.LIBELLE, ''), 'N.A') AS OCCUPATION,
                    '{row.RELATED_PERSON_RELATION}' AS RELATED_PERSON_RELATION_CODE_ATB,
                    '{row.RELATED_PERSON_ROLE}' AS RELATED_PERSON_ROLE_CODE_ATB,
                    '{role_entity}' AS ROLE_ENTITY -- relation with the entity
                    --'MAND' AS ROLE_ACCOUNT -- Relation to the account
                --FROM [MISDW].[TRG].[T24_FBNK_CUSTOMER] AS CUSTOMER
                FROM [MISDW].[GO_AML].[T24_CUSTOMER_DECOMPOSED_LEGAL_DETAILS] AS CUSTOMER
                LEFT JOIN [MISDW].[GO_AML].[T24_OCCUPATION] AS T24_OCCUPATION ON RIGHT('0000' + T24_OCCUPATION.CODE, 4) = RIGHT('0000' + OCCUPATION, 4)
                WHERE
                    CUSTOMER.CUSTOMER_CODE = '{row.RELATED_PERSON_ID}'
                """

                # Log the query being executed (use with caution for sensitive information)
                self._log('debug', "Executing query for RELATED_PERSON_ID %s: %s", row.RELATED_PERSON_ID, query)

                try:
                    temp_df = self.query_executor.retry_query_execution(query, self.connection, max_attempts=1)
                    if not temp_df.empty:
                        final_df = pd.concat([final_df, temp_df], ignore_index=True)
                        self._log('info', "Data retrieved successfully for RELATED_PERSON_ID %s", row.RELATED_PERSON_ID)
                    else:
                        self._log('warning', "No data returned for RELATED_PERSON_ID %s", row.RELATED_PERSON_ID)
                
                except Exception as e:
                    self._log('error', "Error while retrieving data for RELATED_PERSON_ID %s: %s", row.RELATED_PERSON_ID, e)

            # Log the completion of data aggregation
            self._log('info', "Finished processing all rows for PM-related person details.")
            return clean_dataframe(final_df)

        except Exception as e:
            # Log any exceptions that occur during the method execution
            self._log('error', "Error while retrieving PM-related person details: %s", e)
            raise RuntimeError("Failed to retrieve PM-related person details.")

        finally:
            self.disconnect()
