import os
from typing import Any, cast

import httpx

DEFAULT_API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")


class APIClient:
    """Client communicating with the FastAPI RFP Automation Backend."""

    def __init__(self, base_url: str = DEFAULT_API_BASE, token: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token

    def _get_headers(self) -> dict[str, str]:
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def set_token(self, token: str | None) -> None:
        self.token = token

    def check_health(self) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=3.0) as client:
                res = client.get(f"{self.base_url}/health")
                if res.status_code == 200:
                    return cast(dict[str, Any], res.json())
                return {"status": "degraded", "backend": "unhealthy"}
        except Exception:
            return {"status": "unreachable", "backend": "down"}

    def login(self, username: str, password: str) -> tuple[bool, str | dict[str, Any]]:
        try:
            with httpx.Client(timeout=5.0) as client:
                res = client.post(
                    f"{self.base_url}/auth/login",
                    json={"email": username, "username": username, "password": password},
                )
                if res.status_code == 200:
                    data = cast(dict[str, Any], res.json())
                    token = data.get("access_token")
                    if isinstance(token, str):
                        self.set_token(token)
                    return True, data
                detail = res.json().get("detail", "Login failed")
                if isinstance(detail, list):
                    detail = detail[0].get("msg", "Validation error") if detail else "Validation error"
                return False, str(detail)
        except Exception as e:
            return False, f"Connection error: {e!s}"

    def get_models(self) -> list[dict[str, Any]]:
        try:
            with httpx.Client(timeout=5.0) as client:
                res = client.get(f"{self.base_url}/ai/models", headers=self._get_headers())
                if res.status_code == 200:
                    data = res.json()
                    raw_models = (
                        data.get("models", [])
                        if isinstance(data, dict)
                        else (data if isinstance(data, list) else [])
                    )
                    normalized: list[dict[str, Any]] = []
                    for m in raw_models:
                        if isinstance(m, dict):
                            tag = m.get("tag") or m.get("model_tag") or m.get("name", "")
                            name = m.get("name") or m.get("display_name") or m.get("label", "")
                            normalized.append({
                                "model_tag": tag,
                                "tag": tag,
                                "name": name,
                                "display_name": name,
                                "label": m.get("label") or f"{name} ({tag})",
                                "ram_usage": m.get("ram_usage") or f"~{m.get('ram_required_gb', 4)}GB",
                                "context_length": m.get("context_length") or str(m.get("context_window", "32K")),
                                "is_default": bool(m.get("is_default", False)),
                                "is_available": bool(m.get("is_available", True)),
                            })
                    return normalized
                return []
        except Exception:
            return []

    def set_model_preference(self, model_tag: str) -> bool:
        try:
            with httpx.Client(timeout=5.0) as client:
                res = client.put(
                    f"{self.base_url}/ai/preference",
                    json={"model_tag": model_tag},
                    headers=self._get_headers(),
                )
                return res.status_code == 200
        except Exception:
            return False

    def upload_pdf(self, file_bytes: bytes, filename: str) -> dict[str, Any]:
        with httpx.Client(timeout=30.0) as client:
            files = {"file": (filename, file_bytes, "application/pdf")}
            res = client.post(f"{self.base_url}/pdf/upload", files=files, headers=self._get_headers())
            if res.status_code in (200, 201):
                return cast(dict[str, Any], res.json())
            raise RuntimeError(res.json().get("detail", "PDF upload failed"))

    def upload_excel(self, file_bytes: bytes, filename: str) -> dict[str, Any]:
        with httpx.Client(timeout=30.0) as client:
            files = {"file": (filename, file_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            res = client.post(f"{self.base_url}/excel/upload", files=files, headers=self._get_headers())
            if res.status_code in (200, 201):
                return cast(dict[str, Any], res.json())
            raise RuntimeError(res.json().get("detail", "Excel upload failed"))

    def create_run(
        self,
        pdf_document_id: str,
        workbook_id: str,
        model_name: str | None = None,
        vendor_name: str | None = None,
    ) -> dict[str, Any]:
        with httpx.Client(timeout=10.0) as client:
            payload = {
                "pdf_document_id": pdf_document_id,
                "workbook_id": workbook_id,
                "model_name": model_name,
                "vendor_name": vendor_name,
            }
            res = client.post(f"{self.base_url}/runs", json=payload, headers=self._get_headers())
            if res.status_code in (200, 201):
                return cast(dict[str, Any], res.json())
            raise RuntimeError(res.json().get("detail", "Failed to start run"))

    def get_run(self, run_id: str) -> dict[str, Any]:
        with httpx.Client(timeout=10.0) as client:
            res = client.get(f"{self.base_url}/runs/{run_id}", headers=self._get_headers())
            if res.status_code == 200:
                return cast(dict[str, Any], res.json())
            raise RuntimeError(res.json().get("detail", "Failed to fetch run status"))

    def cancel_run(self, run_id: str) -> bool:
        try:
            with httpx.Client(timeout=5.0) as client:
                res = client.post(f"{self.base_url}/runs/{run_id}/cancel", headers=self._get_headers())
                return res.status_code == 200
        except Exception:
            return False

    def submit_review(self, run_id: str, reviews: list[dict[str, Any]]) -> dict[str, Any]:
        with httpx.Client(timeout=20.0) as client:
            res = client.post(
                f"{self.base_url}/runs/{run_id}/review",
                json={"reviews": reviews},
                headers=self._get_headers(),
            )
            if res.status_code == 200:
                return cast(dict[str, Any], res.json())
            raise RuntimeError(res.json().get("detail", "Failed to save reviews"))

    def list_runs(self, status_filter: str | None = None) -> list[dict[str, Any]]:
        try:
            params = {}
            if status_filter and status_filter != "All":
                params["status"] = status_filter.lower()
            with httpx.Client(timeout=10.0) as client:
                res = client.get(f"{self.base_url}/runs", params=params, headers=self._get_headers())
                if res.status_code == 200:
                    return cast(list[dict[str, Any]], res.json())
                return []
        except Exception:
            return []

    def get_download_url(self, filename: str) -> str:
        return f"{self.base_url}/excel/download/{filename}"

    def download_file(self, filename: str) -> bytes | None:
        try:
            with httpx.Client(timeout=30.0) as client:
                res = client.get(f"{self.base_url}/excel/download/{filename}", headers=self._get_headers())
                if res.status_code == 200:
                    return res.content
                return None
        except Exception:
            return None
