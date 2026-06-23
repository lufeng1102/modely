# MLflow Integration

modely-ai complements MLflow Model Registry by acting as an external asset intake and governance layer.

## What modely-ai does

- Discovers, evaluates, downloads, locks, scans, and catalogs external models and datasets.
- Produces reports that can support model adoption decisions before assets enter a project or registry.

## What MLflow Model Registry does

Use MLflow Model Registry for internal model lifecycle management:

- registered models and model versions
- aliases, stages, tags, and descriptions
- lineage to MLflow runs and logged models
- organization-level promotion and governance workflows

## Recommended combination

Use modely-ai to assess and import external assets. After validation, register internally produced or accepted models in MLflow.

## Examples

```bash
modely-ai score hf://models/gpt2 --json
modely-ai scan hf://models/gpt2 --json
modely-ai get hf://models/gpt2 --local-dir ./models/gpt2
modely-ai report ./models/gpt2 --format markdown --output gpt2-report.md

# Then register validated artifacts with MLflow in your project workflow.
```
