# ISPM Catalog (Community Edition)

Community Edition includes a read-only **ISPM (Integration Security Posture
Management) catalog**: default business categories (Identity, Communication,
Storage, AI/ML, and others) and a mapping from common SaaS provider names to
those categories. Scans use this catalog to classify providers; the dashboard
ISPM page shows the same data.

The catalog ships in `app/policies/ispm_categories.yaml`. Community Edition
does not support editing categories or per-tenant overrides in the UI.

## API (read-only)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/ispm/categories` | Full category catalog and thresholds |
| `GET` | `/ispm/providers` | Provider to category mapping |

See http://localhost:8000/docs for request and response shapes.

## Related code

| Module | Path |
|--------|------|
| Classifier | `app/analysis/ispm_classifier.py` |
| Routes | `app/api/ispm.py` |
