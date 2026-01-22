# Session Technical Changes Log

This document summarizes all file modifications made during the current development session. It details **what** was changed, **why**, and the specific **issues fixed**.

## 1. Core Engine (`bi_engine.py`)

### **Changes**

- **Architecture**: Implemented a **Structured Query Planning** system using Pydantic models (`QueryPlan`, `AvailabilityPlan`, `TeamPlan`).
- **Logic**: Replaced loose string matching with strict heuristic and deterministic LLM planners (`plan_question`, `_heuristic_plan`).
- **Serialization**: Added `_serialize_for_json` method to handle Neo4j time objects (`Date`, `DateTime`) before passing them to the LLM.
- **Privacy**: **Removed** `_anonymize_data` and the `decoder_map` logic. The engine now returns real candidate names by default.
- **Features**: Added "What-If" simulator (`simulate_scenario`) and "Risk Assessment" (SPOF) logic.

### **Why / Fixes**

- **Fixes JSON Errors**: Prevents `TypeError: Object of type Date is not JSON serializable` when the LLM tries to summarize temporal data from Neo4j.
- **Fixes Benchmark Confusion**: Removing privacy masking fixes the issue where benchmark scripts couldn't match "Candidate_X" to "Jacob Young", ensuring accurate correctness scoring.
- **Fixes Logic Stability**: The new `QueryPlan` ensures that complex queries (e.g., "Senior Python Devs available next month") are parsed into structured filters rather than relying on unstable generated Cypher.

---

## 2. Benchmarks (`benchmarks/`)

### A. System Comparison (`benchmarks/5_compare_systems.py`)

- **What**:
  - Synced response parsing to match the new `bi_engine` output structure.
  - Removed `decoder_map` lookup (since names are now real).
  - Added CSV export and statistical summary (Average, P95 latency).
- **Fix**: Resolves `KeyError` crashes when the script tried to access non-existent `decoder_map` keys. Enables proper persistent logging of results.

### B. Stress Test (`benchmarks/6_stress_test_scalability.py`)

- **What**:
  - Computed `needed` nodes dynamically before injection.
  - **Optimization**: Refactored the Cypher `CREATE` statement to be atomic. Instead of creating a node and then setting properties (which could trigger constraint violations), it now clones properties and assigns a unique ID in a single map projection: `SET new_p = p {.*, id: ...}`.
- **Fix**: Resolves `ConstraintValidationFailed` errors in Neo4j during high-volume synthetic data injection.

### C. Ragas Evaluation (`benchmarks/9_evaluate_metrics.py`)

- **What**:
  - Fixed attribute access: changed `naive_system.vector_store` to `naive_system.vectorstore`.
  - Removed `decoder_map` name reconstruction logic.
  - Added necessary imports for `ragas` and `datasets`.
- **Fix**:
  - Fixes `AttributeError` preventing the script from retrieving context documents.
  - Fixes `ModuleNotFoundError` for Ragas framework components.

### D. Visualization (`benchmarks/10_visualize_results.py`)

- **What**:
  - Updated file path handling to use `os.path.abspath(__file__)` and `os.path.join`.
- **Fix**: Fixes `FileNotFoundError` when running the script from the project root instead of the `benchmarks/` directory.

---

## 3. Dependencies (`requirements.txt`)

### **Changes**

- Added `ragas>=0.1.0`.
- Added `datasets>=2.14.0`.
- Added `openpyxl>=3.1.2` (for Excel export capability).

### **Why / Fixes**

- **Fix**: Ensures the environment supports Script 9 (Metric Evaluation) and other data export features required for the final report.

---

## 4. Utility Scripts (`0_init_schema.py`, `validate_graph.py`)

### **Changes**

- Restored/Created `0_init_schema.py` to enforce Unique Constraints on `p.id`.
- Restored/Created `validate_graph.py` to check for orphaned nodes and invalid allocations.

### **Why / Fixes**

- **Fix**: Ensures database integrity before running expensive benchmarks. Prevents "duplicate node" errors by enforcing uniqueness at the database level.

---

## 5. Data Pipeline & Team Matching (`1_generate_data.py`, `2b_ingest_projects.py`, `3_match_team.py`)

### A. Data Generation (`1_generate_data.py`)

- **What**:
  - Added logic to generate **Certifications** (Scenario 5 requirement).
  - Added extraction of **Projects** from CV text and creation of `WORKED_ON` relationships.
- **Why**: Supports "Find certified candidates" and "Find candidates with specific project history" queries.

### B. Project Ingestion (`2b_ingest_projects.py`)

- **What**:
  - Defined explicit `PROJECTS_DATA` with `end_days`.
  - Added specific `start_date` and `end_date` properties to generated projects.
  - Implemented a "load profile" (Busy vs Partial vs Bench) to ensure realistic availability testing.
- **Why**:
  - Fixes **Temporal Queries** ("Available next month") by providing concrete project end dates for `bi_engine.py` to query against.
  - Ensures specific `allocation_percentage` (1.0 vs 0.5) is set for accurate capacity calculations.

### C. Team Matcher (`3_match_team.py`)

- **What**:
  - **Refactored Node Creation**: Separated `RFP` nodes and `Project` nodes, linking them via `CREATES`.
  - **Enhanced Parsing**: Improved LLM extraction to capture `budget`, `deadline`, and `duration_months`.
  - **Simulation Mode**: Added support for `simulate_only=True` to run matching logic without writing to the DB.
  - **Date Logic**: switched to strict `date()` objects for `start_date`/`end_date` to match the core engine's data model.
- **Why**:
  - Aligns the ingestion process with the new `bi_engine` schema (Budget, Dates, structured IDs).
  - Prevents "phantom" projects from cluttering the database during dry runs.
