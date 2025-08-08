import os
import sys
import subprocess
import requests

from version import __version__


class VersionChecker:
    """
    Checks GitHub for a newer release tag and, if found,
    pulls the latest code via git and restarts the process.
    """

    GITHUB_API_LATEST_RELEASE = (
        "https://api.github.com/repos/{repo}/releases/latest"
    )

    def __init__(self, repo: str):
        """
        :param repo: GitHub "owner/repo", e.g. "Ameer-Jamal/readableSQL"
        """
        self.repo = repo
        self.local_version = __version__

    def fetch_latest_version(self) -> str | None:
        """Return the latest SemVer string from GitHub, or None on failure."""
        url = self.GITHUB_API_LATEST_RELEASE.format(repo=self.repo)
        try:
            resp = requests.get(url, headers={"Accept": "application/vnd.github.v3+json"})
            resp.raise_for_status()
            tag = resp.json().get("tag_name", "")
            return tag.lstrip("v")
        except Exception:
            return None

    @staticmethod
    def version_tuple(v: str) -> tuple[int, ...]:
        return tuple(int(x) for x in v.split("."))

    def is_update_available(self, latest: str) -> bool:
        """Return True if latest > local."""
        try:
            return self.version_tuple(latest) > self.version_tuple(self.local_version)
        except Exception:
            return False

    def perform_update(self) -> None:
        """
        Pull the latest code and restart this process.
        Raises on failure.
        """
        # 1. Pull
        subprocess.run(["git", "pull"], check=True)
        # 2. Restart (replace process image)
        os.execv(sys.executable, [sys.executable] + sys.argv)

    def check_for_update(self) -> None:
        """
        Fetches remote version, compares, and updates/restarts if needed.
        Call early in your app startup.
        """
        latest = self.fetch_latest_version()
        if latest and self.is_update_available(latest):
            print(f"Updating from {self.local_version} to {latest}…")
            self.perform_update()
