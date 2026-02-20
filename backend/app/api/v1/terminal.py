"""Terminal routes - execute commands (pip install, etc.)"""

import subprocess
import os
from pathlib import Path
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.models.user import User
from app.config import settings
from app.core.exceptions import ValidationError

router = APIRouter()

# Allowed commands (whitelist for security)
ALLOWED_PREFIXES = ['pip install ', 'pip3 install ', 'python -m pip install ']


class TerminalCommandRequest(BaseModel):
    command: str


@router.post("/execute")
def execute_command(
    req: TerminalCommandRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Execute terminal command (pip install only for security).
    Packages are installed in user-specific env for the session.
    """
    cmd = req.command.strip()
    if not cmd:
        return {"output": ""}

    # Only allow pip install
    allowed = False
    for prefix in ALLOWED_PREFIXES:
        if cmd.lower().startswith(prefix.lower()):
            allowed = True
            break
    if not allowed:
        return {"output": "Allowed: pip install <package> (e.g. pip install numpy)"}

    # User-specific env dir for persistence
    user_env = Path(settings.get_temp_dir()) / f"user_{current_user.id}"
    user_env.mkdir(parents=True, exist_ok=True)

    # Extract package names
    for prefix in ['pip install ', 'pip3 install ', 'python -m pip install ']:
        if cmd.lower().startswith(prefix.lower()):
            packages = cmd[len(prefix):].strip().split()
            break
    else:
        packages = []

    if not packages:
        return {"output": "Usage: pip install numpy pandas"}

    try:
        result = subprocess.run(
            ["pip", "install", "--target", str(user_env)] + packages,
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ, "PYTHONPATH": str(user_env) + os.pathsep + os.environ.get("PYTHONPATH", "")}
        )
        out = (result.stdout or "") + (result.stderr or "")
        return {"output": out.strip() or "Done"}
    except subprocess.TimeoutExpired:
        return {"output": "Timeout - package may be too large"}
    except Exception as e:
        return {"output": f"Error: {str(e)}"}
