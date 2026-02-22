"""Terminal routes - execute commands (pip install, etc.)"""

import subprocess
import os
import shlex
import time
from pathlib import Path
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.models.user import User
from app.config import settings
from app.services.rate_limiter import rate_limiter

router = APIRouter()


_user_install_windows = {}
_WINDOW_SECONDS = 3600


class TerminalCommandRequest(BaseModel):
    command: str


def _extract_install_packages(command: str) -> list[str]:
    """
    Parse and validate package names from pip install command.
    """
    raw = command.strip()
    if not raw:
        return []

    lowered = raw.lower()
    prefixes = ["pip install ", "pip3 install ", "python -m pip install "]
    prefix = next((p for p in prefixes if lowered.startswith(p)), None)
    if not prefix:
        return []

    pkg_expr = raw[len(prefix):].strip()
    if not pkg_expr:
        return []

    tokens = shlex.split(pkg_expr)
    packages = []
    for token in tokens:
        if token.startswith("-"):
            continue
        package = token.split("==", 1)[0].split(">=", 1)[0].split("<=", 1)[0]
        package = package.strip().lower()
        if package:
            packages.append(package)
    return packages


def _check_install_quota(user_id: int) -> bool:
    now = time.time()
    events = _user_install_windows.setdefault(user_id, [])
    cutoff = now - _WINDOW_SECONDS
    events[:] = [ts for ts in events if ts >= cutoff]
    if len(events) >= settings.TERMINAL_MAX_INSTALLS_PER_USER_PER_HOUR:
        return False
    events.append(now)
    return True


@router.post("/execute")
def execute_command(
    req: TerminalCommandRequest,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """
    Execute terminal command (pip install only for security).
    Packages are installed in user-specific env for the session.
    """
    cmd = req.command.strip()
    if not cmd:
        return {"output": ""}

    if not settings.ENABLE_TERMINAL_INSTALLS:
        return {"output": "Terminal package installs are disabled by admin policy."}

    if not cmd.lower().startswith(("pip install ", "pip3 install ", "python -m pip install ")):
        return {"output": "Allowed: pip install <package> (e.g. pip install numpy)"}

    # User-specific env dir for persistence
    user_env = Path(settings.get_temp_dir()) / f"user_{current_user.id}"
    user_env.mkdir(parents=True, exist_ok=True)

    packages = _extract_install_packages(cmd)

    if not packages:
        return {"output": "Usage: pip install numpy pandas"}
    if len(packages) > settings.TERMINAL_MAX_PACKAGES_PER_COMMAND:
        return {
            "output": f"Too many packages in one command. Max allowed: {settings.TERMINAL_MAX_PACKAGES_PER_COMMAND}"
        }

    disallowed = [p for p in packages if p not in {pkg.lower() for pkg in settings.ALLOWED_PIP_PACKAGES}]
    if disallowed:
        return {
            "output": (
                "Disallowed package(s): "
                + ", ".join(disallowed)
                + ". Allowed: "
                + ", ".join(settings.ALLOWED_PIP_PACKAGES)
            )
        }

    if not _check_install_quota(current_user.id):
        return {
            "output": (
                f"Install quota exceeded. Max {settings.TERMINAL_MAX_INSTALLS_PER_USER_PER_HOUR} "
                "install commands per hour."
            )
        }

    ip = request.client.host if request.client else "unknown"
    min_key = f"highcost:min:terminal:{ip}:{current_user.id}"
    hour_key = f"highcost:hour:terminal:{ip}:{current_user.id}"
    if not rate_limiter.allow(min_key, settings.HIGH_COST_RATE_LIMIT_PER_MINUTE, 60):
        return {"output": "Too many terminal commands. Please wait a minute."}
    if not rate_limiter.allow(hour_key, settings.HIGH_COST_RATE_LIMIT_PER_HOUR, 3600):
        return {"output": "Hourly terminal command limit reached. Try later."}

    try:
        result = subprocess.run(
            ["pip", "install", "--target", str(user_env)] + packages,
            capture_output=True,
            text=True,
            timeout=120,
            env={
                "PATH": os.environ.get("PATH", ""),
                "HOME": os.environ.get("HOME", ""),
                "LANG": os.environ.get("LANG", "C.UTF-8"),
                "PYTHONPATH": str(user_env) + os.pathsep + os.environ.get("PYTHONPATH", ""),
            },
        )
        out = (result.stdout or "") + (result.stderr or "")
        return {"output": out.strip() or "Done"}
    except subprocess.TimeoutExpired:
        return {"output": "Timeout - package may be too large"}
    except Exception as e:
        return {"output": f"Error: {str(e)}"}
