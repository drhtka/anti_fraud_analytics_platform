Place large IEEE-CIS CSV files here using the following structure:

- preferred: `data/raw/train_transaction.csv`
- preferred: `data/raw/train_identity.csv`
- fallback: `data/train_transaction.csv`
- fallback: `data/train_identity.csv`

Why `data/raw/`:

- keeps raw source files separate from future processed outputs;
- makes the project structure easier to read;
- avoids mixing heavy CSV files with notes or derived artifacts.

The UI reads these files on the backend through DuckDB and only sends
small summaries, limited tables, and generated charts to the browser.
