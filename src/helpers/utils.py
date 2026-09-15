import os
from datetime import datetime
import pandas as pd
import xml.etree.ElementTree as ET
from typing import List
import re

def extract_xml_values(xml_str: str) -> List[str]:
    """
    Extract text values from an XML string.

    Args:
        xml_str (str): The input XML string.

    Returns:
        List[str]: A list of text values from the XML string.
    """
    root = ET.fromstring(f"<root>{xml_str}</root>")
    return [child.text for child in root]

def trim_all_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Trim whitespace from all string columns in a DataFrame.

    Args:
        df (pd.DataFrame): The input DataFrame.

    Returns:
        pd.DataFrame: A DataFrame with trimmed string columns.
    """
    return df.apply(lambda col: col.map(lambda val: val.strip() if isinstance(val, str) else val))

def remove_newlines_and_spaces(input_string: str) -> str:
    """
    Remove all newline characters and spaces from a string.

    Args:
        input_string (str): The input string.

    Returns:
        str: The string without newlines or spaces.
    """
    return ''.join(input_string.replace('\n', '').split())

def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean a DataFrame by trimming all string values.

    Args:
        df (pd.DataFrame): The input DataFrame.

    Returns:
        pd.DataFrame: The cleaned DataFrame.
    """
    return df.apply(lambda col: col.apply(lambda val: val.strip() if isinstance(val, str) else val))
    #return df.applymap(lambda val: clean_text(val) if isinstance(val, str) else val)
    #return df.apply(lambda col: col.apply(lambda val: clean_text(val.strip()) if isinstance(val, str) else val))

def write_transaction_details_to_xml(df: pd.DataFrame, output_path: str, file_name: str, fiu_ref_number: str = None, prev_rejected_ref_number: str = None) -> None:
    """
    Write transaction details to an XML file.

    Args:
        df (pd.DataFrame): A DataFrame containing transaction details.
        output_path (str): The directory path to save the XML file.
        file_name (str): The name of the XML file.

    Returns:
        None
    """
    # goAML schema order: entity_reference -> fiu_ref_number -> prev_rejected_ref_number -> report_date.
    # For correction/resubmission reports, CTAF may require fiu_ref_number.
    fiu_ref_xml = f"        <fiu_ref_number>{fiu_ref_number}</fiu_ref_number>\n" if fiu_ref_number else ""
    prev_rejected_xml = f"        <prev_rejected_ref_number>{prev_rejected_ref_number}</prev_rejected_ref_number>\n" if prev_rejected_ref_number else ""

    header = f"""
    <report>
        <rentity_id>30</rentity_id>
        <submission_code>E</submission_code>
        <report_code>STR</report_code>
        <entity_reference>DS19-2023</entity_reference>
{fiu_ref_xml}{prev_rejected_xml}        <report_date>2024-06-10T08:13:27</report_date>
        <currency_code_local>TND</currency_code_local>
        <reporting_user_code>atbgoamlbo</reporting_user_code>
        <location>
            <address_type>2</address_type>
            <address>9, RUE HEDI NOUIRA</address>
            <city>TUNIS</city>
            <zip>1001</zip>
            <country_code>TN</country_code>
            <state>TUNIS</state>
        </location>
        <reason>nothing</reason>
        <action>DS CTAF</action>
    """

    footer = """
        <report_indicators>
            <indicator>0529IOF</indicator>
        </report_indicators>
    </report>
    """

    # Ensure the output directory exists
    os.makedirs(output_path, exist_ok=True)
    
    file_path = os.path.join(output_path, file_name)
    
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(header + '\n')
        
        for _, row in df.iterrows():
            # Assume "transaction_detail" column exists in the DataFrame
            #processed_detail = remove_newlines_and_spaces(row['transaction_detail'])
            processed_detail = row['transaction_detail']
            file.write(f"{processed_detail}\n")
        
        file.write('\n' + footer)


#def clean_text(text):
#    text = text.replace('>', '')  # Remove '>'
#    text = re.sub(r'\s+', '-', text.strip())  # Replace multiple spaces with '-'
#    return text

def clean_text(text):
    replacements = {
        '': ['>', '<', ','],  # Remove these characters
        ' Et ': ['&']  # Replace '&' with 'Et'
    }
    
    for replacement, chars in replacements.items():
        for char in chars:
            text = text.replace(char, replacement)

    text = re.sub(r'\s+', '-', text.strip())  # Replace multiple spaces with '-'
    return text

#def parse_xml_values_by_position(input_data: str):
#    """
#    Parses XML-like input data and extracts positions and values as a list of tuples.
#
#    Args:
#        input_data (str): A string containing XML-like data.
#
#    Returns:
#        List[Tuple[int, str]]: A list of tuples with position and value.
#    """
#    # Use regex to capture values, allowing both single and double quotes for 'm'
#    # Match any alphanumeric or special characters for value
#    pattern = r"<c(\d+)(?: m=['\"](\d+)['\"])?>(.*?)</c\1>"
#    matches = re.findall(pattern, input_data)
#
#    # Create a list of tuples (position, value)
#    data = []
#    for tag, m, value in matches:
#        # Position will be m if it's present; otherwise, assign sequential position
#        position = int(m) if m else len(data) + 1
#        data.append((position, value))
#
#    # Sort data by position to ensure it's ordered correctly
#    data.sort(key=lambda x: x[0])
#
#    return data

import re
from typing import List, Tuple, Optional

def parse_xml_values_by_position(input_data: Optional[str]) -> Optional[List[Tuple[int, str]]]:
    """
    Parses XML-like input data and extracts positions and values as a list of tuples.

    Args:
        input_data (str): A string containing XML-like data.

    Returns:
        List[Tuple[int, str]]: A list of tuples with position and value, or None if input_data is None.
    """
    if input_data is None:
        return [(1, None)]  # Return None if input_data is None
    
    # Use regex to capture values, allowing both single and double quotes for 'm'
    pattern = r"<c(\d+)(?: m=['\"](\d+)['\"])?>(.*?)</c\1>"
    matches = re.findall(pattern, input_data)

    # Create a list of tuples (position, value)
    data = []
    for tag, m, value in matches:
        # Position will be m if it's present; otherwise, assign sequential position
        position = int(m) if m else len(data) + 1
        data.append((position, value))

    # Sort data by position to ensure it's ordered correctly
    data.sort(key=lambda x: x[0])

    return data


#def aggregate_legal_id_section(df):
#    # Define the function to format LEGAL_ID_SECTION based on LEGAL_DOC_NAME
#    def format_legal_id_section(group):
#        legal_id_section = []
#        for _, row in group.iterrows():
#            if row["LEGAL_DOC_NAME"] == "CIN":
#                legal_id_section.append(f"<id_number>{row['LEGAL_ID']}</id_number>")
#            elif row["LEGAL_DOC_NAME"] == "PASSPORT":
#                legal_id_section.append(
#                    f"<passport_number>{row['LEGAL_ID']}</passport_number>"
#                    f"<passport_country>{row['LEGAL_ISS_AUTH']}</passport_country>"
#                )
#        return " ".join(legal_id_section)  # Concatenate the values with a space
#    
#    # Group by CUSTOMER_ID and keep only the first row for non-aggregated columns
#    df_grouped = df.groupby("CUSTOMER_ID", as_index=False).first()
#    
#    # Apply the formatting function to each CUSTOMER_ID group and create the new column
#    df_grouped["LEGAL_ID_SECTION"] = df.groupby("CUSTOMER_ID").apply(format_legal_id_section).reset_index(drop=True)
#
#    return df_grouped

#def aggregate_legal_id_section(df):
#    print("======= fct aggregate_legal_id_section ===========")
#    print(df)
#    print("==================")
#    # Define the function to format LEGAL_ID_SECTION based on LEGAL_DOC_NAME
#    def format_legal_id_section(group):
#        legal_id_section = []
#        for _, row in group.iterrows():
#            if row["LEGAL_DOC_NAME"] == "CIN":
#                legal_id_section.append(f"<id_number>{row['LEGAL_ID']}</id_number>")
#            elif row["LEGAL_DOC_NAME"] == "PASSPORT":
#                legal_id_section.append(
#                    f"<passport_number>{row['LEGAL_ID']}</passport_number>"
#                    f"<passport_country>{row['LEGAL_ISS_AUTH']}</passport_country>"
#                )
#        return " ".join(legal_id_section)  # Concatenate the values with a space
#    
#    # Determine grouping columns
#    groupby_cols = ["CUSTOMER_ID"]
#    if "RELATED_PERSON_RELATION_CODE_ATB" in df.columns and "RELATED_PERSON_ROLE_CODE_ATB" in df.columns:
#        groupby_cols.extend(["RELATED_PERSON_RELATION_CODE_ATB", "RELATED_PERSON_ROLE_CODE_ATB"])
#    
#    # Group by dynamic columns and keep the first row for non-aggregated columns
#    df_grouped = df.groupby(groupby_cols, as_index=False).first()
#    
#    # Apply the formatting function to each group and create the new column
#    df_grouped["LEGAL_ID_SECTION"] = df.groupby(groupby_cols).apply(format_legal_id_section).reset_index(drop=True)
#
#    return df_grouped

# version 1
#def aggregate_legal_id_section(df):
#    print("======= fct aggregate_legal_id_section ===========")
#    print(df)
#    print("==================")
#    
#    # Define the function to format LEGAL_ID_SECTION based on LEGAL_DOC_NAME
#    def format_legal_id_section(group):
#        legal_id_section = []
#        for _, row in group.iterrows():
#            if row["LEGAL_DOC_NAME"] == "CIN":
#                legal_id_section.append(f"<id_number>{row['LEGAL_ID']}</id_number>")
#            elif row["LEGAL_DOC_NAME"] == "PASSPORT":
#                legal_id_section.append(
#                    f"<passport_number>{row['LEGAL_ID']}</passport_number>"
#                    f"<passport_country>{row['LEGAL_ISS_AUTH']}</passport_country>"
#                )
#        return " ".join(legal_id_section)  # Concatenate the values with a space
#
#    # Determine grouping columns
#    groupby_cols = ["CUSTOMER_ID"]
#    if "RELATED_PERSON_RELATION_CODE_ATB" in df.columns and "RELATED_PERSON_ROLE_CODE_ATB" in df.columns:
#        groupby_cols.extend(["RELATED_PERSON_RELATION_CODE_ATB", "RELATED_PERSON_ROLE_CODE_ATB"])
#    
#    # Ensure missing values in grouping columns are treated correctly
#    df[groupby_cols] = df[groupby_cols].fillna('N.A')  # Replace NaN with a placeholder
#    
#    # Group and retain all relevant rows
#    df["LEGAL_ID_SECTION"] = df.groupby(groupby_cols)[["LEGAL_DOC_NAME", "LEGAL_ID", "LEGAL_ISS_AUTH"]].apply(format_legal_id_section).reset_index(drop=True)
#    
#    return df

#Grouping by CUSTOMER_ID Only:
#
#For each unique CUSTOMER_ID, collect all rows and generate the IDENTIFICATIONS_ID_SECTION by concatenating the identification details.​
#Retain only the first row for each CUSTOMER_ID, remove the columns LEGAL_DOC_NAME, LEGAL_ID, LEGAL_ISS_AUTH, LEGAL_ISS_DATE, and LEGAL_EXP_DATE, and add the IDENTIFICATIONS_ID_SECTION column.​
#Grouping by CUSTOMER_ID, RELATED_PERSON_RELATION_CODE_ATB, and RELATED_PERSON_ROLE_CODE_ATB:
#
#For each unique combination of these columns, generate the IDENTIFICATIONS_ID_SECTION for the group.​
#Retain only the first row for each group, remove the specified columns, and add the IDENTIFICATIONS_ID_SECTION column.

# version 2
def aggregate_legal_id_section(df):
    print("======= fct aggregate_legal_id_section ===========")
    print(df)
    print("==================")
    
    # Function to format IDENTIFICATIONS_ID_SECTION based on LEGAL_DOC_NAME
    def format_identifications_id_section(group):
        identifications = []
        for _, row in group.iterrows():
            doc_type = "B" if row["LEGAL_DOC_NAME"] == "CIN" else "C" if row["LEGAL_DOC_NAME"] == "PASSPORT" else "D"
            identification = (
                f"<identification>"
                f"<type>{doc_type}</type>"
                f"<number>{row['LEGAL_ID']}</number>"
                f"<issue_date>{row['LEGAL_ISS_DATE']}</issue_date>"
            )
            # Include expiry_date if LEGAL_DOC_NAME is 'CS' or 'PASSPORT'
            if row["LEGAL_DOC_NAME"] in ["CS", "PASSPORT"]:
                identification += f"<expiry_date>{row['LEGAL_EXP_DATE']}</expiry_date>"
            identification += f"<issue_country>{row['LEGAL_ISS_AUTH']}</issue_country>"
            identification += "</identification>"
            identifications.append(identification)
        return " ".join(identifications)
    
    # Determine grouping columns
    groupby_cols = ["CUSTOMER_ID"]
    if "RELATED_PERSON_RELATION_CODE_ATB" in df.columns and "RELATED_PERSON_ROLE_CODE_ATB" in df.columns:
        groupby_cols.extend(["RELATED_PERSON_RELATION_CODE_ATB", "RELATED_PERSON_ROLE_CODE_ATB"])
    
    # Ensure missing values in grouping columns are treated correctly
    df[groupby_cols] = df[groupby_cols].fillna('N.A')
    
    # Compute IDENTIFICATIONS_ID_SECTION for each group
    aggregated_df = df.groupby(groupby_cols).apply(lambda group: pd.Series({
        "IDENTIFICATIONS_ID_SECTION": format_identifications_id_section(group)
    })).reset_index()
    
    # Drop duplicate rows based on grouping columns and merge with aggregated data
    df = df.drop_duplicates(subset=groupby_cols).merge(aggregated_df, on=groupby_cols, how='left')
    
    # Remove specified columns
    df = df.drop(columns=["LEGAL_DOC_NAME", "LEGAL_ID", "LEGAL_ISS_AUTH", "LEGAL_ISS_DATE", "LEGAL_EXP_DATE"], errors='ignore')
    
    return df


# Function to format date from yyyymmdd to yyyy-mm-ddT00:00:00
def format_date(date_str, customer_id):
    """
    Formats a date string from 'yyyymmdd' to 'yyyy-mm-ddT00:00:00'.
    If the input is invalid or empty, returns 'N.A - CUSTOMER_ID'.
    """
    if date_str and len(date_str) == 8:
        try:
            formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}T00:00:00"
            return formatted_date
        except ValueError:
            return f'CUSTOMER_ID: {customer_id} - N.A'
    else:
        return f'CUSTOMER_ID: {customer_id} - N.A'

# Function to parse the fields and construct the XML
def construct_identification(row):
    """
    Parses identification fields and constructs XML segments for each identification entry.
    """
    # Split the fields based on the '::' delimiter
    legal_doc_names = row['LEGAL_DOC_NAME'].split('::')
    legal_ids = row['LEGAL_ID'].split('::')
    legal_iss_auths = row['LEGAL_ISS_AUTH'].split('::')
    legal_iss_dates = row['LEGAL_ISS_DATE'].split('::')
    legal_exp_dates = row['LEGAL_EXP_DATE'].split('::')

    # Determine the number of identification entries
    num_entries = max(len(legal_doc_names), len(legal_ids), len(legal_iss_auths), len(legal_iss_dates), len(legal_exp_dates))

    # Map document type codes to their respective values
    doc_type_mapping = {
        'CS': '3SEJ',
        'CARTESEJ': '3SEJ',
        'CIN': 'B',
        'PASSEPORT': 'C',
        'PASSPETRG': 'C' # Other 'MF', 'MATRFISC' -> D (Autre)
    }

    # Construct XML segments for each identification entry
    xml_segments = []
    for i in range(num_entries):
        doc_type_code = legal_doc_names[i] if i < len(legal_doc_names) and legal_doc_names[i] else f'CUSTOMER_ID: {row["CUSTOMER_ID"]} - N.A'
        id_number = legal_ids[i] if i < len(legal_ids) and legal_ids[i] else f'CUSTOMER_ID: {row["CUSTOMER_ID"]} - N.A'
        issue_country = legal_iss_auths[i] if i < len(legal_iss_auths) and legal_iss_auths[i] else f'CUSTOMER_ID: {row["CUSTOMER_ID"]} - N.A'
        issue_date = format_date(legal_iss_dates[i], row["CUSTOMER_ID"]) if i < len(legal_iss_dates) and legal_iss_dates[i] else f'CUSTOMER_ID: {row["CUSTOMER_ID"]} - N.A'
        expiry_date = format_date(legal_exp_dates[i], row["CUSTOMER_ID"]) if i < len(legal_exp_dates) and legal_exp_dates[i] else f'CUSTOMER_ID: {row["CUSTOMER_ID"]} - N.A'

        doc_type = doc_type_mapping.get(doc_type_code, 'D')

        xml_parts = [
            '<identification>',
            f'    <type>{doc_type}</type>',
            f'    <number>{id_number}</number>',
            f'    <issue_date>{issue_date}</issue_date>',
            f'    <issue_country>{issue_country}</issue_country>'
        ]

        # Include the expiry_date only for 'CS' or 'PASSEPORT'
        if doc_type_code in ['CS', 'PASSEPORT']:
            xml_parts.insert(-1, f'    <expiry_date>{expiry_date}</expiry_date>')

        xml_parts.append('</identification>')

        xml_segments.append('\n'.join(xml_parts))

    return '\n'.join(xml_segments)








