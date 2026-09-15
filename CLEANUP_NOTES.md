# Cleanup notes

This version removes files that were not part of the active application import path.

Removed:
- Generated/sensitive `output/` files.
- Python cache folders/files: `__pycache__`, `*.pyc`.
- Jupyter checkpoint folders: `.ipynb_checkpoints`.
- Temporary Excel lock files: `~$*`.
- Dated/backup Python modules not imported by the app:
  - `src/controller/transaction_router_03_10_2025.py`
  - `src/helpers/xmlStructure copy.py`
  - `src/helpers/xmlStructure_2.py`
  - `src/helpers/xmlStructure_old.py`
  - `src/model/get_client_T24_old.py`
  - `src/model/teller-2025-12-29.py`
  - `src/model/teller_01_10_2025.py`
  - `src/model/teller_03_10_2025.py`
- Dated copies of `param_file/accountant_trx*.xlsx`; kept active `accountant_trx.xlsx`.

Conservative choices:
- Kept notebooks and `tests/` data because they may be useful for manual verification.
- Kept all active controllers/models imported by `app/1_account_transaction_xml_generator.py`.
- No functional rewrite was done in this cleanup pass.
