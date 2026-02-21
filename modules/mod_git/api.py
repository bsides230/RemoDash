import os
import shutil
import json
import socket
import datetime
import subprocess
import shlex
from urllib.parse import quote_plus
from typing import List, Optional, Dict, Any
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

git = None
def get_git():
    global git
    if git: return git
    try:
        import git as _git
        git = _git
        return git
    except ImportError:
        return None

from settings_manager import SettingsManager
from core.api.auth import verify_token
from core.api.filesystem import check_path_access

router = APIRouter()
settings_manager = SettingsManager()

# --- Pydantic Models ---
class GitRepoRequest(BaseModel):
    path: str
    message: Optional[str] = None
    branch: Optional[str] = None
    files: Optional[List[str]] = None
    delete_files: Optional[bool] = False

class GitCredentialsRequest(BaseModel):
    username: Optional[str] = None
    token: Optional[str] = None
    git_name: Optional[str] = None
    git_email: Optional[str] = None

class GitCloneRequest(BaseModel):
    url: str
    path: Optional[str] = None
    name: Optional[str] = None
    username: Optional[str] = None
    token: Optional[str] = None

# --- Git Credentials Manager ---
class GitCredentialsManager:
    def __init__(self, data_file="data/git_credentials.json"):
        self.data_file = Path(data_file)
        # Check permissions/ensure dir
        try:
            self.data_file.parent.mkdir(parents=True, exist_ok=True)
        except: pass

    def load(self) -> Dict[str, str]:
        if not self.data_file.exists():
            return {}
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save(self, data: Dict[str, str]):
        try:
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            # Try to set permissions to 600
            try:
                os.chmod(self.data_file, 0o600)
            except: pass
        except Exception as e:
            print(f"Failed to save git credentials: {e}")

    def get_credentials(self):
        return self.load()

git_cred_manager = GitCredentialsManager()

# --- Git Endpoints ---

@router.get("/credentials", dependencies=[Depends(verify_token)])
async def get_git_credentials():
    creds = git_cred_manager.load()
    # Mask token
    if creds.get("token"):
        creds["token"] = "********"
    return creds

@router.post("/credentials", dependencies=[Depends(verify_token)])
async def save_git_credentials(req: GitCredentialsRequest):
    current = git_cred_manager.load()

    # Update fields if provided
    if req.username is not None: current["username"] = req.username
    if req.token is not None: current["token"] = req.token
    if req.git_name is not None: current["git_name"] = req.git_name
    if req.git_email is not None: current["git_email"] = req.git_email

    git_cred_manager.save(current)

    # Also set global git config if git_name/email provided
    _git = get_git()
    if _git and (req.git_name or req.git_email):
        try:
            if req.git_name:
                subprocess.run(["git", "config", "--global", "user.name", req.git_name], check=False)
            if req.git_email:
                subprocess.run(["git", "config", "--global", "user.email", req.git_email], check=False)
        except Exception as e:
            print(f"Failed to set git global config: {e}")

    return {"success": True}

@router.get("/repos", dependencies=[Depends(verify_token)])
async def list_git_repos():
    repos = settings_manager.settings.get("git_repos", [])
    result = []

    # Get current mode and roots for filtering
    mode = settings_manager.settings.get("filesystem_mode", "open")
    allowed_roots = []
    if mode == "jailed":
        root_str = settings_manager.settings.get("filesystem_root")
        if root_str: allowed_roots.append(Path(root_str).expanduser().resolve())
        for er in settings_manager.settings.get("filesystem_extra_roots", []):
             allowed_roots.append(Path(er).expanduser().resolve())

    for path in repos:
        # Check access (Filter out repos outside jail in JAILED mode)
        if mode == "jailed":
            try:
                p_obj = Path(path).expanduser().resolve()
                is_allowed = False
                for ar in allowed_roots:
                    try:
                        if os.path.commonpath([ar, p_obj]) == str(ar):
                            is_allowed = True
                            break
                    except: continue
                if not is_allowed:
                    continue
            except:
                continue

        status = "Unknown"
        branch = "Unknown"
        changed = False
        try:
            _git = get_git()
            if _git:
                r = _git.Repo(path)
                try:
                    branch = r.active_branch.name
                except:
                    branch = "Detached"
                changed = r.is_dirty() or (len(r.untracked_files) > 0)
                status = "Dirty" if changed else "Clean"
        except Exception as e:
            status = f"Error: {str(e)}"

        result.append({
            "path": path,
            "name": os.path.basename(path),
            "status": status,
            "branch": branch,
            "changed": changed
        })
    return result

@router.post("/repos", dependencies=[Depends(verify_token)])
async def add_git_repo(req: GitRepoRequest):
    # Validate path access
    p_obj = check_path_access(req.path)
    p = str(p_obj)

    if not p_obj.exists():
        raise HTTPException(status_code=404, detail="Path does not exist")

    current = settings_manager.settings.get("git_repos", [])
    if p not in current:
        current.append(p)
        settings_manager.settings["git_repos"] = current
        settings_manager.save_settings()
    return {"success": True}

@router.post("/repos/remove", dependencies=[Depends(verify_token)])
async def remove_git_repo(req: GitRepoRequest):
    p = req.path
    current = settings_manager.settings.get("git_repos", [])
    if p in current:
        current.remove(p)
        settings_manager.settings["git_repos"] = current
        settings_manager.save_settings()

    if req.delete_files:
        try:
            # Validate safety
            p_obj = check_path_access(p)
            if p_obj.exists() and p_obj.is_dir():
                shutil.rmtree(p_obj)
        except Exception as e:
            # If removing from settings succeeded but file delete failed, we still return success
            # but maybe log it?
            print(f"Failed to delete repo files: {e}")
            pass

    return {"success": True}

@router.post("/clone", dependencies=[Depends(verify_token)])
async def git_clone(req: GitCloneRequest):
    _git = get_git()
    if not _git: raise HTTPException(status_code=501, detail="GitPython not installed")

    # Determine Destination
    mode = settings_manager.settings.get("git_root_mode", "manual")
    root_path = settings_manager.settings.get("git_root_path", "")

    target_path_str = ""

    if mode == "auto":
        if not root_path:
             raise HTTPException(status_code=400, detail="Git Root Path not configured in settings")

        # Determine name
        name = req.name
        if not name:
             # Try to parse from URL
             try:
                 name = req.url.split("/")[-1]
                 if name.endswith(".git"): name = name[:-4]
             except: pass

        if not name:
             raise HTTPException(status_code=400, detail="Could not determine repository name")

        target_path_str = str(Path(root_path).expanduser() / name)
    else:
        if not req.path:
             raise HTTPException(status_code=400, detail="Path is required in Manual mode")
        target_path_str = req.path

    # Validate destination
    p_obj = check_path_access(target_path_str)

    if p_obj.exists() and any(p_obj.iterdir()):
         raise HTTPException(status_code=400, detail="Destination path exists and is not empty")

    try:
        # Prepare Environment for SSH (Skip Host Key Checking)
        env = os.environ.copy()
        env["GIT_SSH_COMMAND"] = "ssh -o StrictHostKeyChecking=no"

        clone_url = req.url

        # Load Credentials (req or global)
        creds = git_cred_manager.load()
        username = req.username or creds.get("username")
        token = req.token or creds.get("token")

        if username and token:
            askpass_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "git_askpass.py")
            if os.path.exists(askpass_script):
                 env["GIT_ASKPASS"] = askpass_script
                 env["GIT_USERNAME"] = username
                 env["GIT_PASSWORD"] = token
                 env["GIT_TERMINAL_PROMPT"] = "0"
            else:
                 # Fallback: Inject into URL
                 safe_user = quote_plus(username)
                 safe_token = quote_plus(token)
                 if clone_url.startswith("https://"):
                     clone_url = clone_url.replace("https://", f"https://{safe_user}:{safe_token}@", 1)
                 elif clone_url.startswith("http://"):
                     clone_url = clone_url.replace("http://", f"http://{safe_user}:{safe_token}@", 1)

        _git.Repo.clone_from(clone_url, str(p_obj), env=env)

        # Auto-add to known repos
        current = settings_manager.settings.get("git_repos", [])
        if str(p_obj) not in current:
            current.append(str(p_obj))
            settings_manager.settings["git_repos"] = current
            settings_manager.save_settings()

        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status", dependencies=[Depends(verify_token)])
async def get_git_status(path: str):
    check_path_access(path) # Validate Access
    _git = get_git()
    if not _git:
         raise HTTPException(status_code=501, detail="GitPython not installed")
    try:
        try:
            r = _git.Repo(path)
        except _git.exc.InvalidGitRepositoryError:
            return {"error": "Invalid Git Repository", "branch": "Invalid", "files": [], "history": []}
        except _git.exc.NoSuchPathError:
            return {"error": "Path not found", "branch": "Missing", "files": [], "history": []}

        diffs = []
        # Staged
        try:
            for item in r.index.diff(None):
                diffs.append({"file": item.a_path, "type": "modified", "staged": False})
        except: pass

        # Diff against HEAD (only if HEAD exists)
        try:
            # Check if HEAD is valid
            _ = r.head.commit
            for item in r.index.diff("HEAD"):
                diffs.append({"file": item.a_path, "type": "modified", "staged": True})
        except ValueError:
            # Empty repo (no commits)
            pass
        except: pass

        # Untracked
        try:
            for f in r.untracked_files:
                diffs.append({"file": f, "type": "untracked", "staged": False})
        except: pass

        history = []
        try:
            for c in list(r.iter_commits(max_count=10)):
                history.append({
                    "hexsha": c.hexsha[:7],
                    "message": c.message.strip(),
                    "author": str(c.author),
                    "time": c.committed_datetime.isoformat()
                })
        except: pass

        branch_name = "Unknown"
        try:
            if r.head.is_detached:
                branch_name = "Detached"
            else:
                branch_name = r.active_branch.name
        except:
            # Likely empty repo without branch yet
            try: branch_name = r.git.branch(show_current=True) or "No Branch"
            except: branch_name = "No Branch"

        return {
            "branch": branch_name,
            "files": diffs,
            "history": history
        }
    except Exception as e:
        # Return structured error instead of 500
        return {"error": str(e), "branch": "Error", "files": [], "history": []}

@router.post("/commit", dependencies=[Depends(verify_token)])
async def git_commit(req: GitRepoRequest):
    check_path_access(req.path) # Validate Access
    _git = get_git()
    if not _git: raise HTTPException(status_code=501)
    try:
        r = _git.Repo(req.path)
        if req.files and len(req.files) > 0:
            r.git.reset()
            for f in req.files:
                r.git.add(f)
        else:
            r.git.add(A=True)
        r.index.commit(req.message or "Update from RemoDash")
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/diff", dependencies=[Depends(verify_token)])
async def get_git_diff(path: str, file: str):
    check_path_access(path) # Validate Access
    _git = get_git()
    if not _git: raise HTTPException(status_code=501)
    try:
        r = _git.Repo(path)
        try:
            diff = r.git.diff('HEAD', file)
        except:
            try:
                diff = r.git.diff(file)
                if not diff and (file in r.untracked_files):
                    with open(os.path.join(path, file), 'r', encoding='utf-8', errors='replace') as f:
                        diff = f.read()
            except:
                diff = ""
        return {"diff": diff}
    except Exception as e:
        return {"diff": f"Error: {str(e)}"}

@router.post("/push", dependencies=[Depends(verify_token)])
async def git_push(req: GitRepoRequest):
    check_path_access(req.path) # Validate Access
    _git = get_git()
    if not _git: raise HTTPException(status_code=501)
    try:
        r = _git.Repo(req.path)
        origin = r.remote(name='origin')

        env = {"GIT_SSH_COMMAND": "ssh -o StrictHostKeyChecking=no"}
        creds = git_cred_manager.load()
        if creds.get("username") and creds.get("token"):
            askpass_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "git_askpass.py")
            if os.path.exists(askpass_script):
                 env["GIT_ASKPASS"] = askpass_script
                 env["GIT_USERNAME"] = creds["username"]
                 env["GIT_PASSWORD"] = creds["token"]
                 env["GIT_TERMINAL_PROMPT"] = "0"

        with r.git.custom_environment(**env):
            origin.push()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/pull", dependencies=[Depends(verify_token)])
async def git_pull(req: GitRepoRequest):
    check_path_access(req.path) # Validate Access
    _git = get_git()
    if not _git: raise HTTPException(status_code=501)
    try:
        r = _git.Repo(req.path)
        origin = r.remote(name='origin')

        env = {"GIT_SSH_COMMAND": "ssh -o StrictHostKeyChecking=no"}
        creds = git_cred_manager.load()
        if creds.get("username") and creds.get("token"):
            askpass_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "git_askpass.py")
            if os.path.exists(askpass_script):
                 env["GIT_ASKPASS"] = askpass_script
                 env["GIT_USERNAME"] = creds["username"]
                 env["GIT_PASSWORD"] = creds["token"]
                 env["GIT_TERMINAL_PROMPT"] = "0"

        with r.git.custom_environment(**env):
            origin.pull()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stash", dependencies=[Depends(verify_token)])
async def git_stash(req: GitRepoRequest):
    check_path_access(req.path) # Validate Access
    _git = get_git()
    if not _git: raise HTTPException(status_code=501)
    try:
        r = _git.Repo(req.path)
        try: _ = r.head.commit
        except ValueError: raise Exception("Cannot stash: No commits yet")

        r.git.stash('save', req.message or f"Stash from RemoDash {datetime.datetime.now()}")
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stash/pop", dependencies=[Depends(verify_token)])
async def git_stash_pop(req: GitRepoRequest):
    check_path_access(req.path) # Validate Access
    _git = get_git()
    if not _git: raise HTTPException(status_code=501)
    try:
        r = _git.Repo(req.path)
        r.git.stash('pop')
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/discard", dependencies=[Depends(verify_token)])
async def git_discard(req: GitRepoRequest):
    check_path_access(req.path) # Validate Access
    _git = get_git()
    if not _git: raise HTTPException(status_code=501)
    try:
        r = _git.Repo(req.path)

        has_commits = True
        try: _ = r.head.commit
        except ValueError: has_commits = False

        if req.files and len(req.files) > 0:
            # Discard specific files
            untracked = set(r.untracked_files)

            for f in req.files:
                fp = os.path.join(req.path, f)
                if f in untracked:
                     if os.path.exists(fp):
                         try:
                            if os.path.isdir(fp): shutil.rmtree(fp)
                            else: os.remove(fp)
                         except: pass
                else:
                    if has_commits:
                        r.git.checkout('HEAD', '--', f)
                    else:
                        # No commits: unstage and delete
                        try:
                            r.git.rm('--cached', f)
                            if os.path.exists(fp): os.remove(fp)
                        except: pass
        else:
            # Discard all
            if has_commits:
                r.git.reset('--hard', 'HEAD')
            else:
                # No commits: Unstage all
                try: r.git.rm('-r', '--cached', '.', ignore_unmatch=True)
                except: pass

            r.git.clean('-fd') # Clean untracked

        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- SSH Key Management ---

@router.get("/ssh_key", dependencies=[Depends(verify_token)])
async def get_ssh_key():
    """Checks for SSH key and returns public key + fingerprint."""
    ssh_dir = Path.home() / ".ssh"
    # Prefer Ed25519, fall back to RSA
    key_types = ["id_ed25519", "id_rsa"]
    found_key = None

    for k in key_types:
        if (ssh_dir / k).exists() and (ssh_dir / f"{k}.pub").exists():
            found_key = ssh_dir / k
            break

    if not found_key:
        return {"exists": False}

    try:
        pub_path = found_key.with_suffix(".pub")
        pub_content = pub_path.read_text(encoding="utf-8").strip()

        # Get Fingerprint (Randomart)
        # ssh-keygen -lv -f /path/to/key
        proc = subprocess.run(
            ["ssh-keygen", "-lv", "-f", str(found_key)],
            capture_output=True, text=True
        )
        fingerprint = proc.stdout

        return {
            "exists": True,
            "type": found_key.name,
            "public_key": pub_content,
            "fingerprint": fingerprint
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read key: {str(e)}")

@router.post("/ssh_key/generate", dependencies=[Depends(verify_token)])
async def generate_ssh_key():
    """Generates a new Ed25519 SSH key pair."""
    ssh_dir = Path.home() / ".ssh"
    ssh_dir.mkdir(parents=True, exist_ok=True)
    key_path = ssh_dir / "id_ed25519"

    if key_path.exists():
        raise HTTPException(status_code=400, detail="SSH Key already exists")

    try:
        # Generate Ed25519 key, no passphrase (-N ""), comment "remodash@local"
        cmd = [
            "ssh-keygen", "-t", "ed25519",
            "-C", "remodash@local",
            "-f", str(key_path),
            "-N", ""
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)

        if proc.returncode != 0:
            raise Exception(proc.stderr)

        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")
