import os
import xml.etree.ElementTree as ET
from decimal import Decimal
 
 
def update_balances(file_name, output_path , start_balance):

    print("updating balances")
    file_path = os.path.join(output_path, file_name)
 
    tree = ET.parse(file_path)
    root = tree.getroot()
 
    current_balance = Decimal(str(start_balance))
 
    for transaction in root.findall(".//transaction"):
 
        amount_node = transaction.find(".//amount_local")
        balance_node = transaction.find(".//balance")
 
        if amount_node is None:
            print("No amount_local found")
            continue
 
        if balance_node is None:
            print("No balance found")
            continue
 
        amount = Decimal(amount_node.text)
 
        current_balance += amount
 
        balance_node.text = str(current_balance)
 
    tree.write(
        file_path,
        encoding="utf-8",
        xml_declaration=True
    )