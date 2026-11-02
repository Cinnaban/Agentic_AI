"""Kaggle public-dataset client for market reference data (read-only).

Search, metadata and download of *public* datasets work without credentials. Optional auth raises rate limits:
KAGGLE_USERNAME + KAGGLE_KEY (basic) or KAGGLE_API_TOKEN (bearer). Search results and metadata are cached in
shared_storage; downloads are size-capped (KAGGLE_MAX_DOWNLOAD_MB, default 50) and stored under
shared_storage/market_datasets/kaggle so every agent project can reuse them.
"""
from __future__ import annotations

import io
import os
import re
import sys
import zipfile
from pathlib import Path

import requests

from .alpha_vantage import ROOT, _load_env, _storage

API = "https://www.kaggle.com/api/v1"
NS = "kaggle"
SEARCH_TTL, META_TTL = 6 * 3600, 24 * 3600
REF = re.compile(r"^[a-z0-9][a-z0-9\-_.]*/[a-z0-9][a-z0-9\-_.]*$", re.I)


class Kaggle:
    def __init__(self):
        _load_env()
        self.token = os.getenv("KAGGLE_API_TOKEN", "").strip()
        self.user = os.getenv("KAGGLE_USERNAME", "").strip()
        self.key = os.getenv("KAGGLE_KEY", "").strip()
        self.max_mb = float(os.getenv("KAGGLE_MAX_DOWNLOAD_MB", "50"))
        self.last_error = None

    def authenticated(self):
        return bool(self.token or (self.user and self.key))

    def _auth(self):
        if self.token:
            return {"headers": {"Authorization": f"Bearer {self.token}"}}
        if self.user and self.key:
            return {"auth": (self.user, self.key)}
        return {}

    def _get(self, path, params=None, **kw):
        resp = requests.get(f"{API}/{path}", params=params, timeout=30, **self._auth(), **kw)
        resp.raise_for_status()
        return resp

    def _cached(self, key, ttl, fn):
        disk = _storage()
        dkey = disk.build_cache_key(key) if disk else None
        if disk:
            try:
                hit = disk.get_cached_data(NS, dkey)
                if hit is not None:
                    return hit
            except Exception:
                pass
        try:
            value = fn()
        except (requests.RequestException, ValueError) as exc:
            self.last_error = type(exc).__name__
            return None
        if disk and value is not None:
            try:
                disk.set_cached_data(NS, dkey, value, ttl)
            except Exception:
                pass
        return value

    @staticmethod
    def _brief(d):
        return {"ref": d.get("ref"), "title": d.get("title"), "subtitle": d.get("subtitle") or "", "url": d.get("url"),
                "downloads": d.get("downloadCount"), "usability": d.get("usabilityRatingNullable"),
                "bytes": d.get("totalBytes"), "updated": (d.get("lastUpdated") or "")[:10], "license": d.get("licenseName")}

    def search(self, query, limit=5, file_type="csv", sort="votes"):
        """Top public datasets for a query: [{'ref','title','subtitle','url','downloads','usability','bytes','updated'}]."""
        params = {"search": query, "sortBy": sort, "fileType": file_type, "pageSize": max(limit, 1)}
        data = self._cached(("search", params), SEARCH_TTL, lambda: self._get("datasets/list", params).json())
        return [self._brief(d) for d in (data or [])[:limit] if isinstance(d, dict) and d.get("ref")]

    def metadata(self, ref):
        if not REF.match(ref or ""):
            raise ValueError("dataset ref must look like owner/name")
        data = self._cached(("view", ref), META_TTL, lambda: self._get(f"datasets/view/{ref}").json())
        return self._brief({**data, "ref": ref, "title": data.get("titleNullable"), "subtitle": data.get("subtitleNullable"),
                            "totalBytes": data.get("totalBytesNullable"), "licenseName": data.get("licenseNameNullable"),
                            "url": f"https://www.kaggle.com/datasets/{ref}"}) if isinstance(data, dict) else None

    def folder(self):
        disk = _storage()
        base = disk.directories["cache"].parent if disk else ROOT / "shared_storage"
        return Path(base) / "market_datasets" / "kaggle"

    def download(self, ref, force=False):
        """Download a public dataset into shared_storage and return the extracted folder, or None.

        Datasets larger than KAGGLE_MAX_DOWNLOAD_MB are refused so a huge archive can never fill the disk."""
        meta = self.metadata(ref)
        if not meta:
            return None
        if meta["bytes"] and meta["bytes"] > self.max_mb * 1_000_000:
            self.last_error = f"{ref} is {meta['bytes'] / 1e6:.0f} MB, above the {self.max_mb:g} MB cap"
            return None
        target = self.folder() / ref.replace("/", "__")
        if target.is_dir() and any(target.iterdir()) and not force:
            return target
        try:
            resp = self._get(f"datasets/download/{ref}", stream=True)
            buf, size = io.BytesIO(), 0
            for chunk in resp.iter_content(1 << 20):
                size += len(chunk)
                if size > self.max_mb * 1_000_000:
                    self.last_error = "download exceeded the size cap"
                    return None
                buf.write(chunk)
            target.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(buf) as z:
                for name in z.namelist():  # extract only plain files inside the target folder
                    dest = (target / name).resolve()
                    if name.endswith("/") or target.resolve() not in dest.parents:
                        continue
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(z.read(name))
        except (requests.RequestException, zipfile.BadZipFile, OSError) as exc:
            self.last_error = type(exc).__name__
            return None
        return target
