#!/usr/bin/env python3
"""Build the Android APK for the mobile app."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from shutil import which
from typing import Any, Dict
from urllib.request import urlretrieve

import logging_config  # noqa: F401

CONFIG_PATH = Path("config/apk_build.json")
MOBILE_APP_PATH = Path("config/mobile_app.json")
GRADLE_PATH = Path("android/app/build.gradle")
GRADLE_WRAPPER_JAR = Path("android/gradle/wrapper/gradle-wrapper.jar")

REQUIRED_KEYS = [
    "appName",
    "appId",
    "serverUrl",
    "versionName",
    "versionCode",
    "icons",
    "permissions",
    "gradleWrapperUrl",
    "signing",
]

SIGNING_KEYS = ["keystorePath", "alias", "storePassword", "keyPassword"]


def check_tools() -> None:
    """Ensure required external tools are available."""
    for tool in ("node", "java", "adb"):
        if which(tool) is None:
            raise RuntimeError(f"{tool} is required but not installed")


def load_config(path: Path) -> Dict[str, Any]:
    """Load and validate the APK build configuration."""
    with path.open() as f:
        data: Dict[str, Any] = json.load(f)
    for key in REQUIRED_KEYS:
        if key not in data:
            raise KeyError(f"Missing required key: {key}")
    for key in SIGNING_KEYS:
        if key not in data["signing"]:
            raise KeyError(f"Missing signing key: {key}")
    return data


def update_mobile_config(cfg: Dict[str, Any]) -> None:
    """Write selected values into config/mobile_app.json."""
    mobile: Dict[str, Any] = {}
    if MOBILE_APP_PATH.exists():
        with MOBILE_APP_PATH.open() as f:
            mobile = json.load(f)
    mobile.update(
        {
            "appName": cfg["appName"],
            "appId": cfg["appId"],
            "serverUrl": cfg["serverUrl"],
            "icons": cfg["icons"],
            "permissions": cfg["permissions"],
            "version": cfg["versionName"],
            "versionCode": cfg["versionCode"],
        }
    )
    with MOBILE_APP_PATH.open("w") as f:
        json.dump(mobile, f, indent=2)
        f.write("\n")


def maybe_inject_signing(signing: Dict[str, str]) -> None:
    """Append signing info to build.gradle if not present."""
    if not GRADLE_PATH.exists():
        return
    with GRADLE_PATH.open() as f:
        content = f.read()
    if "storeFile file" in content:
        return
    snippet = (
        "\nandroid {\n"
        "    signingConfigs {\n"
        "        release {\n"
        f"            storeFile file('{signing['keystorePath']}')\n"
        f"            storePassword '{signing['storePassword']}'\n"
        f"            keyAlias '{signing['alias']}'\n"
        f"            keyPassword '{signing['keyPassword']}'\n"
        "        }\n"
        "    }\n"
        "}\n"
    )
    with GRADLE_PATH.open("a") as f:
        f.write(snippet)


def run_cmd(cmd: list[str], cwd: str | None = None) -> None:
    """Run a command and raise on error."""
    subprocess.run(cmd, check=True, cwd=cwd)


def ensure_gradle_wrapper(url: str) -> None:
    """Download the Gradle wrapper JAR if it's missing."""
    if GRADLE_WRAPPER_JAR.exists():
        return
    GRADLE_WRAPPER_JAR.parent.mkdir(parents=True, exist_ok=True)
    urlretrieve(url, GRADLE_WRAPPER_JAR)


def build_android(cfg: Dict[str, Any], release: bool) -> None:
    """Execute npm, capacitor, and gradle steps."""
    run_cmd(["npm", "install"])
    run_cmd(["npm", "run", "build"])
    run_cmd(["npx", "cap", "sync", "android"])
    maybe_inject_signing(cfg["signing"])
    ensure_gradle_wrapper(cfg["gradleWrapperUrl"])
    task = "assembleRelease" if release else "assembleDebug"
    gradle_cmd = [
        "./gradlew",
        task,
        f"-Pandroid.injected.signing.store.file={cfg['signing']['keystorePath']}",
        f"-Pandroid.injected.signing.store.password={cfg['signing']['storePassword']}",
        f"-Pandroid.injected.signing.key.alias={cfg['signing']['alias']}",
        f"-Pandroid.injected.signing.key.password={cfg['signing']['keyPassword']}",
    ]
    run_cmd(gradle_cmd, cwd="android")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--release", action="store_true", help="Build a release APK instead of debug"
    )
    args = parser.parse_args()
    check_tools()
    cfg = load_config(CONFIG_PATH)
    update_mobile_config(cfg)
    build_android(cfg, args.release)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
