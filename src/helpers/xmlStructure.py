from typing import Union
import pandas as pd

class XML:
    """
    A utility class for creating XML elements from row data.
    """

    @staticmethod
    def _is_missing(value: Union[str, None]) -> bool:
        """Return True for values that must never be written into XML."""
        if value is None:
            return True
        try:
            if pd.isna(value):
                return True
        except (TypeError, ValueError):
            pass

        text = str(value).strip()
        return text == "" or text.upper() in {"N.A", "NA", "NAN", "NONE", "NULL", "NAT"}

    @staticmethod
    def _xml_escape(value: Union[str, None]) -> str:
        """Escape text values before inserting them into XML."""
        import html
        return html.escape(str(value).strip(), quote=False)

    @staticmethod
    def _optional_tag(tag: str, value: Union[str, None], customer_id: str = None) -> str:
        """
        Create an XML tag, replacing missing values with an explicit N.A marker.
        This prevents Python/Pandas missing values such as NaN/NaT from being
        written as literal XML values.
        """
        if not XML._is_missing(value):
            return f"<{tag}>{XML._xml_escape(value)}</{tag}>"

        na_message = f"N.A - {tag}"
        if customer_id:
            na_message += f" - CustomerID: {customer_id}"
        return f"<{tag}>{XML._xml_escape(na_message)}</{tag}>"

    @staticmethod
    def _cin_id_number_tag(row: Union[dict, pd.Series]) -> str:
        """
        Return <id_number> for Tunisian physical persons when a CIN is available.
        CTAF requires this field in addition to the <identifications> block.
        """
        import re

        nationality = str(row.get("NATIONALITY", "")).strip().upper()
        residence = str(row.get("RESIDENCE", "")).strip().upper()
        if nationality != "TN" and residence != "TN":
            return ""

        # Prefer explicit columns if still available.
        legal_doc_name = str(row.get("LEGAL_DOC_NAME", "")).upper()
        legal_id = str(row.get("LEGAL_ID", "")).strip()
        if "CIN" in legal_doc_name and re.fullmatch(r"\d{8}", legal_id):
            return f"<id_number>{legal_id}</id_number>"

        # Fallback: extract the CIN number from IDENTIFICATIONS_ID_SECTION.
        identifications = str(row.get("IDENTIFICATIONS_ID_SECTION", ""))
        match = re.search(
            r"<identification>.*?<type>\s*B\s*</type>.*?<number>\s*(\d{8})\s*</number>.*?</identification>",
            identifications,
            flags=re.DOTALL,
        )
        if match:
            return f"<id_number>{match.group(1)}</id_number>"

        return ""

    def create_xml_account_related_persons(self, row: Union[dict, pd.Series], comments: str = None) -> str:
        """
        Create an XML for account-related persons.

        Args:
            row (Union[dict, pd.Series]): The input row containing person details.

        Returns:
            str: The generated XML string.
        """

        customer_id = row.get("CUSTOMER_ID")
        country_of_birth = row.get("COUNTRY_OF_BIRTH")
        nationality_2 = row.get("NATIONALITY_2")

        return f"""
        <account_related_person>
            <t_person>
                {self._optional_tag("gender", row.get("GENDER"), row.get("CUSTOMER_ID"))}
                {self._optional_tag("first_name", row.get("FIRST_NAME"), row.get("CUSTOMER_ID"))}
                {self._optional_tag("last_name", row.get("LAST_NAME"), row.get("CUSTOMER_ID"))}
                {self._optional_tag("birthdate", row.get("BIRTHDATE"), row.get("CUSTOMER_ID"))}
                {self._optional_tag("birth_place", row.get("BIRTH_PLACE"), row.get("CUSTOMER_ID"))}
                {self._optional_tag("country_of_birth", country_of_birth, customer_id) if pd.notna(country_of_birth) and str(country_of_birth).strip() else ""}
                {self._cin_id_number_tag(row)}
                {self._optional_tag("nationality1", row.get("NATIONALITY"), row.get("CUSTOMER_ID"))}
                {self._optional_tag("nationality2", nationality_2, customer_id) if pd.notna(nationality_2) and str(nationality_2).strip() else ""}
                {self._optional_tag("residence", row.get("RESIDENCE"), row.get("CUSTOMER_ID"))}
                <addresses>
                    <address>
                        {self._optional_tag("address_type", row.get("ADDRESS_TYPE"), row.get("CUSTOMER_ID"))}
                        {self._optional_tag("address", row.get("ADDRESS"), row.get("CUSTOMER_ID"))}
                        {self._optional_tag("town", row.get("TOWN"), row.get("CUSTOMER_ID"))}
                        {self._optional_tag("city", row.get("TOWN"), row.get("CUSTOMER_ID"))}
                        {self._optional_tag("zip", row.get("ZIP"), row.get("CUSTOMER_ID"))}
                        {self._optional_tag("country_code", row.get("COUNTRY_CODE"), row.get("CUSTOMER_ID"))}
                    </address>
                </addresses>
                {self._optional_tag("occupation", row.get("OCCUPATION"), row.get("CUSTOMER_ID"))}
                <identifications>
                    {row.get("IDENTIFICATIONS_ID_SECTION")}
                </identifications>
                {f"<comments>{comments}</comments>" if comments else ""}
            </t_person>
            {self._optional_tag("role", row.get("ROLE_ACCOUNT"), row.get("CUSTOMER_ID"))}
        </account_related_person>
        """

    def create_xml_entity_related_person(self, row: Union[dict, pd.Series], comments: str = None) -> str:
        """
        Create an XML for entity-related persons.

        Args:
            row (Union[dict, pd.Series]): The input row containing person details.

        Returns:
            str: The generated XML string.
        """
        customer_id = row.get("CUSTOMER_ID")
        country_of_birth = row.get("COUNTRY_OF_BIRTH")
        nationality_2 = row.get("NATIONALITY_2")

        return f"""
        <entity_related_person>
            <person>
                {self._optional_tag("gender", row.get("GENDER"), row.get("CUSTOMER_ID"))}
                {self._optional_tag("first_name", row.get("FIRST_NAME"), row.get("CUSTOMER_ID"))}
                {self._optional_tag("last_name", row.get("LAST_NAME"), row.get("CUSTOMER_ID"))}
                {self._optional_tag("birthdate", row.get("BIRTHDATE"), row.get("CUSTOMER_ID"))}
                {self._optional_tag("birth_place", row.get("BIRTH_PLACE"), row.get("CUSTOMER_ID"))}
                {self._optional_tag("country_of_birth", country_of_birth, customer_id) if pd.notna(country_of_birth) and str(country_of_birth).strip() else ""}
                {self._cin_id_number_tag(row)}
                {self._optional_tag("nationality1", row.get("NATIONALITY"), row.get("CUSTOMER_ID"))}
                {self._optional_tag("nationality2", nationality_2, customer_id) if pd.notna(nationality_2) and str(nationality_2).strip() else ""}
                <addresses>
                    <address>
                        {self._optional_tag("address_type", row.get("ADDRESS_TYPE", "1"), row.get("CUSTOMER_ID"))}
                        {self._optional_tag("address", row.get("ADDRESS"), row.get("CUSTOMER_ID"))}
                        {self._optional_tag("town", row.get("TOWN"), row.get("CUSTOMER_ID"))}
                        {self._optional_tag("city", row.get("TOWN"), row.get("CUSTOMER_ID"))}
                        {self._optional_tag("country_code", row.get("COUNTRY_CODE"), row.get("CUSTOMER_ID"))}
                    </address>
                </addresses>
                {self._optional_tag("occupation", row.get("OCCUPATION"), row.get("CUSTOMER_ID"))}
                <identifications>
                    {row.get("IDENTIFICATIONS_ID_SECTION")}
                </identifications>
                {f"<comments>{comments}</comments>" if comments else ""}
            </person>
            {self._optional_tag("role", row.get("ROLE_ENTITY"), row.get("CUSTOMER_ID"))}
        </entity_related_person>
        """

    def create_xml_entity(self, row: dict[str, str], related_persons: str) -> str:
        """
        Creates an XML entity representation based on the given row data and related persons' information.

        Args:
            row (dict): A dictionary containing entity data where keys are column names and values are their corresponding data.
            related_persons (str): A string containing related persons' XML content.

        Returns:
            str: A formatted XML string representing the entity.
        """
        # Indent each line of the related_persons XML content
        indented_related_persons = "\n".join(["    " + line for line in related_persons.splitlines() if line.strip() != ""])
        
        # Conditionally include the <entity_identifications> block
        entity_identifications = (
            f"""
            <entity_identifications>
                <entity_identifier>
                    <type>{row['ENTITY_IDENTIFIER_TYPE']}</type>
                    <number>{row['ENTITY_IDENTIFIER_ID']}</number>
                    <issue_country>{row['ENTITY_ISSUE_COUNTRY']}</issue_country>
                </entity_identifier>
            </entity_identifications>
            """ if 'ENTITY_IDENTIFIER_ID' in row else ""
        )
    
        return f"""
        <IB_entity>
            <name>{row['NAME']}</name>
            <incorporation_legal_form>{row['LEGAL_FORM_CODE_goAML']}</incorporation_legal_form>
            <business>{row['BUSINESS_DESC']}</business>
            <entity_status>{row['ENTITY_STATUS']}</entity_status>
            <addresses>
                <address>
                    <address_type>{row['ADDRESS_TYPE']}</address_type>
                    <address>{row['ADDRESS']}</address>
                    <town>{row['TOWN']}</town>
                    <city>{row['TOWN']}</city>
                    <country_code>{row['INCORPORATION_COUNTRY_CODE']}</country_code>
                </address>
            </addresses>
            <incorporation_country_code>{row['INCORPORATION_COUNTRY_CODE']}</incorporation_country_code>
            <related_persons>
            {indented_related_persons}
            </related_persons>
            <incorporation_date>{row['INCORPORATION_DATE']}</incorporation_date>
            {entity_identifications}
        </IB_entity>
        """

    def create_xml_account(self, row: Union[dict, pd.Series], related_persons: str) -> str:
        """
        Create an XML for an account with related persons.

        Args:
            row (Union[dict, pd.Series]): The input row containing account details.
            related_persons (str): XML string for related persons.

        Returns:
            str: The generated XML string.
        """
        indented_related_persons = "\n".join(["    " + line for line in related_persons.splitlines() if line.strip()])
        closed_date = self._optional_tag("closed", row.get("CLOSED_DATE_FORMATTED")) if row.get("STATUS") != 'A' else ""

        print('+++++++++++++++')
        if row.get("CLOSED_DATE_FORMATTED") and float(row.get("BALANCE")) == 0:
            balance = '<balance>0</balance>'
        else:
            balance = self._optional_tag("balance", row.get("BALANCE"))

        return f"""
        <IB_account>
            {self._optional_tag("institution_name", "ARAB TUNISIAN BANK")}
            {self._optional_tag("swift", "ATBKTNTT")}
            {self._optional_tag("account", row.get("RIB"))}
            {self._optional_tag("currency_code", row.get("CURRENCY_DESC"))}
            {self._optional_tag("account_name", row.get("ACCOUNT_NAME"))}
            {self._optional_tag("personal_account_type", row.get("ACOUNT_TYPE_CODE_goAML"))}
           <related_persons>
            {indented_related_persons.strip() if indented_related_persons.strip() else '''
            <account_related_person>
                <t_person>
                    <gender>M</gender>
                    <first_name>UNKNOWN</first_name>
                    <last_name>UNKNOWN</last_name>
                    <birthdate>1900-01-01T00:00:00</birthdate>
                    <birth_place>N.A</birth_place>
                    <nationality1>TN</nationality1>
                    <residence>TN</residence>
                    <addresses>
                    </addresses>
                    <occupation>N.A</occupation>
                </t_person>
                <role>MAND</role>
            </account_related_person>
            '''}
           </related_persons>
            {self._optional_tag("opened", row.get("OPENING_DATE_FORMATTED"))}
            {closed_date}
            {balance}
            {self._optional_tag("date_balance", row.get("DATE_BALANCE"))}
            {self._optional_tag("status_code", row.get("STATUS"))}
        </IB_account>
        """

    def create_transaction_xml(self, row: Union[dict, pd.Series], comment: str = None) -> str:
        """
        Create an XML for a transaction with optional comment section.
    
        Args:
            row (Union[dict, pd.Series]): The input row containing transaction details.
            comment (str, optional): An optional comment to include in the XML.
    
        Returns:
            str: The generated XML string.
        """
        # Construct the comment section if provided
        comment_section = self._optional_tag("comments", comment) if comment else ""

        # Format the XML with the given data
        return f"""
        <transaction>
            {self._optional_tag("transactionnumber", row.get("TRANSACTION_NUMBER"))}
            {self._optional_tag("internal_ref_number", row.get("TRANSACTION_REF"))}
            {self._optional_tag("transaction_location", row.get("TRANSACTION_LOCATION").replace('.', ' '))}
            {self._optional_tag("date_transaction", row.get("DATE_TRANSACTION"))}
            {self._optional_tag("transmode_code", row.get("TRANSACTION_CODE_GOAML"))}
            {self._optional_tag("amount_local", row.get("AMOUNT_LOCAL"))}
            {self._optional_tag("transaction_status", row.get("TRANSACTION_STATUS_CODE"))}
            PL_FROM
            PL_TO
            {comment_section}
        </transaction>
        """

    def create_xml_OBJ(self, row: Union[dict, pd.Series], version: int) -> str:
        """
        Create an XML for a financial object with fund and currency details.
    
        Args:
            row (Union[dict, pd.Series]): The input row containing financial data.
            version (int): The version of the XML structure (1 or 2).
    
        Returns:
            str: The generated XML string.
        """
        # Validate version and retrieve the appropriate data
        if version == 1:
            fund_code = row.get('FUND_CODE_1')
            currency_code = row.get('CURRENCY_CODE_1')
            foreign_amount = row.get('FOREIGN_AMOUNT_1')
            country = row.get('COUNTRY_1')
        elif version == 2:
            fund_code = row.get('FUND_CODE_2')
            currency_code = row.get('CURRENCY_CODE_2')
            foreign_amount = row.get('FOREIGN_AMOUNT_2')
            country = row.get('COUNTRY_2')
        else:
            raise ValueError("Invalid version. Please use 1 or 2.")
    
        # Construct the XML with optional tags
        return f"""
        <t_PL1>
            {self._optional_tag("PL2_funds_code", fund_code)}
            <PL2_foreign_currency>
                {self._optional_tag("foreign_currency_code", currency_code)}
                {self._optional_tag("foreign_amount", foreign_amount)}
            </PL2_foreign_currency>
            PL_CONDUCTOR
            PL3
            {self._optional_tag("PL2_country", country)}
        </t_PL1>
        """

    def create_xml_conductor(self, row: Union[dict, pd.Series], comments: str = None) -> str:
        """
        Create an XML for a conductor with personal and address details.

        Args:
            row (Union[dict, pd.Series]): The input row containing conductor data.
            comments (str, optional): Additional comments to include in the XML. Defaults to None.

        Returns:
            str: The generated XML string.
        """

        customer_id = row.get("CUSTOMER_ID")
        country_of_birth = row.get("COUNTRY_OF_BIRTH")
        nationality_2 = row.get("NATIONALITY_2")

        # Create the main conductor XML with optional tags
        return f"""
        <t_conductor>
            {self._optional_tag("gender", row.get('GENDER'), row.get("CUSTOMER_ID"))}
            {self._optional_tag("first_name", row.get('FIRST_NAME'), row.get("CUSTOMER_ID"))}
            {self._optional_tag("last_name", row.get('LAST_NAME'), row.get("CUSTOMER_ID"))}
            {self._optional_tag("birthdate", row.get('BIRTHDATE'), row.get("CUSTOMER_ID"))}
            {self._optional_tag("birth_place", row.get('BIRTH_PLACE'), row.get("CUSTOMER_ID"))}
            {self._optional_tag("country_of_birth", country_of_birth, customer_id) if pd.notna(country_of_birth) and str(country_of_birth).strip() else ""}
            {self._cin_id_number_tag(row)}
            {self._optional_tag("nationality1", row.get('NATIONALITY'), row.get("CUSTOMER_ID"))}
            {self._optional_tag("nationality2", nationality_2, customer_id) if pd.notna(nationality_2) and str(nationality_2).strip() else ""}
            {self._optional_tag("residence", row.get('RESIDENCE'), row.get("CUSTOMER_ID"))}
            <addresses>
                <address>
                    {self._optional_tag("address_type", row.get('ADDRESS_TYPE'), row.get("CUSTOMER_ID"))}
                    {self._optional_tag("address", row.get('ADDRESS'), row.get("CUSTOMER_ID"))}
                    {self._optional_tag("town", row.get("TOWN"), row.get("CUSTOMER_ID"))}
                    {self._optional_tag("city", row.get("TOWN"), row.get("CUSTOMER_ID"))}
                    {self._optional_tag("zip", row.get('ZIP'), row.get("CUSTOMER_ID"))}
                    {self._optional_tag("country_code", row.get('COUNTRY_CODE'), row.get("CUSTOMER_ID"))}
                </address>
            </addresses>
            {self._optional_tag("occupation", row.get('OCCUPATION'), row.get("CUSTOMER_ID"))}
            <identifications>
                    {row.get("IDENTIFICATIONS_ID_SECTION")}
            </identifications>
            {f"<comments>{comments}</comments>" if comments else ""}
        </t_conductor>
        """

    def create_xml_entity_related_person_v2(self, row: Union[dict, pd.Series], comments: str = None) -> str:
        """
        Create an XML for an entity-related person with full personal and address details.
    
        Args:
            row (Union[dict, pd.Series]): The input row containing related person data.
    
        Returns:
            str: The generated XML string.
        """
        customer_id = row.get("CUSTOMER_ID")
        country_of_birth = row.get("COUNTRY_OF_BIRTH")
        nationality_2 = row.get("NATIONALITY_2")

        return f"""
        <account_related_person>
            <t_person>
                {self._optional_tag("gender", row.get('GENDER'), row.get("CUSTOMER_ID"))}
                {self._optional_tag("first_name", row.get('FIRST_NAME'), row.get("CUSTOMER_ID"))}
                {self._optional_tag("last_name", row.get('LAST_NAME'), row.get("CUSTOMER_ID"))}
                {self._optional_tag("birthdate", row.get('BIRTHDATE'), row.get("CUSTOMER_ID"))}
                {self._optional_tag("birth_place", row.get('BIRTH_PLACE'), row.get("CUSTOMER_ID"))}
                {self._optional_tag("country_of_birth", country_of_birth, customer_id) if pd.notna(country_of_birth) and str(country_of_birth).strip() else ""}
                {self._optional_tag("id_number", row.get('LEGAL_ID'), row.get("CUSTOMER_ID"))}
                {self._optional_tag("nationality1", row.get('NATIONALITY'), row.get("CUSTOMER_ID"))}
                {self._optional_tag("nationality2", nationality_2, customer_id) if pd.notna(nationality_2) and str(nationality_2).strip() else ""}
                <residence>NA</residence>
                <addresses>
                    <address>
                        {self._optional_tag("address_type", "1")}
                        {self._optional_tag("address", row.get('ADDRESS'), row.get("CUSTOMER_ID"))}
                        {self._optional_tag("town", row.get("TOWN"), row.get("CUSTOMER_ID"))}
                        {self._optional_tag("city", row.get("TOWN"), row.get("CUSTOMER_ID"))}
                        {self._optional_tag("country_code", row.get('COUNTRY_CODE'), row.get("CUSTOMER_ID"))}
                    </address>
                </addresses>
                {self._optional_tag("occupation", row.get('OCCUPATION'), row.get("CUSTOMER_ID"))}
                {f"<comments>{comments}</comments>" if comments else ""}
            </t_person>
            {self._optional_tag("role", row.get('ROLE_CODE_CTAF'), row.get("CUSTOMER_ID"))}
        </account_related_person>
        """

    def create_xml_person(self, row: Union[dict, pd.Series], comments: str = None) -> str:
        """
        Create an XML for a person with full details.
    
        Args:
            row (Union[dict, pd.Series]): The input row containing personal information.
    
        Returns:
            str: The generated XML string.
        """

        customer_id = row.get("CUSTOMER_ID")
        country_of_birth = row.get("COUNTRY_OF_BIRTH")
        nationality_2 = row.get("NATIONALITY_2")
            
        return f"""
        <IB_person>
            {self._optional_tag("gender", row.get('GENDER'), row.get("CUSTOMER_ID"))}
            {self._optional_tag("first_name", row.get('FIRST_NAME'), row.get("CUSTOMER_ID"))}
            {self._optional_tag("last_name", row.get('LAST_NAME'), row.get("CUSTOMER_ID"))}
            {self._optional_tag("birthdate", row.get('BIRTHDATE'), row.get("CUSTOMER_ID"))}
            {self._optional_tag("birth_place", row.get('BIRTH_PLACE'), row.get("CUSTOMER_ID"))}
            {self._optional_tag("country_of_birth", country_of_birth, customer_id) if pd.notna(country_of_birth) and str(country_of_birth).strip() else ""}
            {self._cin_id_number_tag(row)}
            {self._optional_tag("nationality1", row.get('NATIONALITY'), row.get("CUSTOMER_ID"))}
            {self._optional_tag("nationality2", nationality_2, customer_id) if pd.notna(nationality_2) and str(nationality_2).strip() else ""}
            {self._optional_tag("residence", row.get('RESIDENCE'), row.get("CUSTOMER_ID"))}
            <addresses>
                <address>
                    {self._optional_tag("address_type", row.get('ADDRESS_TYPE'), row.get("CUSTOMER_ID"))}
                    {self._optional_tag("address", row.get('ADDRESS'), row.get("CUSTOMER_ID"))}
                    {self._optional_tag("town", row.get("TOWN"), row.get("CUSTOMER_ID"))}
                    {self._optional_tag("city", row.get("TOWN"), row.get("CUSTOMER_ID"))}
                    {self._optional_tag("zip", row.get('ZIP'), row.get("CUSTOMER_ID"))}
                    {self._optional_tag("country_code", row.get('COUNTRY_CODE'), row.get("CUSTOMER_ID"))}
                </address>
            </addresses>
            {self._optional_tag("occupation", row.get('OCCUPATION'), row.get("CUSTOMER_ID"))}
            <identifications>
                    {row.get("IDENTIFICATIONS_ID_SECTION")}
            </identifications>
            {f"<comments>{comments}</comments>" if comments else ""}
        </IB_person>
        """
    
    def create_xml_person_nc(self, row: Union[dict, pd.Series]) -> str:
        """
        Create a minimal XML for a person with just the name fields.
    
        Args:
            row (Union[dict, pd.Series]): The input row containing name information.
    
        Returns:
            str: The generated XML string.
        """
        return f"""
        <IB_person>
            {self._optional_tag("first_name", row.get('T_NAME'))}
            {self._optional_tag("last_name", row.get('T_NAME'))}
        </IB_person>
        """
    
    def create_xml_entity_nc(self, name: str) -> str:
        return f"""
        <IB_entity>
            <name>{name}</name>
            <entity_status>A</entity_status>
        </IB_entity>
        """