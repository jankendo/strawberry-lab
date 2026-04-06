"""GitHub Actions workflow dispatch helpers."""

from __future__ import annotations

from dataclasses import dataclass

import requests

from src.config import AppConfig


@dataclass(frozen=True)
class WorkflowRunSummary:
    """Workflow run status data."""

    run_id: int
    html_url: str
    status: str
    conclusion: str | None


class GitHubClient:
    """Thin GitHub Actions API client for workflow dispatch and polling."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._base = f"https://api.github.com/repos/{config.github_owner}/{config.github_repo}"
        self._headers = {
            "Authorization": f"Bearer {config.github_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def is_available(self) -> bool:
        """Return true when all dispatch settings are present."""
        return bool(
            self._config.github_token
            and self._config.github_owner
            and self._config.github_repo
            and self._config.github_workflow_file
        )

    def dispatch_scrape(self, source: str) -> None:
        """Dispatch the configured workflow with a source input."""
        if not self.is_available():
            raise RuntimeError("GitHub workflow settings are incomplete.")
        url = f"{self._base}/actions/workflows/{self._config.github_workflow_file}/dispatches"
        response = requests.post(
            url,
            headers=self._headers,
            json={"ref": self._config.github_ref, "inputs": {"source": source}},
            timeout=20,
        )
        if response.status_code >= 300:
            raise RuntimeError(f"Workflow dispatch failed: {response.status_code} {response.text}")

    def get_latest_run(self) -> WorkflowRunSummary | None:
        """Get latest run for configured workflow."""
        if not self.is_available():
            return None
        url = f"{self._base}/actions/workflows/{self._config.github_workflow_file}/runs?per_page=1"
        response = requests.get(url, headers=self._headers, timeout=20)
        if response.status_code >= 300:
            raise RuntimeError(f"Failed to fetch workflow runs: {response.status_code}")
        runs = response.json().get("workflow_runs", [])
        if not runs:
            return None
        run = runs[0]
        return WorkflowRunSummary(
            run_id=run["id"],
            html_url=run["html_url"],
            status=run["status"],
            conclusion=run.get("conclusion"),
        )
