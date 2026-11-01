from sqlalchemy import create_engine,text
DDL='''CREATE SCHEMA IF NOT EXISTS algotrd_data;
CREATE TABLE IF NOT EXISTS algotrd_data.instruments (instrument_id text PRIMARY KEY, exchange text NOT NULL, asset_class text NOT NULL, underlying_symbol text, valid_from date, valid_until date, tick_size numeric, expiry_date date, strike_price numeric, option_type text, lot_size integer, contract_multiplier numeric, metadata_source text, metadata_verified_at timestamptz);
CREATE TABLE IF NOT EXISTS algotrd_data.provider_instrument_mappings (provider text NOT NULL, provider_symbol text NOT NULL, instrument_id text NOT NULL REFERENCES algotrd_data.instruments(instrument_id), segment text, valid_from date, valid_until date, PRIMARY KEY(provider,provider_symbol));
CREATE TABLE IF NOT EXISTS algotrd_data.ingestion_jobs (job_id text PRIMARY KEY, provider text, instrument_id text, status text, started_at timestamptz, completed_at timestamptz, attempts integer, error_classification text);
CREATE TABLE IF NOT EXISTS algotrd_data.data_partitions (partition_id bigserial PRIMARY KEY, path text UNIQUE NOT NULL, instrument_id text, row_count bigint, checksum text, schema_version text, validation_status text, start_at timestamptz, end_at timestamptz, file_size bigint, lineage jsonb);
CREATE TABLE IF NOT EXISTS algotrd_data.data_quality_reports (report_id bigserial PRIMARY KEY, instrument_id text, dataset_version text, report jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS algotrd_data.dataset_versions (dataset_version text PRIMARY KEY, status text NOT NULL, schema_version text, manifest jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), published_at timestamptz);
CREATE TABLE IF NOT EXISTS algotrd_data.dataset_version_partitions (dataset_version text REFERENCES algotrd_data.dataset_versions(dataset_version), partition_id bigint REFERENCES algotrd_data.data_partitions(partition_id), checksum text, PRIMARY KEY(dataset_version,partition_id));
CREATE TABLE IF NOT EXISTS algotrd_data.market_sessions (exchange text, trading_date date, opens_at timestamptz, closes_at timestamptz, session_type text, reference_source text, verified boolean NOT NULL DEFAULT false, PRIMARY KEY(exchange,trading_date));'''
def inspect(url):
 e=create_engine(url)
 with e.connect() as c:return [r[0] for r in c.execute(text("SELECT schemaname||'.'||tablename FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema') ORDER BY 1"))]
def migrate(url):
 e=create_engine(url)
 with e.begin() as c:
  for s in DDL.split(';'):
   if s.strip(): c.execute(text(s))
