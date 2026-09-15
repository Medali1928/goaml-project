from src.db.connection import DatabaseConnection
from src.db.query_executor import QueryExecutor

from src.helpers.xmlStructure import XML
from src.helpers.utils import clean_dataframe, construct_identification

import pandas as pd
from datetime import datetime
import time
from typing import Optional, Tuple

class GetClientEQ(DatabaseConnection):

    def __init__(self, db_config: dict,) -> None:
        super().__init__(db_config['server'], db_config['database'], db_config['username'], db_config['password'])
        self.xml_generator = XML()

    def get_client(self, account_number: str) -> Tuple[str, str, str, pd.DataFrame]:
        xml = XML()
        df_account = self.get_account(account_number)
        if df_account.empty:
            raise ValueError(f"No account found with the number: {account_number}")
        
        current_time = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        df_account['DATE_BALANCE'] = current_time

        account_type = df_account.CUST_TYPE[0]

        match account_type:
            case 'PPH':
                handler = self._handle_pph_account
            case 'PPH_CJ':
                handler = self._handle_pph_cj_account
            case 'PM':
                handler = self._handle_pm_account
            case default:
                handler = self._handle_unknown_account
        
        return handler(df_account)
    
    def _handle_pph_account(self, df_account: pd.DataFrame) -> tuple:

        df_PPH = pd.DataFrame()

        df_PPH = self.get_PPH_2(customer_type=df_account.CUST_TYPE[0], customer_id=df_account.CUSTOMER_ID[0], filter_by="CUSTOMER_CODE")

        # 2 check for procuration
        df_related_third_party = pd.DataFrame()
        df_related_third_party = self.get_tiers(df_account.CUSTOMER_ID[0]).assign(ROLE_ACCOUNT='MAND')# fix
        if not df_related_third_party.empty:
            df_PPH = pd.concat([df_PPH, df_related_third_party], ignore_index=True)

        df_PPH['IDENTIFICATIONS_ID_SECTION'] = df_PPH.apply(construct_identification, axis=1)

        PPH_xml = "\n".join([self.xml_generator.create_xml_account_related_persons(row) for index, row in df_PPH.iterrows()])
        account_xml = "\n".join([self.xml_generator.create_xml_account(row, PPH_xml) for index, row in df_account.iterrows()])
        account_xml = account_xml.replace('PL_ENTITY', '')

        account_correspondences = {
            'T24_ACCOUNT': df_account['T24_ACCOUNT'].iloc[0],
            'EQ_ACCOUNT': df_account['EQ_ACCOUNT'].iloc[0],
            'ORACLE_ACCOUNT': df_account['ORACLE_ACCOUNT'].iloc[0]
        }

        # 2026-01-07
        df_PPH['ACCOUNT_TYPE'] = 'CST'

        return account_correspondences, account_xml, df_account.CUSTOMER_ID[0], df_account.CUST_TYPE[0], df_PPH
    
    def _handle_pph_cj_account(self, df_account: pd.DataFrame) -> tuple:

        df_PPH = pd.DataFrame()
        df_mandates = pd.DataFrame()

        df_mandates = self.get_mandate(df_account.CUSTOMER_ID[0])

        if not df_mandates.empty:
            for _, row in df_mandates.iterrows():
                df_PPH = pd.concat([df_PPH, self.get_PPH_2(customer_type='PPH_CJ', customer_id=row['CUSTOMER_ID_I'], filter_by="CUSTOMER_CODE")], ignore_index=True)

            df_PPH.drop_duplicates('CUSTOMER_ID' ,keep='first', inplace=True)

            df_PPH['IDENTIFICATIONS_ID_SECTION'] = df_PPH.apply(construct_identification, axis=1)
            
            PPH_xml = "\n".join([self.xml_generator.create_xml_account_related_persons(row) for index, row in df_PPH.iterrows()])
        else:
            PPH_xml = "Aucun co-titulaire associé à ce compte joint n a ete identifie dans la source de donnees."  
        
        account_xml = "\n".join([self.xml_generator.create_xml_account(row, PPH_xml) for index, row in df_account.iterrows()])
        account_xml = account_xml.replace('PL_ENTITY', '')

        account_correspondences = {
            'T24_ACCOUNT': df_account['T24_ACCOUNT'].iloc[0],
            'EQ_ACCOUNT': df_account['EQ_ACCOUNT'].iloc[0],
            'ORACLE_ACCOUNT': df_account['ORACLE_ACCOUNT'].iloc[0]
        }

        # 2026-01-07
        df_PPH['ACCOUNT_TYPE'] = 'CJ'

        return account_correspondences, account_xml, df_account.CUSTOMER_ID[0], df_account.CUST_TYPE[0], df_PPH

    def _handle_pm_account(self, df_account: pd.DataFrame) -> tuple:

        df_pm = pd.DataFrame()
        df_related_third_party = pd.DataFrame()

        df_pm = self.get_account_related_PM(df_account.CUSTOMER_ID[0])
        df_related_third_party = self.get_tiers(df_account.CUSTOMER_ID[0]).assign(ROLE_ACCOUNT='MAND')#fix

        if not df_related_third_party.empty:

            df_related_third_party['IDENTIFICATIONS_ID_SECTION'] = df_related_third_party.apply(construct_identification, axis=1)

            xml_pm_related_persons = "\n".join(
                df_related_third_party.apply(self.xml_generator.create_xml_entity_related_person, axis=1))
            
            xml_pph = "\n".join([self.xml_generator.create_xml_account_related_persons(row) 
                            for _, row in df_related_third_party.iterrows()])
            
        else:
            xml_pm_related_persons = "Aucun tiers associé à ce compte n a ete identifie dans la source de donnees."  
            xml_pph = "Aucun tiers associé à ce compte n a ete identifie dans la source de donnees."  
            
        xml_pm = self.xml_generator.create_xml_entity(df_pm.iloc[0], xml_pm_related_persons)
        
        
        xml_account = "\n".join([self.xml_generator.create_xml_account(row, xml_pph) 
                                for _, row in df_account.iterrows()])
        xml_account = xml_account.replace('PL_ENTITY', xml_pm.replace('IB_', 't_'))

        account_correspondences = {
        'T24_ACCOUNT': df_account['T24_ACCOUNT'].iloc[0],
        'EQ_ACCOUNT': df_account['EQ_ACCOUNT'].iloc[0],
        'ORACLE_ACCOUNT': df_account['ORACLE_ACCOUNT'].iloc[0]
        }

        # 2026-01-07
        df_related_third_party['ACCOUNT_TYPE'] = 'CPM'

        return account_correspondences, xml_account, df_account.CUSTOMER_ID[0], df_account.CUST_TYPE[0], df_related_third_party

    def _handle_unknown_account(self, df_account: pd.DataFrame):
        print('77')

        """
        if df_account['CUST_TYPE'].eq('PPH').any() or df_account['CUST_TYPE'].eq('PPH_CJ').any():
            df_PPH = self.get_PPH(df_account.CUST_TYPE[0], df_account.CUSTOMER_ID[0])

            PPH_xml = "\n".join([xml.create_xml_account_related_persons(row) for index, row in df_PPH.iterrows()])
            account_xml = "\n".join([xml.create_xml_account(row, PPH_xml) for index, row in df_account.iterrows()])
            account_xml = account_xml.replace('PL_ENTITY', '')

            return account_xml, df_account.CUSTOMER_ID[0], df_account.CUST_TYPE[0], df_PPH

        elif df_account['CUST_TYPE'].eq('PM').any():
            df_PM = self.getEntity(df_account.CUSTOMER_ID[0])
            df_PM_related_persons_details = self.get_signatories(df_account.CUSTOMER_ID[0])

            xml_PM_related_persons = df_PM_related_persons_details.apply(xml.create_xml_entity_related_person, axis=1)
            xml_PM_related_persons = "\n".join(xml_PM_related_persons)
            xml_PM = xml.create_xml_entity(df_PM.iloc[0], xml_PM_related_persons)

            xml_PPH = "\n".join([xml.create_xml_account_related_persons(row) for index, row in df_PM_related_persons_details.iterrows()])
            xml_account = "\n".join([xml.create_xml_account(row, xml_PPH) for index, row in df_account.iterrows()])
            xml_account = xml_account.replace('PL_ENTITY', xml_PM.replace('IB_', 't_'))

            return xml_account, df_account.CUSTOMER_ID[0], df_account.CUST_TYPE[0], df_PM_related_persons_details
            """

    def get_account(self, account: str) -> pd.DataFrame:

        query = f"""
        SELECT
            EQ_T24.GLOBUS_ACCT_NUMBER AS T24_ACCOUNT,
            EQ_ACCOUNT.BRN_ACC + EQ_ACCOUNT.BN + EQ_ACCOUNT.SFX_ACC AS EQ_ACCOUNT,
            EQ_ORACLE.NEEAN AS ORACLE_ACCOUNT,

            CASE 
                WHEN PATINDEX('%[^0]%', EQ_ACCOUNT.BN) > 0 
                THEN SUBSTRING(EQ_ACCOUNT.BN, PATINDEX('%[^0]%', EQ_ACCOUNT.BN), LEN(EQ_ACCOUNT.BN))
                ELSE '0'  -- Handles cases where BN is all zeros
            END AS CUSTOMER_ID,

            
            CASE
                WHEN EQ_ACCOUNT.CUST_TYPE_CODE IN ('HA & HD', 'HB', 'HC', 'HE', 'HZ', 'MA', 'EA', 'EB', 'EC', 'ED', 'EE', 'EF') THEN 'PPH'
                WHEN EQ_ACCOUNT.CUST_TYPE_CODE IN ('AJ') THEN 'PPH_CJ'
                WHEN EQ_ACCOUNT.CUST_TYPE_CODE IN ('CA', 'CB', 'CC', 'CD', 'CF', 'CG', 'CH', 'CI', 'DA', 'DB', 'DC', 'FA', 'GA', 'GB', 'GC', 'GD', 'IA', 'IB', 'JA', 'JB', 'KA', 'KB', 'ST') THEN 'PM'
                ELSE 'Unknown'  -- Or any default value/message you want to return for unmatched values
            END AS CUST_TYPE,
            
            EQ_ACCOUNT.RIB AS RIB,
            
            --EQ_ACCOUNT.CURRENCY_DESC AS CURRENCY_DESC,
			CASE
                WHEN EQ_ACCOUNT.CURRENCY_DESC = 'TDC' THEN 'TND'
                ELSE EQ_ACCOUNT.CURRENCY_DESC
            END AS CURRENCY_DESC,
            EQ_ACCOUNT.CURRENCY_CODE AS CURRENCY_CODE,
            
            'EQ - ' + EQ_ACCOUNT.ACCOUNT_NAME AS ACCOUNT_NAME,
            
            ACC_MAP.Description_ATB AS ACCOUNT_TYPE_DESC_ATB,
            ACC_MAP.ACCOUNT_TYPE_ATB AS ACCOUNT_TYPE_CODE_ATB,
            ACC_MAP.ACCOUNT_TYPE_goAML AS ACOUNT_TYPE_CODE_goAML,
            
            CASE
				WHEN NULLIF(EQ_ACCOUNT.OPENED, 0) IS NOT NULL THEN
					CONVERT(CHAR(19), CAST(CAST(19000000 + EQ_ACCOUNT.OPENED AS CHAR(8)) AS DATETIME), 126)
				ELSE NULL
			END AS OPENING_DATE_FORMATTED,

			CASE
				WHEN NULLIF(EQ_ACCOUNT.CLOSED, 0) IS NOT NULL THEN
					CONVERT(CHAR(19), CAST(CAST(19000000 + EQ_ACCOUNT.CLOSED AS CHAR(8)) AS DATETIME), 126)
				ELSE NULL
			END AS CLOSED_DATE_FORMATTED,
            
            EQ_ACCOUNT.EQA_BALANCE_CCY AS BALANCE,
            EQ_ACCOUNT.STATUS AS STATUS
        FROM [MISDW].[GO_AML].[EQA_ACCOUNT_DAILY] AS EQ_ACCOUNT
        LEFT JOIN [MISDW].[TRG].[T24_FATB_ALTERNATE_ACCO000] AS EQ_T24 ON EQ_T24.ALTERNATIVE_NUMBER = EQ_ACCOUNT.BRN_ACC + EQ_ACCOUNT.BN + EQ_ACCOUNT.SFX_ACC
        LEFT JOIN [MISDW].[TRG].[EQA_ACC_EXTERNAL_ACCOUNT_NUMBER] AS EQ_ORACLE ON EQ_ORACLE.NEAB + EQ_ORACLE.NEAN + EQ_ORACLE.NEAS = EQ_T24.ALTERNATIVE_NUMBER
        LEFT JOIN [MISDW].[GO_AML].[ACCOUNT_TYPE] AS ACC_MAP ON TRIM(ACC_MAP.ACCOUNT_TYPE_ATB) = TRIM(EQ_ACCOUNT.ACOUNT_TYPE_CODE)
        WHERE
            EQ_ACCOUNT.BRN_ACC + EQ_ACCOUNT.BN + EQ_ACCOUNT.SFX_ACC = '{account}'
        """

        try:
            self.connect()
            attempts = 0
            max_attempts = 3

            while attempts < max_attempts:
                query_executor = QueryExecutor(self.connection)
                df = query_executor.execute_query_to_dataframe(query)

                if not df.empty:
                    break
                attempts += 1
                time.sleep(5)  # Wait for 5 seconds before retrying
                    
        finally:
            self.disconnect()
                
        return clean_dataframe(df.head(1))

    def get_PPH_2(self, customer_id: str, filter_by: str, customer_type: str = None) -> pd.DataFrame:

        customer_id = customer_id.lstrip('0') # removes all leading (stands for left) zeros ('0') from the string customer_id. ex 00012345 -> 12345

        print("####################################")
        print(customer_id)
        print(filter_by)
        print(customer_type)
        print("####################################")

        if filter_by not in ("CUSTOMER_CODE", "LEGAL_ID"):
            raise ValueError("filter_by must be either 'CUSTOMER_CODE' or 'LEGAL_ID'")
        
        query = f"""
        SELECT
            CASE 
                WHEN PATINDEX('%[^0]%', CUSTOMER_CODE) > 0 
                THEN SUBSTRING(CUSTOMER_CODE, PATINDEX('%[^0]%', CUSTOMER_CODE), LEN(CUSTOMER_CODE))
                ELSE '0'  
            END AS CUSTOMER_ID,
            GENDER AS GENDER,
            GIVEN_NAMES AS FIRST_NAME,
            FAMILY_NAME AS LAST_NAME,
            CASE
                WHEN ISDATE(CONVERT(VARCHAR, TRY_CONVERT(INT, DATE_OF_BIRTH))) = 1 THEN CONVERT(VARCHAR, CONVERT(DATE, CONVERT(VARCHAR, TRY_CONVERT(INT, DATE_OF_BIRTH))), 23) + 'T00:00:00'
                ELSE NULL
            END AS BIRTHDATE,
            PLACE_OF_BIRTH AS BIRTH_PLACE,
            LEGAL_DOC_NAME,
            LEGAL_ID, --Numéro de la carte d’identité nationale CIN / Numéro passeport
            LEGAL_ISS_AUTH, --Pays d'émission du passeport
            LEGAL_ISS_DATE,
            LEGAL_EXP_DATE,
            NATIONALITY AS NATIONALITY,
            RESIDENCE AS RESIDENCE,
            '1' AS ADDRESS_TYPE,
            COALESCE(NULLIF(STREET, ''), 'N.A') AS ADDRESS,
            'N.A' AS TOWN,
            COALESCE(NULLIF(ADDRESS, ''), 'N.A') AS CITY,
            COALESCE(NULLIF(POST_CODE, ''), 'N.A') AS ZIP,
            --CONCAT(
			--    NULLIF(ADDRESS, ''),
			--    CASE
			--        WHEN NULLIF(ADDRESS, '') IS NOT NULL AND NULLIF(STREET, '') IS NOT NULL THEN ' '
			--        ELSE ''
			--    END,
			--    NULLIF(STREET, '')
			--) AS ADDRESS,
            COUNTRY AS COUNTRY_CODE,
            T24_OCCUPATION.LIBELLE AS OCCUPATION
        FROM [MISDW].[GO_AML].[EQ_PPH]
        LEFT JOIN [MISDW].[GO_AML].[T24_OCCUPATION] AS T24_OCCUPATION ON RIGHT('0000' + T24_OCCUPATION.CODE, 4) = RIGHT('0000' + OCCUPATION, 4)
        WHERE
            CASE 
                WHEN PATINDEX('%[^0]%', {filter_by}) > 0 
                THEN SUBSTRING({filter_by}, PATINDEX('%[^0]%', {filter_by}), LEN({filter_by}))
                ELSE '0'  
            END = '{customer_id}'
        """
        try:
            self.connect()
            attempts = 0
            max_attempts = 3
            while attempts < max_attempts:
                query_executor = QueryExecutor(self.connection)
                df = query_executor.execute_query_to_dataframe(query)
                if not df.empty:
                    break
                attempts += 1
                time.sleep(5)  # Wait for 5 seconds before retrying
                    
        finally:
            self.disconnect()

        if customer_type == 'PPH':
            df['ROLE_ACCOUNT'] = 'TICPT'
        if customer_type == 'PPH_CJ':
            df['ROLE_ACCOUNT'] = 'TICJD'
        if customer_type == 'PPH_MAND':
            df['ROLE_ACCOUNT'] = 'MAND'

        return clean_dataframe(df)
    
    def get_mandate(self, customer_id: str) -> pd.DataFrame:

        customer_id = customer_id.lstrip('0')
        
        query = f"""
        SELECT 
            CASE 
                WHEN PATINDEX('%[^0]%', RKAN) > 0 
                THEN SUBSTRING(RKAN, PATINDEX('%[^0]%', RKAN), LEN(RKAN))
                ELSE '0'  
            END AS CUSTOMER_ID_G,
            
            CASE 
                WHEN PATINDEX('%[^0]%', RKSCUS) > 0 
                THEN SUBSTRING(RKSCUS, PATINDEX('%[^0]%', RKSCUS), LEN(RKSCUS))
                ELSE '0'  
            END AS CUSTOMER_ID_I

        FROM MISDW.GO_AML.EQA_JOINT_ACCOUNT

        WHERE 
            CASE 
                WHEN PATINDEX('%[^0]%', RKAN) > 0 
                THEN SUBSTRING(RKAN, PATINDEX('%[^0]%', RKAN), LEN(RKAN))
                ELSE '0'  
            END = '{customer_id}'
        """
        try:
            self.connect()
            attempts = 0
            max_attempts = 3
            while attempts < max_attempts:
                query_executor = QueryExecutor(self.connection)
                df = query_executor.execute_query_to_dataframe(query)
                if not df.empty:
                    break
                attempts += 1
                time.sleep(5)  # Wait for 5 seconds before retrying
                    
        finally:
            self.disconnect()
            
        return clean_dataframe(df)
    
    def get_tiers(self, customer_id: str) -> pd.DataFrame:

        customer_id = customer_id.lstrip('0')
        
        query = f"""
        SELECT
        	BASIC_N AS CUSTOMER_ID,
        	L_NATURE_CLIENT AS CUSTOMER_TYPE,
            CASE
                WHEN TIERS.GENDER IS NULL OR TIERS.GENDER = '' THEN NULL
                ELSE TIERS.GENDER
            END AS GENDER,
            GIVEN_NAMES AS FIRST_NAME,
            FAMILY_NAME AS LAST_NAME,
            CASE
                WHEN ISDATE(CONVERT(VARCHAR, TRY_CONVERT(INT, DATE_OF_BIRTH))) = 1 THEN CONVERT(VARCHAR, CONVERT(DATE, CONVERT(VARCHAR, TRY_CONVERT(INT, DATE_OF_BIRTH))), 23) + 'T00:00:00'
                ELSE '0000-00-00T00:00:00'
            END AS BIRTHDATE,
            COALESCE(NULLIF(TIERS.[L PLACE OF BIRT], ''), 'N.A') AS BIRTH_PLACE,
            LEGAL_DOC_NAME,
            LEGAL_ID, --Numéro de la carte d’identité nationale CIN / Numéro passeport
            LEGAL_ISS_AUTH, --Pays d'émission du passeport
            LEGAL_ISS_DATE,
            LEGAL_EXP_DATE,
            TIERS.NATIONALITY,
            TIERS.RESIDENCE,
            '1' AS ADDRESS_TYPE,
            COALESCE(NULLIF(TIERS.STREET, ''), 'N.A') AS ADDRESS,
            'N.A' AS TOWN,
            COALESCE(NULLIF(TIERS.ADDRESS, ''), 'N.A') AS CITY,
            COALESCE(NULLIF(TIERS.POST_CODE, ''), 'N.A') AS ZIP,
            --COALESCE(NULLIF(TIERS.POST_CODE, ''), 'N.A') AS ZIP,
            --CONCAT(
			--    NULLIF(ADDRESS, ''),
			--    CASE
			--        WHEN NULLIF(ADDRESS, '') IS NOT NULL AND NULLIF(STREET, '') IS NOT NULL THEN ' '
			--        ELSE ''
			--    END,
			--    NULLIF(STREET, '')
			--) AS ADDRESS,
            COALESCE(NULLIF(COUNTRY, ''), 'N.A') AS COUNTRY_CODE,
            COALESCE(NULLIF(T24_OCCUPATION.LIBELLE, ''), 'N.A') AS OCCUPATION,
            TYPE_TIERS AS RELATED_PERSON_ROLE_CODE_ATB,
            CASE 
                WHEN TYPE_TIERS = 'REPRES-LEGAL' THEN 'RL' -- Représentant Légal
                WHEN TYPE_TIERS = 'Dirigeant' THEN 'A' -- Directeur General
                WHEN TYPE_TIERS = 'TUTEUR-LEGAL' THEN 'RL' -- Représentant Légal
                WHEN TYPE_TIERS = 'ACT-PPH' THEN 'ACTI' -- Actionnaire
                WHEN TYPE_TIERS = 'GARANTPPH' THEN 'ACTI' -- Actionnaire
                WHEN TYPE_TIERS = 'SIGNATAIRE' THEN 'RL' -- Représentant Légal
            END	AS ROLE_ENTITY
        FROM [MISDW].[GO_AML].[EQ_TIERS] AS TIERS
        LEFT JOIN [MISDW].[GO_AML].[T24_OCCUPATION] AS T24_OCCUPATION ON RIGHT('0000' + T24_OCCUPATION.CODE, 4) = RIGHT('0000' + OCCUPATION, 4)
        WHERE
            CASE 
                WHEN PATINDEX('%[^0]%', BASIC_N) > 0 
                THEN SUBSTRING(BASIC_N, PATINDEX('%[^0]%', BASIC_N), LEN(BASIC_N))
                ELSE '0'  
            END = '{customer_id}'
        """
        try:
            self.connect()
            attempts = 0
            max_attempts = 3
            while attempts < max_attempts:
                query_executor = QueryExecutor(self.connection)
                df = query_executor.execute_query_to_dataframe(query)
                if not df.empty:
                    break
                attempts += 1
                time.sleep(5)  # Wait for 5 seconds before retrying
                    
        finally:
            self.disconnect()

        return clean_dataframe(df)
    
    def get_account_related_PM(self, customer_id: str) -> pd.DataFrame:

        customer_id = customer_id.lstrip('0')
        
        query = f"""
        SELECT
            CASE 
                WHEN PATINDEX('%[^0]%', PM.CUSTOMER_CODE) > 0 
                THEN SUBSTRING(PM.CUSTOMER_CODE, PATINDEX('%[^0]%', PM.CUSTOMER_CODE), LEN(PM.CUSTOMER_CODE))
                ELSE '0'  
            END AS CUSTOMER_CODE,
            PM.NAME_1 AS NAME,
            PM.L_FORM_JURID AS LEGAL_FORM_CODE_ATB,
            FJ.code_goAML AS LEGAL_FORM_CODE_goAML,
            INDUSTRY.DESCRIPTION AS BUSINESS_DESC,
            CASE
                WHEN PM.L_SIT_JUR = 2 THEN 'A'
                ELSE 'I'
            END AS ENTITY_STATUS,
            '2' AS ADDRESS_TYPE,
            COALESCE(NULLIF(STREET, ''), 'N.A') AS ADDRESS,
            'N.A' AS TOWN,
            COALESCE(NULLIF(ADDRESS, ''), 'N.A') AS CITY,
            COALESCE(NULLIF(POST_CODE, ''), 'N.A') AS ZIP,
            --CASE
            --    WHEN PM.POST_CODE IS NULL OR PM.POST_CODE = '' THEN 'N.A'
            --    ELSE PM.POST_CODE
            --END AS ZIP,
            --PM.ADDRESS + PM.STREET AS ADDRESS,
            COUNTRY AS INCORPORATION_COUNTRY_CODE,
            CASE
                WHEN ISDATE(CONVERT(VARCHAR, TRY_CONVERT(INT, PM.BIRTH_INCORP_DATE))) = 1 THEN CONVERT(VARCHAR, CONVERT(DATE, CONVERT(VARCHAR, TRY_CONVERT(INT, PM.BIRTH_INCORP_DATE))), 23) + 'T00:00:00'
                ELSE '0000-00-00T00:00:00'
            END AS INCORPORATION_DATE,
            'MF' AS ENTITY_IDENTIFIER_TYPE,
            PM.LEGAL_ID AS ENTITY_IDENTIFIER_ID,
            PM.COUNTRY AS ENTITY_ISSUE_COUNTRY
        FROM [MISDW].[GO_AML].[EQ_PM] AS PM
        LEFT JOIN [MISDW].[GO_AML].[FORME_JURIDIQUE] AS FJ ON FORMAT(FJ.ID_FORMJ, '00') = PM.L_FORM_JURID
        LEFT JOIN [MISDW].[TRG].[T24_FBNK_INDUSTRY] AS INDUSTRY ON RIGHT(REPLICATE('0', 4) + INDUSTRY.INDUSTRY_CODE, 4) = RIGHT(REPLICATE('0', 4) + PM.INDUSTRY, 4)
        WHERE
            CASE 
                WHEN PATINDEX('%[^0]%', PM.CUSTOMER_CODE) > 0 
                THEN SUBSTRING(PM.CUSTOMER_CODE, PATINDEX('%[^0]%', PM.CUSTOMER_CODE), LEN(PM.CUSTOMER_CODE))
                ELSE '0'  
            END = '{customer_id}'
        """
        try:
            self.connect()
            attempts = 0
            max_attempts = 3
            while attempts < max_attempts:
                query_executor = QueryExecutor(self.connection)
                df = query_executor.execute_query_to_dataframe(query)
                if not df.empty:
                    break
                attempts += 1
                time.sleep(5)  # Wait for 5 seconds before retrying
                    
        finally:
            self.disconnect()

        return clean_dataframe(df)