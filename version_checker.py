# version_checker.py

import json
import ssl
import urllib.request
import urllib.error
import subprocess
import sys
import os
import logging
from typing import Optional
from PyQt5.QtWidgets import QMessageBox

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


class VersionChecker:
    """
    Checks GitHub tags for this repository and, if a newer version is available,
    offers to pull and restart the application in place.
    """

    OWNER = "Ameer-Jamal"
    REPO = "readableSQL"
    TAGS_API_URL = "https://api.github.com/repos/{owner}/{repo}/tags"
    REMOTE = "origin"
    BRANCH = "master"

    def __init__(self, current_version: str, repo_path: Optional[str] = None):
        self.current = current_version
        self.repo_path = repo_path or os.path.abspath(os.path.join(__file__, os.pardir))

    def _ssl_context(self) -> ssl.SSLContext:
        """
        Create an SSL context. Prefer certifi if available; otherwise fall back to system CA.
        """
        try:
            import certifi  # lazy import
            ctx = ssl.create_default_context(cafile=certifi.where())
            logging.debug("Using certifi CA bundle.")
            return ctx
        except Exception as e:
            logging.debug(f"certifi not available; falling back to system CA: {e}")
            return ssl.create_default_context()

    def fetch_latest_tag(self) -> Optional[str]:
        """
        Retrieve the list of tags from GitHub and return the highest semver tag,
        or None if we failed to talk to GitHub.
        """
        url = self.TAGS_API_URL.format(owner=self.OWNER, repo=self.REPO)
        logging.info(f"Fetching tags from {url}…")
        ctx = self._ssl_context()

        try:
            with urllib.request.urlopen(url, context=ctx, timeout=8) as resp:
                raw = resp.read().decode()
                tags = json.loads(raw)
        except Exception as e:
            logging.warning(f"Could not fetch tags: {e}")
            return None

        versions = [t.get("name", "").lstrip("v") for t in tags if t.get("name", "").startswith("v")]
        logging.info(f"Found GitHub tags: {versions}")
        if not versions:
            return None

        def semver_key(v: str):
            parts = v.split(".")
            return tuple(int(p) for p in parts)

        versions.sort(key=semver_key, reverse=True)
        latest = versions[0]
        logging.info(f"Latest semver tag is: {latest}")
        return latest

    def _compare(self, v1: str, v2: str) -> int:
        """
        Compare two dot-separated version strings.
          return  1 if v1>v2
                  0 if v1==v2
                 -1 if v1<v2
        """
        a = [int(x) for x in v1.split(".")]
        b = [int(x) for x in v2.split(".")]
        n = max(len(a), len(b))
        a += [0] * (n - len(a))
        b += [0] * (n - len(b))
        if a > b:
            return 1
        if a < b:
            return -1
        return 0

    def is_update_available(self) -> bool:
        """
        Return True if a newer tag exists on GitHub.
        """
        latest = self.fetch_latest_tag()
        if not latest:
            logging.info("No tags to compare against.")
            return False
        cmpv = self._compare(latest, self.current)
        logging.info(f"Comparing latest `{latest}` vs current `{self.current}` ⇒ {cmpv}")
        return cmpv > 0

    def prompt_update(self, parent=None):
        """
        If an update is available, show a Qt dialog asking the user to pull and restart.
        On confirmation, performs 'git pull' and re-executes the process.
        """
        if not self.is_update_available():
            return

        latest = self.fetch_latest_tag()
        if latest is None:
            return

        dlg = QMessageBox(parent)
        dlg.setWindowTitle("Update Available")
        dlg.setText(f"A new version {latest} is available (you have {self.current}).")
        dlg.setInformativeText("Pull & restart now?")
        dlg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)

        if dlg.exec() != QMessageBox.Yes:
            logging.info("User declined update.")
            return

        try:
            logging.info(f"Pulling {self.REMOTE}/{self.BRANCH}…")
            subprocess.check_call(["git", "pull", self.REMOTE, self.BRANCH], cwd=self.repo_path)
            logging.info("Restarting…")
            os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception as e:
            logging.error(f"Update failed: {e}")
            err = QMessageBox(parent)
            err.setWindowTitle("Update Failed")
            err.setText(f"Auto-update failed:\n{e}")
            err.exec()
