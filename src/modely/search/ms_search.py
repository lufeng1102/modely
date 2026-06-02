"""ModelScope search backend for modely-ai."""

import json
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional

import requests

from .types import SearchResult


# ModelScope uses the PUT-method dolphin API for model search
_SEARCH_URL = "{endpoint}/api/v1/dolphin/models"

# Map sort field names to dolphin API SortBy values
_SORT_BY_MAP = {
    "downloads": "downloads",
    "lastModified": "last_updated",
    "likes": "likes",
    "created_at": "created_at",
}


def _to_iso(ts) -> Optional[str]:
    """Convert a Unix timestamp (int seconds or ISO string) to ISO 8601."""
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        except (ValueError, OSError):
            return None
    return str(ts)


def _build_search_body(
    keyword: Optional[str],
    task: Optional[str],
    limit: int,
    page: int = 1,
    sort: str = "downloads",
) -> Dict:
    """Build the JSON body for ModelScope dolphin search API."""
    body: Dict = {
        "PageSize": limit,
        "PageNumber": page,
        "Name": keyword or "",
        "tags": [],
        "tasks": [],
        "SortBy": _SORT_BY_MAP.get(sort, "downloads"),
    }
    if task:
        body["tasks"] = [task]
    return body


def _parse_model_item(item: Dict) -> SearchResult:
    """Parse a ModelScope model item from dolphin API into a SearchResult."""
    # Build full repo ID from Path/Name
    path = item.get("Path", "")
    name = item.get("Name", "")
    if path and name:
        repo_id = f"{path}/{name}"
    else:
        repo_id = name or path or item.get("Id", "")

    # Tasks field can be a list of dicts (each with Name) or a list of strings
    tasks_raw = item.get("Tasks") or []
    if tasks_raw and isinstance(tasks_raw[0], dict):
        pipeline_tag = tasks_raw[0].get("Name")
    else:
        pipeline_tag = tasks_raw[0] if tasks_raw else None

    # Tags field can be a list of dicts or strings
    tags_raw = item.get("Tags") or []
    tags: List[str] = []
    for t in tags_raw:
        if isinstance(t, dict):
            tag_name = t.get("Name") or t.get("value")
            if tag_name:
                tags.append(str(tag_name))
        elif t:
            tags.append(str(t))

    # Likes is often null; fall back to Stars
    likes = item.get("Likes")
    if likes is None:
        likes = item.get("Stars", 0) or 0

    result = SearchResult(
        id=repo_id,
        source="ms",
        repo_type="model",
        url=f"https://modelscope.cn/models/{repo_id}",
        author=item.get("Organization") or item.get("Path"),
        downloads=item.get("Downloads", 0) or 0,
        likes=likes,
        last_modified=_to_iso(item.get("LastUpdatedTime") or item.get("CreatedTime")),
        created_at=_to_iso(item.get("CreatedTime")),
        pipeline_tag=pipeline_tag,
        library_name=None,
        tags=tags,
        license=item.get("License"),
        description=item.get("Description") or item.get("ChineseName"),
    )
    return result


def search_modelscope(
    keyword: Optional[str] = None,
    *,
    repo_type: str = "model",
    task: Optional[str] = None,
    sort: str = "downloads",
    direction: str = "desc",
    limit: int = 20,
) -> List[SearchResult]:
    """Search ModelScope for models or datasets.

    Uses the PUT-method dolphin API. Currently only supports models
    (datasets use a different, less-documented endpoint).
    """
    if repo_type == "dataset":
        print("Warning: ModelScope dataset search is not yet supported.", file=sys.stderr)
        return []

    endpoint = os.environ.get("MODELSCOPE_ENDPOINT", "https://www.modelscope.cn")
    url = _SEARCH_URL.format(endpoint=endpoint)
    body = _build_search_body(keyword, task, limit, sort=sort)

    try:
        response = requests.put(
            url,
            json=body,
            timeout=30,
            headers={
                "Content-Type": "application/json",
                "user-agent": "modely-ai/search",
            },
        )
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.Timeout:
        print("Warning: ModelScope search timed out.", file=sys.stderr)
        return []
    except requests.exceptions.ConnectionError:
        print("Warning: Could not connect to ModelScope.", file=sys.stderr)
        return []
    except requests.exceptions.HTTPError as e:
        print(f"Warning: ModelScope search HTTP error: {e}", file=sys.stderr)
        return []
    except json.JSONDecodeError:
        print("Warning: ModelScope returned invalid JSON.", file=sys.stderr)
        return []
    except Exception as e:
        print(f"Warning: ModelScope search failed: {e}", file=sys.stderr)
        return []

    # Navigate response: Data -> Model -> Models
    inner = data.get("Data")
    if not isinstance(inner, dict):
        return []

    model_data = inner.get("Model")
    if not isinstance(model_data, dict):
        return []

    items = model_data.get("Models")
    if not isinstance(items, list):
        return []

    output = []
    for item in items:
        try:
            if repo_type == "model":
                result = _parse_model_item(item)
            else:
                # Datasets don't have a documented search API; skip for now.
                # A dataset item uses similar fields but with different key names.
                continue
            output.append(result)
        except Exception:
            # Skip malformed items
            continue

    # Client-side sorting as a fallback to ensure correct order
    if sort == "lastModified":
        output.sort(key=lambda r: r.last_modified or "", reverse=(direction == "desc"))
    elif sort == "likes":
        output.sort(key=lambda r: r.likes, reverse=(direction == "desc"))
    elif sort == "created_at":
        output.sort(key=lambda r: r.created_at or "", reverse=(direction == "desc"))
    else:  # downloads (default)
        output.sort(key=lambda r: r.downloads, reverse=(direction == "desc"))

    return output
