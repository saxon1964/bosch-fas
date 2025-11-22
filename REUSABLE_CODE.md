# Reusable Code Inventory

## ✅ Files We're Keeping (Will Reuse)

### 1. **technical_data_schema.py**
**Purpose:** Comprehensive schema definition (100+ fields)

**What's useful:**
- `TECHNICAL_DATA_SCHEMA` - Complete field definitions
- All values as strings (preserves ranges)
- Categories: combustion_engine, electric_motor, sustainability, noise_emissions, etc.
- `EXTRACTION_INSTRUCTIONS` - Detailed prompt for Claude
- `get_extraction_prompt()` - Generates extraction prompt

**Will be used in:** `src/extractor.py`

---

### 2. **extract_technical_data.py**
**Purpose:** AI-powered extraction with throttling and retry logic

**What's useful:**
- `TechnicalDataExtractor` class:
  - `extract_from_url()` - Fetch page + AI extraction
  - `extract_with_ai()` - Claude API call with retry logic
  - JSON parsing (with markdown extraction)
  - Progress tracking
  - Error handling
  - Crawl4AI integration

**Will be refactored into:** `src/extractor.py` (with throttling enhancements)

**Key features to preserve:**
- AsyncWebCrawler integration
- Claude API calls
- JSON extraction from markdown
- Progress tracking
- Failed URL logging

---

### 3. **smart_crawler.py**
**Purpose:** Pattern-based URL discovery (NO AI)

**What's useful:**
- `SmartCrawler` class:
  - `crawl()` - Main crawl logic
  - Pattern matching with fnmatch
  - Anti-pattern filtering
  - Deduplication
  - Depth limiting
  - Crawl4AI integration

**Will be refactored into:** `src/crawler.py` (multi-manufacturer version)

**Key features to preserve:**
- Pattern/anti-pattern matching
- Depth control
- URL deduplication
- Non-AI approach (cost-free)

---

### 4. **retry_failed.py**
**Purpose:** Improved JSON parsing for Claude responses

**What's useful:**
- Brace-counting algorithm:
  ```python
  # Extract FIRST complete JSON object
  start_idx = response_text.find('{')
  brace_count = 0
  for idx in range(start_idx, len(response_text)):
      if response_text[idx] == '{':
          brace_count += 1
      elif response_text[idx] == '}':
          brace_count -= 1
          if brace_count == 0:
              json_text = response_text[start_idx:idx+1]
              break
  ```

**Will be integrated into:** `src/extractor.py` (replace simple JSON parsing)

**Key benefit:** Handles cases where Claude adds extra text after JSON

---

## 🗑️ Files Deleted (Won't Reuse)

- ❌ **test_smart_crawler.py** - Simple test runner, replaced by `scripts/run_monthly.py`
- ❌ **view.sh** - Shell script, replaced by `scripts/view_data.py` (to be implemented)

---

## 📦 Migration Plan

### Phase 1: Extract Core Logic
```
technical_data_schema.py     →  Keep as-is (already perfect)
extract_technical_data.py    →  Extract classes/functions for src/extractor.py
smart_crawler.py            →  Extract classes/functions for src/crawler.py
retry_failed.py             →  Extract JSON parser for src/extractor.py
```

### Phase 2: Enhance for Multi-Manufacturer
```
src/crawler.py:
├── Import SmartCrawler logic from smart_crawler.py
├── Add multi-manufacturer support (config file)
├── Add fingerprint extraction from URLs
└── Keep pattern matching (NO AI)

src/extractor.py:
├── Import TechnicalDataExtractor from extract_technical_data.py
├── Add improved JSON parser from retry_failed.py
├── Add throttling (10s delays)
├── Add progress saving (every 10 vehicles)
└── Add token tracking
```

### Phase 3: New Modules
```
src/fingerprint.py:
└── Generate content-based IDs (brand_model_variant_year)

src/change_detector.py:
└── Compare discovered URLs with tracking.db
└── Classify: new, url_changed, disappeared

src/database.py:
└── SQLite operations for tracking.db

src/report_generator.py:
└── Generate Excel reports (NEW_MODELS.xlsx, etc.)
```

---

## 🎯 Next Steps

1. Review reusable code files
2. Start implementing `src/` modules by extracting logic
3. Test with BMW configuration
4. Scale to multiple manufacturers

**Current status:** Code inventory complete, ready for implementation!
