# tieout

tieout reconciles one USD nostro account for one business day. It loads an MT940 bank statement and a CSV ledger export, matches statement lines to ledger entries one-to-one, records breaks for anything left over, and prints control totals. It runs as a set of Django management commands backed by PostgreSQL.

It does not handle multiple currencies, MT942 or camt.053 files, reversal codes (`RC`/`RD`), partial or many-to-one matches, or authentication. There is no web interface.

## Setup

Requirements: Docker with the Compose plugin, and `make`.

```sh
cp .env.example .env
make up        # start PostgreSQL
make migrate   # create the schema
make test      # run the test suite
```

To run the sample day end to end:

```sh
make load      # create the account and load both files from data/
make recon     # run the reconciliation for 2026-11-02
make report    # print the control totals
make reset     # stop containers and delete the database volume
```

Any command can also be run directly:

```sh
docker compose run --rm app python manage.py <command> [options]
```

Lint and format checks use ruff:

```sh
docker compose run --rm app ruff check .
docker compose run --rm app ruff format --check .
```

## Direction convention

Statement lines use the bank's view of the account and ledger entries use ours. A statement credit (`C`) is money the bank received for us, which our books record as a debit (`D`) to cash. So a statement `C` pairs with a ledger `D`, and a statement `D` pairs with a ledger `C`. Every matching rule requires opposite directions.

Amounts are always stored as positive values with the direction in `cd`. Control totals treat `C` as positive and `D` as negative on both sides.

## Management commands

### create_account

```sh
python manage.py create_account --code NGB-USD-01 --name "Northgate Bank USD nostro" --currency USD
```

Creates the account. If an account with that code exists, it says so and changes nothing.

### load_statement

```sh
python manage.py load_statement data/statement_2026-11-02.mt940 --account NGB-USD-01
```

Parses the MT940 file and stores the statement and its lines. It prints the number of lines loaded and the opening and closing balances. The file's SHA-256 hash is stored, and loading the same file again does nothing.

Supported tags are `:20:`, `:25:`, `:28C:`, `:60F:`, `:61:`, `:86:` and `:62F:`. Any other tag, or a reversal code in `:61:`, stops the load with the offending line number. References in `:61:` are split on `//`, so a single `/` inside a reference is kept.

### load_ledger

```sh
python manage.py load_ledger data/ledger_2026-11-02.csv --account NGB-USD-01
```

Loads a UTF-8 CSV with the header `entry_ref,value_date,cd,amount,ref,narrative`. Dates are `YYYY-MM-DD` and amounts use `.` as the decimal separator. `ref` may be empty. An invalid `cd`, amount or date stops the load with the row number, and nothing from the file is saved. Rows whose `entry_ref` already exists for the account are skipped. The command prints the loaded and skipped counts.

### run_recon

```sh
python manage.py run_recon --account NGB-USD-01 --as-of 2026-11-02
```

Matches statement lines that have no match yet against ledger entries that are not flagged as matched, both with a value date on or before `--as-of`. Each pair is scored by three rules, and the highest score wins:

| Rule | Condition | Score |
| --- | --- | --- |
| `exact_amount_ref` | Equal amounts and a shared reference, compared after trimming and upper-casing | 0.99 |
| `exact_amount_date` | Equal amounts on the same value date | 0.96 |
| `amount_tolerance` | Same value date, difference within 0.5% of the ledger amount | 0.92 if equal, otherwise 0.85 |

Pairs scoring below 0.80 are dropped. The rest are sorted by score and assigned greedily, so each line and each entry is used at most once. Pairs scoring 0.95 or more are matched automatically. Pairs below that go to review. Every unassigned line and entry gets an open break. The command prints the run id, the number of lines and entries considered, and the auto, review and break counts.

### show_matches

```sh
python manage.py show_matches --run 1 [--state pending_review]
```

Lists the matches created by a run, one row per match. Each row shows the short match id, state, score, rule, the statement line reference and amount, the ledger entry reference and amount, both value dates, and both narratives. `--state` limits the list to one of `auto`, `pending_review`, `approved` or `rejected`.

### review_match

```sh
python manage.py review_match 0faeaff6 approve --by a.osei --reason "Bank deducted a 15.00 wire fee"
```

Approves or rejects a match in `pending_review`. It takes the full match id or the short id from `show_matches`. It records the reviewer, the reason and the time. It does not change ledger entry flags, statement line links or breaks. Reviewing a match in any other state is an error.

### recon_report

```sh
python manage.py recon_report --account NGB-USD-01 --as-of 2026-11-02
```

Prints four checks, each with its expected and actual totals, the difference, and `PASS` or `FAIL`:

- `statement_balance`: opening balance plus credits minus debits equals the closing balance, for the latest statement closing on or before the as-of date.
- `statement_coverage`: statement lines up to the as-of date equal the sum of cleared (`auto` or `approved`), pending (`pending_review`) and open-break lines.
- `ledger_coverage`: the same check for ledger entries.
- `ledger_flags`: ledger entries flagged `is_matched` equal the cleared ledger total.

## Sample data

`data/` holds one business day, Monday 2026-11-02, for the fictional Northgate Bank account `NGB-USD-01` (account number `0048192031`). Both files have 38 items, and 17 of the statement lines are debits. The statement balances to the cent.

- `statement_2026-11-02.mt940` is the bank statement.
- `ledger_2026-11-02.csv` is the matching ledger export.

The files contain these cases:

- 25 clean pairs with equal amounts and a shared reference. Some ledger references differ only in case or have trailing spaces.
- Two 4,500.00 receipts from different counterparties on the same day. Their ledger rows have no reference and are in the opposite order to the statement.
- Two statement lines value-dated Saturday 2026-10-31 and booked Monday 2026-11-02, with ledger entries dated 2026-11-02 and unrelated references.
- Three statement lines dated 2026-10-30 whose ledger entries are dated 2026-11-02 and whose references differ by spacing or hyphens (`INV20261029` and `inv 2026 1029`).
- Three pairs on 2026-11-02 that differ by less than 0.5%. Two are receipts with a bank fee deducted. The third pairs two unrelated counterparties with similar amounts.
- Three bank charges that appear only on the statement, and three outstanding payments that appear only in the ledger.
