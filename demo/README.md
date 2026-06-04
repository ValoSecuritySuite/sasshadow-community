# Demo data

Redacted sample integrations for trying SaaSShadow Community Edition. All
tokens and secrets here are synthetic placeholders for detector testing.

## Files

- `sample_integration.json` - one integration for a single scan
- `../data/sample_integrations.json` - larger example catalog
- `../samples/artifact_families_dataset.json` - batch dataset for dataset analysis

## Quick try

With the API running (see the root `README.md`):

```bash
curl -s -X POST http://localhost:8000/scan/analyze \
  -H 'Content-Type: application/json' \
  -d "{\"target\": \"salesforce_to_slack_demo\", \"json_data\": $(cat demo/sample_integration.json)}"
```

Open http://localhost:3000/scans to view results in history.
