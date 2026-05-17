# modely-ai

**modely-ai** is a Python package that provides a unified interface for downloading AI models and datasets from multiple platforms including Hugging Face, ModelScope, and GitHub. It offers a simple command-line tool and Python API to efficiently download models and datasets with progress tracking, resumable downloads, and minimal dependencies.

## Features

- 🚀 **Unified interface**: Download from Hugging Face, ModelScope, and GitHub with a single tool
- ⚡ **Progress tracking**: Real-time download progress with tqdm
- 🔄 **Resumable downloads**: Resume interrupted downloads automatically
- 📁 **Flexible options**: Download entire repositories or specific files
- 🔐 **Authentication support**: Access private models and datasets with tokens
- 📦 **Official SDKs**: Uses `huggingface-hub` official SDK for reliable downloads
- 📦 **Minimal dependencies**: Only requires `requests`, `tqdm`, and `huggingface-hub`
- 💾 **Smart caching**: Avoid duplicate downloads with unified cache system
- 🗂️ **Cache management**: CLI commands to view, list, and clean cache

## Installation

Install modely-ai using pip:

```bash
pip install modely-ai
```

## Usage

### Command Line Interface

modely-ai provides a command-line interface with three main subcommands: `hf` for Hugging Face, `ms` for ModelScope, and `github` for GitHub.

#### Download from Hugging Face

Download an entire model repository:
```bash
modely-ai hf bert-base-uncased
```

Download a specific file from a repository:
```bash
modely-ai hf bert-base-uncased --file config.json
```

Download with specific options:
```bash
modely-ai hf facebook/opt-2.7b --repo-type model --revision v1.1.0 --local-dir ./models
```

Download from a private repository:
```bash
modely-ai hf username/private-repo --token YOUR_HUGGINGFACE_TOKEN
```

#### Download from ModelScope

Download an entire model repository:
```bash
modely-ai ms owner/model-name
```

Download a specific file:
```bash
modely-ai ms owner/model-name --file config.json
```

Download a dataset:
```bash
modely-ai ms owner/dataset-name --repo-type dataset
```

Download with specific options:
```bash
modely-ai ms owner/model-name --revision main --local-dir ./models
```

#### Download from GitHub

Download an entire repository:
```bash
modely-ai github owner/repo
```

Download a specific file:
```bash
modely-ai github owner/repo --file README.md
```

Download with specific options:
```bash
modely-ai github owner/repo --revision dev --local-dir ./repos
```

Download with Git LFS support (for large files):
```bash
modely-ai github owner/repo --with-lfs
```

Download from a private repository:
```bash
modely-ai github owner/private-repo --token YOUR_GITHUB_TOKEN
```

### Python API

You can also use modely-ai directly in your Python code:

```python
from modely import hf_snapshot_download, model_file_download, github_snapshot_download, github_file_download

# Download an entire Hugging Face repository
model_path = hf_snapshot_download(
    repo_id="bert-base-uncased",
    repo_type="model",
    revision="main"
)

# Download a specific file from Hugging Face
file_path = hf_file_download(
    repo_id="bert-base-uncased",
    filename="config.json",
    repo_type="model"
)

# Download from ModelScope
ms_model_path = modelscope_snapshot_download(
    repo_id="owner/model-name",
    repo_type="model",
    revision="master"
)

# Download an entire GitHub repository
repo_path = github_snapshot_download(
    repo_id="owner/repo",
    revision="main"
)

# Download a specific file from GitHub
file_path = github_file_download(
    repo_id="owner/repo",
    filename="README.md",
    revision="main"
)
```

## Cache Management

modely-ai includes a unified cache system to avoid duplicate downloads. Files are organized by source (Hugging Face / ModelScope), repository type, repository ID, and revision.

### Cache Directory Configuration

The cache directory is resolved with the following priority:

1. **CLI argument**: `--cache-dir` (for download commands) or `modely cache --cache-dir <DIR>`
2. **Environment variable**: `MODELY_CACHE`
3. **Config file**: `~/.modely/config.json` (set via `modely cache config --set <DIR>`)
4. **Default**: `~/.cache/modely`

```bash
# Set cache directory via environment variable
export MODELY_CACHE=/path/to/cache

# Or set via config file (persistent)
modely-ai cache config --set /path/to/cache

# Or specify per-command
modely-ai --cache-dir /path/to/cache hf gpt2
```

### Cache Structure

```
~/.cache/modely/
├── hf/                    # Hugging Face cache
│   ├── models/            # repo_type = model
│   │   └── gpt2/
│   │       └── main/     # revision
│   │           ├── config.json
│   │           └── pytorch_model.bin
│   └── datasets/         # repo_type = dataset
├── ms/                    # ModelScope cache
│   ├── models/
│   │   └── owner--model-name/
│   │       └── master/
│   └── datasets/
└── github/                # GitHub cache
    └── owner--repo/
        └── main/
            ├── README.md
            └── (repository files)
```

### Cache Hit

When downloading the same file again, modely-ai detects the cached file and skips the download:

```bash
# First download
modely-ai hf gpt2 --file config.json
# Output: Downloading config.json from gpt2...

# Second download (cached)
modely-ai hf gpt2 --file config.json
# Output: File already cached at: ~/.cache/modely/hf/models/gpt2/main/config.json
```

### Cache Commands

```bash
# Show cache directory and total size
modely-ai cache info

# List all cached repositories
modely-ai cache list

# List with detailed file information
modely-ai cache list --detail

# Clean all cache
modely-ai cache clean

# Clean specific repository cache
modely-ai cache clean gpt2

# Show current cache directory configuration
modely-ai cache config

# Set new cache directory
modely-ai cache config --set /tmp/my-cache
```

## Command Reference

### Hugging Face Commands

```bash
modely-ai hf <repo_id> [OPTIONS]
```

Options:
- `--file FILE`: Specific file path to download from the repository
- `--repo-type {model,dataset,space}`: Type of repository (default: model)
- `--revision REVISION`: Revision of the model (default: main)
- `--cache-dir DIR`: Cache directory for downloaded files
- `--local-dir DIR`: Local directory to download files to
- `--token TOKEN`: Access token for private repositories
- `--force-download`: Force re-download even if file exists

### ModelScope Commands

```bash
modely-ai ms <repo_id> [OPTIONS]
```

Options:
- `--file FILE`: Specific file path to download from the repository
- `--repo-type {model,dataset}`: Type of repository (default: model)
- `--revision REVISION`: Revision of the model (default: master)
- `--cache-dir DIR`: Cache directory for downloaded files
- `--local-dir DIR`: Local directory to download files to
- `--token TOKEN`: Access token for private models

### GitHub Commands

```bash
modely-ai github <repo_id> [OPTIONS]
```

Options:
- `--file FILE`: Specific file to download from the repository
- `--revision REVISION`: Branch, tag, or commit SHA (default: main)
- `--cache-dir DIR`: Cache directory for downloaded files
- `--local-dir DIR`: Local directory to download files to
- `--token TOKEN`: GitHub personal access token for private repositories
- `--with-lfs`: Enable Git LFS support for large files
- `--force-download`: Force re-download even if file exists

## Requirements

- Python 3.10 or higher
- requests >= 2.25.0
- tqdm >= 4.62.0
- huggingface-hub >= 0.20.0

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Feel free to submit a pull request or open an issue to improve the functionality or documentation.

## Support

If you encounter any issues or have questions, please open an issue on the GitHub repository.
