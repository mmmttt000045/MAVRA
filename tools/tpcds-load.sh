#!/usr/bin/env bash
# Load dsdgen-generated TPC-DS data into a PostgreSQL template database (`replay-bench --schema tpcds`).
#
# Usage: MAVRA_DB_URL=postgres://user:pass@host:port/db tools/tpcds-load.sh DATA_DIR DDL_FILE [DBNAME]
#   DATA_DIR  Output of `dsdgen -scale 1 -dir DATA_DIR -terminate n` (*.dat, pipe-delimited, no trailing delimiter)
#   DDL_FILE  `tools/tpcds.sql` from tpcds-kit
#   DBNAME    Template database name (default: tpcds_sf1; dropped and recreated if present)
#
# Representation-only adjustments relative to official DDL (preserving query semantics):
#   1. Replace primary keys on the six sales/returns fact tables with non-unique indexes so update scenarios
#      (status log, duplicate load, backup mirror) can insert duplicate keys; dimension primary keys stay intact.
#   2. Widen decimal(7,2) to numeric(12,2) so unit-scale perturbations (x100) do not overflow.
set -euo pipefail
dir=$1
ddl=$2
name=${3:-tpcds_sf1}
url=${MAVRA_DB_URL:-${AGENTDB_URL:?MAVRA_DB_URL (or AGENTDB_URL) not set}}
base=${url%/*}
admin="$base/postgres"
db="$base/$name"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

python3 - "$ddl" "$work/ddl.sql" <<'PY'
import re, sys
src, dst = sys.argv[1:3]
text = open(src, encoding="utf-8", errors="replace").read()
text = re.sub(r"--.*", "", text)
text = re.sub(r"decimal\(7,2\)", "numeric(12,2)", text)
facts = "ss_item_sk, ss_ticket_number|sr_item_sk, sr_ticket_number|cs_item_sk, cs_order_number|cr_item_sk, cr_order_number|ws_item_sk, ws_order_number|wr_item_sk, wr_order_number"
text, n = re.subn(r",\s*primary key \((" + facts + r")\)", "", text)
assert n == 6, f"expected 6 fact-table primary keys, removed {n}"
open(dst, "w", encoding="utf-8").write(text)
PY

psql -X -q -v ON_ERROR_STOP=1 "$admin" -c "drop database if exists $name" -c "create database $name"
psql -X -q -v ON_ERROR_STOP=1 "$db" -f "$work/ddl.sql"

for f in "$dir"/*.dat; do
  t=$(basename "$f" .dat)
  if ! psql -X -tA "$db" -c "select 1 from information_schema.tables where table_schema = 'public' and table_name = '$t'" | grep -q 1; then
    echo "skip $t (no table)"; continue
  fi
  echo "load $t"
  # dsdgen -terminate n omits trailing pipe delimiters
  psql -X -q -v ON_ERROR_STOP=1 "$db" -c "\\copy $t from '$f' with (format text, delimiter '|', null '')"
done

psql -X -q -v ON_ERROR_STOP=1 "$db" <<'SQL'
create index on store_sales (ss_item_sk, ss_ticket_number);
create index on store_sales (ss_sold_date_sk);
create index on store_returns (sr_item_sk, sr_ticket_number);
create index on store_returns (sr_returned_date_sk);
create index on catalog_sales (cs_item_sk, cs_order_number);
create index on catalog_sales (cs_sold_date_sk);
create index on catalog_returns (cr_item_sk, cr_order_number);
create index on catalog_returns (cr_returned_date_sk);
create index on web_sales (ws_item_sk, ws_order_number);
create index on web_sales (ws_sold_date_sk);
create index on web_returns (wr_item_sk, wr_order_number);
create index on web_returns (wr_returned_date_sk);
analyze;
SQL
psql -X -tA "$db" -c "select relname, n_live_tup from pg_stat_user_tables where n_live_tup > 0 order by n_live_tup desc" | head -30
echo "template database $name ready"
