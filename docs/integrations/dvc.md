# DVC Integration

modely-ai and DVC solve complementary parts of the ML asset lifecycle.

## What modely-ai does

- Finds, compares, downloads, locks, scans, and catalogs external assets before they enter a project.
- Produces local directories, lockfiles, reports, and catalog entries for selected models, datasets, and tool repositories.

## What DVC does

Use DVC for project-level data/model versioning and reproducibility:

- `dvc.yaml` pipelines
- stage dependencies and outputs
- remote storage
- data/model version control
- experiment and metric workflows

## Recommended combination

Use modely-ai to choose and pull external assets, then use DVC to track those assets inside a training or evaluation project.

## Examples

```bash
modely-ai get hf://datasets/owner/data --local-dir ./data/raw --profile full
modely-ai lock hf://datasets/owner/data --output modely.lock

dvc add data/raw modely.lock
git add data/raw.dvc modely.lock .gitignore
git commit -m "Track external dataset"
```
