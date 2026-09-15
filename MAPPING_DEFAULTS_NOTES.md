# Configurable goAML Mapping Defaults

Missing goAML mapping fields are no longer allowed to become `nan` in the generated XML.

When `TRANSACTION_CODE_GOAML`, `FUND_CODE_1`, or `FUND_CODE_2` is missing after the merge with `param_file/accountant_trx.xlsx`, the router now fills the missing values from `param_file/default.txt`:

```text
DEFAULT_TRANSACTION_CODE_GOAML=B999
DEFAULT_FUND_CODE_1=A
DEFAULT_FUND_CODE_2=A
```

The generated rows are marked with:

```text
GOAML_MAPPING_FALLBACK_USED=Y
```

A review file is exported to:

```text
output/<account>/<account>_missing_goaml_mapping_defaults_applied_<year>.xlsx
```

Important: these defaults keep XML generation running and prevent invalid `nan` values, but they should be reviewed before official submission. The preferred long-term fix is still to complete `param_file/accountant_trx.xlsx`.
