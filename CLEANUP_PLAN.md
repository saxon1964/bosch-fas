# Cleanup Plan - Old Files

## Files to DELETE (will be replaced with new implementation)

```bash
# Delete these old single-manufacturer files:
rm extract_technical_data.py       # → Will become src/extractor.py
rm smart_crawler.py                # → Will become src/crawler.py
rm retry_failed.py                 # → Integrated into new src/extractor.py
rm test_smart_crawler.py           # → Will become scripts/run_monthly.py
rm view.sh                         # → Will become scripts/view_data.py
```

## Files to KEEP

```
✅ config/manufacturers.yaml         # NEW: Configuration
✅ data/                            # NEW: Data storage
✅ src/                             # NEW: Source code (empty, to be implemented)
✅ scripts/test_api_key.py          # Moved from root
✅ technical_data_schema.py         # Keep: Schema definition
✅ requirements.txt                 # Keep: Dependencies (may need updates)
✅ .env                            # Keep: API key
✅ .env.example                    # Keep: Template
✅ .gitignore                      # Keep: Git rules
✅ README.md                       # Updated
```

## Execute Cleanup

```bash
# Run this command to clean up:
rm extract_technical_data.py smart_crawler.py retry_failed.py test_smart_crawler.py view.sh

# Verify:
ls -lh
```

## After Cleanup - Project Structure

```
fas/
├── config/
│   └── manufacturers.yaml         # ★ Configuration
├── data/
│   ├── archive/                   # ★ Master collection
│   └── runs/                      # ★ Monthly reports
├── src/                           # Source code (to be implemented)
│   ├── crawler.py
│   ├── extractor.py
│   ├── fingerprint.py
│   ├── change_detector.py
│   ├── report_generator.py
│   └── database.py
├── scripts/
│   ├── run_monthly.py             # To be implemented
│   └── test_api_key.py            # ✓ Ready
├── technical_data_schema.py       # ✓ Ready
├── requirements.txt               # ✓ Ready
├── .env                          # ✓ Ready
├── .env.example                  # ✓ Ready
├── .gitignore                    # ✓ Ready
└── README.md                     # ✓ Ready
```

Clean and ready for implementation!
