# Unknown Transaction Fallback Patch

This patch changes `TransactionRouter` so that `UnknownTransaction` receives every accountant row that is not handled by the specialised modules.

Previously, only rows with an empty/missing `OP_TYPE` were sent to `UnknownTransaction`.

Now, the unknown/default handler receives:

- empty or missing `OP_TYPE` rows;
- non-empty `OP_TYPE` rows that are not one of the specialised handlers;
- rows with a known `OP_TYPE` but excluded by the specialised handler filters, such as category or app-source restrictions.

Specialised handler coverage is defined as:

- `Virement` + direct account-impact category;
- `Transfert` + direct account-impact category + `APP_SOURCE` in `Clean Payment`, `TPH`;
- `Carte` + direct account-impact category;
- `Cheque` + direct account-impact category;
- `Caisse` + direct account-impact category;
- `Effet` + direct account-impact category.

Everything outside those masks is sent to `UnknownTransaction`.

Also fixed `UnknownTransaction` so it assigns `stacked_df_unknown`; otherwise the router would not append unknown transactions to the final XML stack.
