"""
Automated Test Suite for Trade Operations Intelligence Platform
==============================================================
Validates:
- Database initialization and schema creation
- Idempotent data ingestion without duplicate records
- Primary key uniqueness & foreign key referential integrity
- Grain-accurate KPI calculations (Trade failure rate, attempt failure rate, SLA breach rate)
- One-to-many join handling (avoiding trade double counting)
- Exception multi-factor priority scoring formula
- SLA calculation and breach flag accuracy
- Error handling on missing raw input files
- Safe operational summary and validation report generation
"""

import os
import sys
import unittest
import tempfile
import sqlite3
from pathlib import Path

import pandas as pd
import numpy as np

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from app import DatabaseManager, DataValidator, AnalyticsEngine, PrioritizationEngine


class TestTradeOperationsPlatform(unittest.TestCase):
    """Unit and Integration tests for the Trade Operations platform."""

    @classmethod
    def setUpClass(cls):
        """Set up live production database manager and engines for integration checks."""
        cls.live_db_manager = DatabaseManager()
        cls.live_analytics = AnalyticsEngine(cls.live_db_manager)
        cls.live_prioritizer = PrioritizationEngine(cls.live_db_manager)
        cls.live_validator = DataValidator(cls.live_db_manager)

    def setUp(self):
        """Create an isolated temporary database for safe destructive unit testing."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_db_path = Path(self.temp_dir.name) / "test_trade_ops.db"
        self.test_db_manager = DatabaseManager(db_path=self.temp_db_path)

    def tearDown(self):
        """Clean up temporary test directory."""
        import gc
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # 1. Database Initialization & Schema Tests
    # -------------------------------------------------------------------------
    def test_database_initialization(self):
        """Test that schema initializes all required tables and indexes."""
        self.test_db_manager.init_schema(rebuild=True)
        self.assertTrue(self.temp_db_path.exists())

        expected_tables = {
            "trades", "settlements", "exceptions", "counterparties",
            "instruments", "known_data_quality_issues", "data_dictionary"
        }
        conn = self.test_db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = {row[0] for row in cursor.fetchall()}
        finally:
            conn.close()

        self.assertTrue(expected_tables.issubset(tables), f"Missing tables: {expected_tables - tables}")

    # -------------------------------------------------------------------------
    # 2. Ingestion & Idempotence Tests
    # -------------------------------------------------------------------------
    def test_idempotent_ingestion(self):
        """Verify that repeated ingestion loads all data and does not duplicate records."""
        # First ingestion
        counts1 = self.test_db_manager.ingest_data(force_rebuild=False)
        self.assertEqual(counts1["trades"], 50000)
        self.assertEqual(counts1["settlements"], 52385)
        self.assertEqual(counts1["exceptions"], 5060)

        # Second ingestion (idempotent run)
        counts2 = self.test_db_manager.ingest_data(force_rebuild=False)
        self.assertEqual(counts2["trades"], 50000)
        self.assertEqual(counts2["settlements"], 52385)
        self.assertEqual(counts2["exceptions"], 5060)

        # Confirm database counts match exactly
        db_counts = self.test_db_manager.get_table_counts()
        self.assertEqual(db_counts["trades"], 50000)
        self.assertEqual(db_counts["settlements"], 52385)
        self.assertEqual(db_counts["exceptions"], 5060)

    # -------------------------------------------------------------------------
    # 3. Primary Key & Referential Integrity Tests
    # -------------------------------------------------------------------------
    def test_primary_key_uniqueness(self):
        """Verify that primary keys in all loaded tables are 100% unique."""
        with self.live_db_manager.get_connection() as conn:
            cursor = conn.cursor()
            pk_map = {
                "trades": "trade_id",
                "settlements": "settlement_id",
                "exceptions": "exception_id",
                "counterparties": "counterparty_id",
                "instruments": "instrument_id"
            }
            for table, pk in pk_map.items():
                cursor.execute(f"SELECT COUNT({pk}) - COUNT(DISTINCT {pk}) FROM {table};")
                duplicates = cursor.fetchone()[0]
                self.assertEqual(duplicates, 0, f"Found {duplicates} duplicate keys in {table}.{pk}")

    def test_foreign_key_integrity(self):
        """Verify referential integrity across all relationships."""
        with self.live_db_manager.get_connection() as conn:
            cursor = conn.cursor()
            # 1. Trades -> Instruments
            cursor.execute("""
                SELECT COUNT(*) FROM trades t
                LEFT JOIN instruments i ON t.instrument_id = i.instrument_id
                WHERE i.instrument_id IS NULL;
            """)
            self.assertEqual(cursor.fetchone()[0], 0, "Found orphaned trades.instrument_id")

            # 2. Trades -> Counterparties
            cursor.execute("""
                SELECT COUNT(*) FROM trades t
                LEFT JOIN counterparties c ON t.counterparty_id = c.counterparty_id
                WHERE c.counterparty_id IS NULL;
            """)
            self.assertEqual(cursor.fetchone()[0], 0, "Found orphaned trades.counterparty_id")

            # 3. Settlements -> Trades
            cursor.execute("""
                SELECT COUNT(*) FROM settlements s
                LEFT JOIN trades t ON s.trade_id = t.trade_id
                WHERE t.trade_id IS NULL;
            """)
            self.assertEqual(cursor.fetchone()[0], 0, "Found orphaned settlements.trade_id")

            # 4. Exceptions -> Trades
            cursor.execute("""
                SELECT COUNT(*) FROM exceptions e
                LEFT JOIN trades t ON e.trade_id = t.trade_id
                WHERE t.trade_id IS NULL;
            """)
            self.assertEqual(cursor.fetchone()[0], 0, "Found orphaned exceptions.trade_id")

    # -------------------------------------------------------------------------
    # 4. KPI & Analytical Correctness Tests
    # -------------------------------------------------------------------------
    def test_executive_kpi_calculation(self):
        """Test accuracy of executive headline KPIs and grain denominators."""
        kpis = self.live_analytics.get_executive_kpis()
        self.assertEqual(kpis["total_trades"], 50000)
        self.assertGreater(kpis["total_notional"], 0)

        # Trade fail rate must equal failed / (settled + failed)
        completed = kpis["settled_trades"] + kpis["failed_trades"]
        expected_trade_fail_rate = (kpis["failed_trades"] / completed) * 100.0
        self.assertAlmostEqual(kpis["trade_fail_rate"], expected_trade_fail_rate, places=2)

        # Settlement attempt fail rate
        self.assertGreater(kpis["total_attempts"], 0)
        self.assertGreaterEqual(kpis["attempt_fail_rate"], 0.0)

        # SLA breach rate between 10% and 30%
        self.assertTrue(10.0 <= kpis["sla_breach_rate"] <= 30.0, f"SLA breach rate {kpis['sla_breach_rate']}% out of expected range")

    def test_one_to_many_join_no_double_counting(self):
        """Ensure joins from trades to settlements and exceptions do not inflate trade counts."""
        with self.live_db_manager.get_connection() as conn:
            cursor = conn.cursor()
            # Distinct trades
            cursor.execute("SELECT COUNT(DISTINCT trade_id) FROM trades;")
            distinct_trades = cursor.fetchone()[0]

            # In joined query with aggregations
            cursor.execute("""
                SELECT COUNT(DISTINCT t.trade_id)
                FROM trades t
                LEFT JOIN settlements s ON t.trade_id = s.trade_id
                LEFT JOIN exceptions e ON t.trade_id = e.trade_id;
            """)
            joined_distinct_trades = cursor.fetchone()[0]
            self.assertEqual(distinct_trades, joined_distinct_trades)
            self.assertEqual(distinct_trades, 50000)

    # -------------------------------------------------------------------------
    # 5. Exception Prioritization Logic Tests
    # -------------------------------------------------------------------------
    def test_exception_prioritization_scoring(self):
        """Test multi-factor priority scoring formula and ordering."""
        df_prio = self.live_prioritizer.compute_prioritized_exceptions(limit=50)
        self.assertFalse(df_prio.empty)

        # Scores must be descending
        scores = df_prio["priority_score"].tolist()
        self.assertEqual(scores, sorted(scores, reverse=True))

        # Check priority bands are assigned
        self.assertTrue(set(df_prio["priority_band"].unique()).issubset({
            "P1 - CRITICAL", "P2 - HIGH", "P3 - MEDIUM", "P4 - LOW"
        }))

        # Highest score must be >= 75
        self.assertGreaterEqual(scores[0], 75.0)

    # -------------------------------------------------------------------------
    # 6. Lifecycle Consistency & SLA Calculations
    # -------------------------------------------------------------------------
    def test_settlement_lifecycle_consistency(self):
        """Verify that SETTLED trades have settlement dates and FAILED trades do not."""
        with self.live_db_manager.get_connection() as conn:
            cursor = conn.cursor()
            # SETTLED trades must have actual settlement date
            cursor.execute("""
                SELECT COUNT(*) FROM trades 
                WHERE settlement_status = 'SETTLED' AND (actual_settlement_date IS NULL OR actual_settlement_date = '');
            """)
            self.assertEqual(cursor.fetchone()[0], 0)

            # FAILED / PENDING trades must have null actual settlement date
            cursor.execute("""
                SELECT COUNT(*) FROM trades 
                WHERE settlement_status IN ('FAILED', 'PENDING') AND (actual_settlement_date IS NOT NULL AND actual_settlement_date != '');
            """)
            self.assertEqual(cursor.fetchone()[0], 0)

    def test_sla_breach_calculation(self):
        """Verify deterministic calculation of sla_breached."""
        with self.live_db_manager.get_connection() as conn:
            cursor = conn.cursor()
            # Verify resolved exceptions where elapsed hours > target have sla_breached = True
            cursor.execute("""
                SELECT COUNT(*) FROM exceptions
                WHERE resolution_status = 'RESOLVED'
                  AND (strftime('%s', resolved_at_utc) - strftime('%s', opened_at_utc)) / 3600.0 > sla_target_hours
                  AND (sla_breached = 0 OR sla_breached = 'FALSE');
            """)
            self.assertEqual(cursor.fetchone()[0], 0, "Found resolved exceptions that exceeded SLA but were not flagged as breached")

    # -------------------------------------------------------------------------
    # 7. Error Handling & Edge Cases
    # -------------------------------------------------------------------------
    def test_missing_files_error_handling(self):
        """Test that DatabaseManager handles missing raw files gracefully without crashing."""
        fake_raw_dir = Path(self.temp_dir.name) / "non_existent_raw"
        mgr = DatabaseManager(raw_dir=fake_raw_dir)
        exists, missing = mgr.check_raw_files_exist()
        self.assertFalse(exists)
        self.assertGreater(len(missing), 0)

        with self.assertRaises(FileNotFoundError):
            mgr.ingest_data()

    def test_safe_report_generation(self):
        """Test that operational summary and validation report can be generated without error."""
        summary_path = Path(self.temp_dir.name) / "test_summary.csv"
        df_sum = self.live_prioritizer.generate_operational_summary_file(output_path=summary_path)
        self.assertTrue(summary_path.exists())
        self.assertGreater(len(df_sum), 0)

        val_report_path = Path(self.temp_dir.name) / "test_val_report.txt"
        val_results = self.live_validator.run_full_validation()
        self.live_validator.write_validation_report_file(val_results, output_path=val_report_path)
        self.assertTrue(val_report_path.exists())
        self.assertEqual(val_results["overall_status"], "PASSED")


def run_tests():
    """Runs the test suite and prints formatted results."""
    suite = unittest.TestLoader().loadTestsFromTestCase(TestTradeOperationsPlatform)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
