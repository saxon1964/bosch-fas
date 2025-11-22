# Multi-Manufacturer Vehicle Data Extraction System

An industrial-grade system for tracking vehicle technical specifications across multiple manufacturers. Designed to detect **new models between runs** and generate actionable reports for spare parts compatibility analysis.

## 🎯 Primary Goal

**Detect new vehicle models every month** across 50+ manufacturers so your team can evaluate spare parts compatibility.

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Monthly Extraction Run                       │
└────────────┬────────────────────────────────────┬───────────────┘
             │                                    │
   ┌─────────▼──────────┐              ┌─────────▼──────────┐
   │  Multi-Manufacturer │              │   Change Detection  │
   │      Crawler        │              │  (Fingerprinting)   │
   │   (NO AI - FREE)    │              │   Content-based ID  │
   └─────────┬──────────┘              └─────────┬──────────┘
             │                                    │
   ┌─────────▼──────────┐              ┌─────────▼──────────┐
   │   Discovered URLs   │─────────────▶│   NEW vs EXISTING  │
   │  (Pattern Matching) │              │    Classification   │
   └──────────────────────┘             └─────────┬──────────┘
                                                   │
                                         ┌─────────▼──────────┐
                                         │  Extract Only NEW  │
                                         │   (AI - Minimal)   │
                                         └─────────┬──────────┘
                                                   │
                                         ┌─────────▼──────────┐
                                         │  Generate Reports  │
                                         │ (Excel + JSON)     │
                                         └────────────────────┘
```

## 📁 Project Structure

```
fas/
│
├── 📋 config/
│   └── manufacturers.yaml           # ★ Configuration for all manufacturers
│       # Define: root URLs, patterns, anti-patterns, crawl depth
│
├── 💾 data/                         # ★ All data stored here
│   ├── tracking.db                  # SQLite: track URLs, fingerprints, timeline
│   │
│   ├── archive/                     # ★ MASTER COLLECTION (all models ever)
│   │   ├── bmw/
│   │   │   ├── bmw_ix_xdrive50_2024.json
│   │   │   ├── bmw_3er_330e_2024.json
│   │   │   └── ... (all BMW models)
│   │   ├── mercedes/
│   │   ├── audi/
│   │   └── ... (50 manufacturers)
│   │
│   └── runs/                        # ★ MONTHLY REPORTS
│       ├── 2024-01-15_INITIAL/
│       │   ├── 📊 INITIAL_DISCOVERY.xlsx    # All 2,500 models
│       │   ├── summary.json
│       │   └── extracted/
│       │       ├── bmw/*.json
│       │       └── mercedes/*.json
│       │
│       ├── 2024-02-15/
│       │   ├── 📊 NEW_MODELS.xlsx           # ★ 15 new models
│       │   ├── 📊 URL_CHANGES.xlsx          # 3 URL changes
│       │   ├── summary.json
│       │   └── extracted/
│       │       └── bmw/
│       │           ├── bmw_ix5_xdrive40_2024.json
│       │           └── ... (only new models)
│       │
│       ├── 2024-05-15/
│       │   ├── 📊 NEW_MODELS.xlsx           # 5 new models (existing mfr)
│       │   ├── 📊 NEW_MANUFACTURER_VW.xlsx  # 85 models (VW baseline)
│       │   └── ...
│       │
│       └── 2024-06-15/
│           └── ...
│
├── 🐍 src/                          # Source code (will be implemented)
│   ├── crawler.py                   # Multi-manufacturer crawler
│   ├── extractor.py                 # AI-powered extraction
│   ├── fingerprint.py               # Content-based vehicle identification
│   ├── change_detector.py           # Detect new/changed/disappeared models
│   ├── report_generator.py          # Generate Excel reports
│   └── database.py                  # SQLite operations
│
├── 🔧 scripts/                      # Runnable scripts
│   ├── run_monthly.py               # ★ MAIN: Monthly extraction run
│   └── test_api_key.py              # Validate Anthropic API key
│
├── 📚 Core files
│   ├── technical_data_schema.py     # ✅ Schema definition (100+ fields)
│   ├── requirements.txt             # Python dependencies
│   ├── .env.example                 # API key template
│   ├── .gitignore                   # Git ignore rules
│   └── README.md                    # This file
│
└── ♻️ Reusable code (to be refactored into src/)
    ├── smart_crawler.py             # Pattern-based crawler → src/crawler.py
    ├── extract_technical_data.py    # AI extractor → src/extractor.py
    └── retry_failed.py              # JSON parser → integrated into extractor
```

## 🔧 Configuration

### manufacturers.yaml

All manufacturer settings in one place:

```yaml
extraction_settings:
  delay_between_urls_seconds: 10      # Throttling
  delay_between_manufacturers_seconds: 30
  max_retries: 3
  daily_token_limit: 1000000

manufacturers:
  - name: BMW
    slug: bmw
    root_url: https://www.bmw.de
    crawl_settings:
      start_urls:
        - https://www.bmw.de/de/neufahrzeuge
      max_depth: 5
      patterns:
        - "*technische-daten*"
      anti_patterns:
        - "*about*"
        - "*support*"
        - "*dealer*"
```

**To add a new manufacturer:** Copy the BMW block and adjust URLs/patterns.

## 🚀 Usage (After Implementation)

### Monthly Run

```bash
# One command does everything:
python scripts/run_monthly.py

# What it does:
# 1. Crawl all manufacturers (FREE)
# 2. Detect new/changed/disappeared models
# 3. Extract only NEW models (AI - minimal cost)
# 4. Generate Excel reports
# 5. Update archive/
# 6. Send email notification (optional)
```

### First Run (Initial Discovery)

```bash
# First time running the system:
python scripts/run_monthly.py --initial

# Result:
# - Creates: data/runs/2024-01-15_INITIAL/
# - Extracts all ~2,500 models ($50 one-time cost)
# - Populates: data/archive/
# - Generates: INITIAL_DISCOVERY.xlsx
```

### Adding a New Manufacturer Later

```bash
# 1. Edit config/manufacturers.yaml (add Volkswagen)
# 2. Run monthly script:
python scripts/run_monthly.py

# System automatically detects new manufacturer
# Result:
# - Crawls VW (first time)
# - Extracts 85 VW models ($1.70)
# - Generates separate report: NEW_MANUFACTURER_VW.xlsx
# - Creates: data/archive/volkswagen/
```

## 📊 Output Reports

### For End Users (Sales/Product Team)

**NEW_MODELS.xlsx** - Monthly report with only new models:
```
Manufacturer | Model | Variant | Type | Power | Range | First Seen | URL
-------------|-------|---------|------|-------|-------|------------|----
BMW          | iX5   | xDrive40| Elec | 313   | 449   | 2024-02-15 | https://...
Mercedes     | EQE   | 350+    | Elec | 288   | 590   | 2024-02-15 | https://...
```

**URL_CHANGES.xlsx** - Informational (same models, new URLs):
```
Model             | Old URL          | New URL          | Status
------------------|------------------|------------------|-------
BMW iX xDrive50   | https://old...   | https://new...   | URL changed
```

## 🔍 Key Features

### 1. Content-Based Fingerprinting

**Problem:** URLs change when manufacturers reorganize websites
**Solution:** Identify vehicles by content (brand + model + variant + year)

```
Fingerprint: "bmw_ix_xdrive50_2024"
URL can change: tracking.db updates URL, doesn't report as "new"
```

### 2. Per-Manufacturer Initial Runs

Add manufacturers anytime:
- **Month 1:** BMW, Mercedes, Audi (initial run)
- **Month 5:** Add Volkswagen → Separate baseline report
- **Month 6:** All 4 manufacturers tracked equally

### 3. Smart Change Detection

```python
# Monthly run identifies:
- Truly NEW models (need spare parts review)
- URL changes (same model, new URL - informational)
- Disappeared models (discontinued/removed from site)
```

### 4. Cost Optimization

```
First run: Extract all 2,500 models = $50 (one-time)
Monthly: Extract only 15 new models = $0.30
Adding new manufacturer: Extract 85 models = $1.70

Annual cost: $50 + (11 × $0.30) + $1.70 = ~$55
```

### 5. Throttling & Reliability

- 10-second delays between extractions
- 30-second delays between manufacturers
- Progress saved every 10 vehicles
- Retry logic (3 attempts)
- Token limit monitoring

## 🗄️ Database Schema

```sql
-- Vehicles table (tracks all models)
CREATE TABLE vehicles (
    fingerprint TEXT PRIMARY KEY,     -- "bmw_ix_xdrive50_2024"
    manufacturer TEXT,
    model TEXT,
    variant TEXT,
    model_year TEXT,

    url TEXT,                         -- Current URL
    url_history JSON,                 -- Track URL changes

    first_seen DATE,                  -- When first discovered
    last_seen DATE,                   -- When last seen
    last_url_change DATE,

    status TEXT                       -- 'active', 'disappeared'
);

-- Manufacturers table
CREATE TABLE manufacturers (
    slug TEXT PRIMARY KEY,
    name TEXT,
    root_url TEXT,
    first_crawled DATE,              -- When added to system
    last_crawled DATE
);

-- Run history
CREATE TABLE runs (
    date DATE PRIMARY KEY,
    total_new INTEGER,
    total_url_changes INTEGER,
    total_disappeared INTEGER,
    total_cost_usd REAL,
    duration_minutes REAL
);
```

## 📦 Data Flow

```
1. CRAWL (FREE)
   └─> config/manufacturers.yaml → Crawl all manufacturers
   └─> Output: List of discovered URLs

2. FINGERPRINT
   └─> Generate fingerprint from URL patterns (fast)
   └─> Compare with tracking.db

3. CLASSIFY
   ├─> NEW: Never seen before
   ├─> URL_CHANGED: Same fingerprint, different URL
   └─> DISAPPEARED: In DB but not found on site

4. EXTRACT (AI - Cost $$$)
   └─> Extract ONLY new models (not all models!)
   └─> 10-second throttling between requests

5. REPORTS
   ├─> NEW_MODELS.xlsx → Email to sales team
   ├─> URL_CHANGES.xlsx → Informational
   └─> Update archive/ with new models

6. UPDATE
   ├─> tracking.db → Update timeline
   └─> archive/ → Add new model files
```

## 💰 Cost Estimates

| Scenario | Models | Cost |
|----------|--------|------|
| First run (all manufacturers) | 2,500 | $50.00 |
| Monthly run (avg new models) | 15 | $0.30 |
| Add new manufacturer | 85 | $1.70 |
| URL changes (no extraction) | N/A | $0.00 |

**Annual budget:** ~$55 for 50 manufacturers

## 🔒 Security

API key protection:
```bash
# .env file
ANTHROPIC_API_KEY=*sk-ant-api03-your-key-here

# Asterisk prefix prevents accidental use outside Python
# Python scripts automatically remove it
```

## 📝 Requirements

- Python 3.8+
- Anthropic API key (Claude Haiku access)
- ~500MB disk space (50 manufacturers × ~100 models)
- Monthly runs: ~3-8 hours (depends on new models)

## 🚦 Implementation Status

### ✅ Completed
- [x] Project structure
- [x] Configuration system
- [x] Technical data schema (100+ fields)
- [x] API key validation

### 🔨 To Be Implemented
- [ ] src/crawler.py
- [ ] src/extractor.py
- [ ] src/fingerprint.py
- [ ] src/change_detector.py
- [ ] src/report_generator.py
- [ ] src/database.py
- [ ] scripts/run_monthly.py
- [ ] Migration from old system

## 📧 Monthly Workflow

```
Day 1 (Start of month):
├─> Developer runs: python scripts/run_monthly.py
├─> System crawls all 50 manufacturers (2 hours)
├─> Detects 23 new models
├─> Extracts 23 models (4 hours with throttling)
└─> Generates reports

Day 1 (End of day):
├─> Email to sales team:
│   Subject: "23 new models detected - January 2024"
│   Attachments:
│   - NEW_MODELS.xlsx (23 models)
│   - URL_CHANGES.xlsx (5 URL updates)
│
└─> Sales team reviews Excel file
    ├─> Filters by manufacturer
    ├─> Checks spare parts compatibility
    └─> Updates product catalog
```

## 🎯 Success Metrics

- **Detection accuracy:** 100% (fingerprint-based matching)
- **False positives:** 0% (URL changes don't count as new)
- **Cost efficiency:** 95% savings vs naive AI-everywhere approach
- **Time to report:** <8 hours for 50 manufacturers
- **End user satisfaction:** Excel reports (no SQL knowledge needed)

## 📖 Next Steps

1. ✅ Review project structure
2. ✅ Review configuration file
3. 🔨 Implement src/ modules (crawler, extractor, etc.)
4. 🔨 Implement scripts/run_monthly.py
5. 🧪 Test with BMW only
6. 📈 Scale to 50 manufacturers
7. 🚀 Production deployment

---

**Current Status:** Architecture and configuration complete. Ready for implementation.
