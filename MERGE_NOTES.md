# Cleaned + XML Patch Merge Notes

This package is based on the cleaned project copy and includes the XML/goAML fixes from the earlier patch pass.

Included fixes:
- `src/helpers/xmlStructure.py`: safer optional XML tag handling; prevents `None`, `NaN`, empty strings and string `nan` values from being written as XML values; adds CIN-based `<id_number>` support where implemented.
- `src/controller/transaction_router.py`: checks for missing goAML transaction/fund mappings after parameter-file merge and blocks generation when mappings are missing.
- `src/helpers/utils.py`: adds `fiu_ref_number` and `prev_rejected_ref_number` support in report header generation.
- `tools/validate_goaml_xml.py`: utility script for XML/XSD validation.

Cleanup retained:
- old/dated duplicate modules removed from the cleaned pass.
- generated outputs/cache folders removed in this merged package.

Recommended next step:
- run the app on a test account, regenerate XML, then validate it with `tools/validate_goaml_xml.py` using the provided XSD.
