"""Safe, allow-listed deployment operations for the Xinye NAS target."""

from __future__ import annotations

import datetime as dt
import json
import os
import posixpath
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MAX_OUTPUT = 12_000
BACKUP_PATTERN = re.compile(r"^\.backup-[A-Za-z0-9_.-]+$")
SERVICE_NAMES = {"backend", "frontend", "all"}
DEFAULT_RUNTIME_IMAGE = "xinye-project-management_runtime:20260905"


def clip(value: str, limit: int = MAX_OUTPUT) -> str:
    """Keep tool responses bounded while retaining the beginning and end."""
    if len(value) <= limit:
        return value
    head = limit * 2 // 3
    return value[:head] + "\n...[truncated]...\n" + value[-(limit - head - 22):]


@dataclass(frozen=True)
class Settings:
    """Runtime configuration loaded from environment variables."""

    host: str
    ssh_port: int
    username: str
    password: str
    private_key: str
    deploy_dir: str
    http_url: str
    project_root: Path
    ssh_timeout: int
    build_timeout: int
    pnpm_bin: str
    node_bin_dir: str
    known_hosts: str
    strict_host_key: bool
    compose_bin: str
    runtime_image: str

    @classmethod
    def from_env(cls) -> "Settings":
        root_value = os.getenv("PROJECT_ROOT", "").strip()
        root = Path(root_value) if root_value else Path(__file__).resolve().parents[3]
        return cls(
            host=os.getenv("NAS_HOST", "").strip(),
            ssh_port=int(os.getenv("NAS_SSH_PORT", "22")),
            username=os.getenv("NAS_USERNAME", "").strip(),
            password=os.getenv("NAS_PASSWORD", ""),
            private_key=os.getenv("NAS_PRIVATE_KEY", "").strip(),
            deploy_dir=os.getenv("NAS_DEPLOY_DIR", "/volume1/docker/xinye-workhours").strip(),
            http_url=os.getenv("NAS_HTTP_URL", "http://192.168.112.188:8088").rstrip("/"),
            project_root=root,
            ssh_timeout=int(os.getenv("NAS_SSH_TIMEOUT", "20")),
            build_timeout=int(os.getenv("NAS_BUILD_TIMEOUT", "900")),
            pnpm_bin=os.getenv("PNPM_BIN", "").strip(),
            node_bin_dir=os.getenv("NODE_BIN_DIR", "").strip(),
            known_hosts=os.getenv("NAS_KNOWN_HOSTS", "").strip(),
            strict_host_key=os.getenv("NAS_STRICT_HOST_KEY", "false").lower() in {"1", "true", "yes"},
            compose_bin=os.getenv("NAS_COMPOSE_BIN", "docker compose").strip(),
            runtime_image=os.getenv("NAS_RUNTIME_IMAGE", DEFAULT_RUNTIME_IMAGE).strip() or DEFAULT_RUNTIME_IMAGE,
        )

    def validate(self) -> None:
        """Validate required settings before opening an SSH connection."""
        missing = [name for name, value in (("NAS_HOST", self.host), ("NAS_USERNAME", self.username)) if not value]
        if not self.password and not self.private_key:
            missing.append("NAS_PASSWORD or NAS_PRIVATE_KEY")
        if missing:
            raise ValueError("Missing MCP configuration: " + ", ".join(missing))
        if not self.deploy_dir.startswith("/") or "\n" in self.deploy_dir:
            raise ValueError("NAS_DEPLOY_DIR must be an absolute POSIX path")
        if not 1 <= self.ssh_port <= 65535:
            raise ValueError("NAS_SSH_PORT must be between 1 and 65535")
        if self.compose_bin not in {"docker compose", "docker-compose"}:
            raise ValueError("NAS_COMPOSE_BIN must be docker compose or docker-compose")
        if "\n" in self.runtime_image or "\r" in self.runtime_image or not self.runtime_image:
            raise ValueError("NAS_RUNTIME_IMAGE must be a non-empty single-line image name")


class NasClient:
    """SSH/SFTP adapter with commands restricted to the configured project."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.client: Any | None = None

    def __enter__(self) -> "NasClient":
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        if self.client is not None:
            self.client.close()
            self.client = None

    def connect(self) -> None:
        self.settings.validate()
        try:
            import paramiko
        except ImportError as exc:
            raise RuntimeError("paramiko is not installed; run the MCP installer first") from exc
        client = paramiko.SSHClient()
        if self.settings.known_hosts:
            client.load_host_keys(self.settings.known_hosts)
            client.set_missing_host_key_policy(paramiko.RejectPolicy())
        elif self.settings.strict_host_key:
            client.load_system_host_keys()
            client.set_missing_host_key_policy(paramiko.RejectPolicy())
        else:
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        args: dict[str, Any] = {
            "hostname": self.settings.host,
            "port": self.settings.ssh_port,
            "username": self.settings.username,
            "timeout": self.settings.ssh_timeout,
            "banner_timeout": self.settings.ssh_timeout,
            "auth_timeout": self.settings.ssh_timeout,
            "look_for_keys": not bool(self.settings.password),
            "allow_agent": not bool(self.settings.password),
        }
        if self.settings.private_key:
            args["key_filename"] = self.settings.private_key
        elif self.settings.password:
            args["password"] = self.settings.password
        client.connect(**args)
        self.client = client

    def exec(self, command: str, timeout: int | None = None) -> tuple[int, str, str]:
        """Run an internally generated command and return exit code/stdout/stderr."""
        if self.client is None:
            raise RuntimeError("NAS connection is not open")
        stdin_data = ""
        effective_command = command
        # Some NAS accounts have sudo permission but do not have NOPASSWD enabled.
        # Run the complete generated command under one sudo process. This also
        # supports sudo policies that do not persist credentials without a tty.
        if self.settings.password and "sudo -n" in command:
            import shlex

            effective_command = f"sudo -S -p '' sh -c {shlex.quote(command)}"
            stdin_data = self.settings.password + "\n"
        stdin, stdout, stderr = self.client.exec_command(
            effective_command,
            timeout=timeout or self.settings.ssh_timeout,
        )
        if stdin_data:
            stdin.write(stdin_data)
            stdin.flush()
            stdin.channel.shutdown_write()
        code = stdout.channel.recv_exit_status()
        return code, stdout.read().decode("utf-8", errors="replace"), stderr.read().decode("utf-8", errors="replace")

    def sftp(self) -> Any:
        if self.client is None:
            raise RuntimeError("NAS connection is not open")
        return self.client.open_sftp()


def q(value: str) -> str:
    """Quote a path for the NAS POSIX shell."""
    import shlex

    return shlex.quote(value)


def base_path(settings: Settings, *parts: str) -> str:
    return posixpath.join(settings.deploy_dir.rstrip("/"), *parts)


def compose_command(settings: Settings, action: str) -> str:
    actions = {
        "config": "config -q",
        "up": "up -d --build --force-recreate backend frontend",
        "ps": "ps --all",
    }
    if action not in actions:
        raise ValueError("Unsupported compose action")
    command = f"sudo -n {settings.compose_bin} -f {q(base_path(settings, 'deploy', 'docker-compose.yml'))} {actions[action]}"
    if action == "up":
        # docker-compose 1.29 cannot recreate images produced by Docker 28 because
        # it expects the removed ContainerConfig field. Remove only containers whose
        # names match the two application services; the compose volume is untouched.
        cleanup = (
            "sudo -n docker ps -aq --filter name=xinye-workhours-api | "
            "xargs -r sudo -n docker rm -f >/dev/null 2>&1 || true; "
            "sudo -n docker ps -aq --filter name=xinye-workhours-web | "
            "xargs -r sudo -n docker rm -f >/dev/null 2>&1 || true"
        )
        return f"({cleanup}; {command})"
    return command


def runtime_image_command(settings: Settings) -> str:
    """Build the pinned LibreOffice runtime only when it is absent on the NAS."""
    image = q(settings.runtime_image)
    dockerfile = q(base_path(settings, "deploy", "Dockerfile.runtime"))
    context = q(settings.deploy_dir)
    # The short-circuit form is safe to embed in the release/rollback shell script.
    # Older backups may not have Dockerfile.runtime; their original Compose build is
    # allowed to run unchanged.
    return f"(sudo -n docker image inspect {image} >/dev/null 2>&1 || [ ! -f {dockerfile} ] || sudo -n docker build --pull=false -f {dockerfile} -t {image} {context})"


def http_health(settings: Settings) -> dict[str, Any]:
    """Read the health endpoint without exposing response secrets."""
    url = settings.http_url + "/health"
    request = urllib.request.Request(url, headers={"User-Agent": "xinye-nas-deploy-mcp/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=settings.ssh_timeout) as response:
            body = response.read(2000).decode("utf-8", errors="replace")
            try:
                payload: Any = json.loads(body)
            except json.JSONDecodeError:
                payload = body
            return {"ok": True, "status_code": response.status, "url": url, "response": payload}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status_code": exc.code, "url": url, "error": str(exc)}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"ok": False, "url": url, "error": str(exc)}


def wait_http_health(settings: Settings, attempts: int = 15, interval_seconds: float = 2) -> dict[str, Any]:
    """Wait for the recreated frontend and backend containers to become ready."""
    last_result: dict[str, Any] = {"ok": False, "error": "health check was not attempted"}
    for attempt in range(1, max(1, attempts) + 1):
        last_result = http_health(settings)
        last_result["attempt"] = attempt
        if last_result.get("ok"):
            return last_result
        if attempt < attempts:
            time.sleep(max(0, interval_seconds))
    return last_result


def local_build(settings: Settings) -> dict[str, Any]:
    """Build the frontend before deployment and return bounded output."""
    frontend = settings.project_root / "frontend"
    if not (frontend / "package.json").is_file():
        raise FileNotFoundError(f"Frontend project not found: {frontend}")
    pnpm = settings.pnpm_bin or shutil.which("pnpm.cmd") or shutil.which("pnpm")
    if not pnpm:
        raise RuntimeError("pnpm was not found; set PNPM_BIN to the pnpm executable")
    build_env = os.environ.copy()
    if settings.node_bin_dir:
        # Windows environment keys are case-insensitive; preserve the existing
        # spelling so a pre-existing ``Path`` entry cannot shadow this update.
        path_key = next((key for key in build_env if key.lower() == "path"), "PATH")
        build_env[path_key] = settings.node_bin_dir + os.pathsep + build_env.get(path_key, "")
    process = subprocess.run(
        [pnpm, "build"], cwd=frontend, text=True, capture_output=True,
        timeout=settings.build_timeout, check=False, env=build_env,
    )
    output = clip((process.stdout or "") + ("\n" + process.stderr if process.stderr else ""))
    if process.returncode != 0:
        raise RuntimeError(f"Frontend build failed (exit {process.returncode})\n{output}")
    return {"command": f"{pnpm} build", "output": output}


def local_payload(settings: Settings) -> dict[str, Path]:
    """Return the exact local directories allowed into a release."""
    payload = {
        "dist": settings.project_root / "frontend" / "dist",
        "backend/app": settings.project_root / "backend" / "app",
        "backend/requirements.txt": settings.project_root / "backend" / "requirements.txt",
        "backend/Dockerfile": settings.project_root / "backend" / "Dockerfile",
        "deploy": settings.project_root / "deploy",
    }
    missing = [f"{name}: {path}" for name, path in payload.items() if not path.exists()]
    if missing:
        raise FileNotFoundError("Release directories missing: " + "; ".join(missing))
    return payload


def remote_mkdir(sftp: Any, directory: str) -> None:
    parts = directory.strip("/").split("/")
    current = ""
    for part in parts:
        current += "/" + part
        try:
            sftp.stat(current)
        except OSError:
            sftp.mkdir(current)


def upload_directory(sftp: Any, local_dir: Path, remote_dir: str, skip_names: set[str] | None = None) -> int:
    """Upload a directory tree through SFTP and return the file count."""
    skip_names = skip_names or set()
    remote_mkdir(sftp, remote_dir)
    count = 0
    for path in local_dir.rglob("*"):
        if path.name in skip_names:
            continue
        target = posixpath.join(remote_dir, path.relative_to(local_dir).as_posix())
        if path.is_dir():
            remote_mkdir(sftp, target)
        elif path.is_file():
            remote_mkdir(sftp, posixpath.dirname(target))
            sftp.put(str(path), target)
            count += 1
    return count


def upload_path(sftp: Any, local_path: Path, remote_path: str, skip_names: set[str] | None = None) -> int:
    """Upload a release directory or a single release file through SFTP."""
    if local_path.is_dir():
        return upload_directory(sftp, local_path, remote_path, skip_names=skip_names)
    if local_path.is_file() and local_path.name not in (skip_names or set()):
        remote_mkdir(sftp, posixpath.dirname(remote_path))
        sftp.put(str(local_path), remote_path)
        return 1
    return 0


def release_names() -> tuple[str, str]:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    token = uuid.uuid4().hex[:8]
    return f".mcp-staging-{stamp}-{token}", f".backup-mcp-{stamp}-{token}"


def create_backup(settings: Settings, client: NasClient, prefix: str = ".backup-mcp") -> str:
    """Create a timestamped deployment-file backup, excluding Docker volumes."""
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    name = f"{prefix}-{stamp}-{uuid.uuid4().hex[:8]}"
    base = q(settings.deploy_dir)
    target = q(base_path(settings, name))
    command = f"""set -eu
mkdir -p {target} {target}/backend
for item in deploy dist; do
  if [ -d {base}/$item ]; then cp -a {base}/$item {target}/$item; fi
done
if [ -d {base}/backend/app ]; then cp -a {base}/backend/app {target}/backend/app; fi
if [ -f {base}/backend/requirements.txt ]; then cp -a {base}/backend/requirements.txt {target}/backend/requirements.txt; fi
if [ -f {base}/backend/Dockerfile ]; then cp -a {base}/backend/Dockerfile {target}/backend/Dockerfile; fi
printf '%s' {q(name)}
"""
    code, stdout, stderr = client.exec(command)
    if code != 0:
        raise RuntimeError(f"NAS backup failed\n{clip(stderr or stdout)}")
    return stdout.strip() or name


def apply_release(settings: Settings, client: NasClient, staging_name: str, backup_name: str) -> dict[str, Any]:
    """Replace release files, validate Compose, recreate services, and restore on failure."""
    base = q(settings.deploy_dir)
    staging = q(base_path(settings, staging_name))
    backup = q(base_path(settings, backup_name))
    config = compose_command(settings, "config")
    up = compose_command(settings, "up")
    script = f"""set -eu
base={base}
staging={staging}
backup={backup}
restore() {{
  rm -rf "$base/deploy" "$base/dist" "$base/backend/app" "$base/backend/requirements.txt" "$base/backend/Dockerfile"
  [ -d "$backup/deploy" ] && cp -a "$backup/deploy" "$base/deploy" || true
  [ -d "$backup/dist" ] && cp -a "$backup/dist" "$base/dist" || true
  [ -d "$backup/backend/app" ] && mkdir -p "$base/backend" && cp -a "$backup/backend/app" "$base/backend/app" || true
  [ -f "$backup/backend/requirements.txt" ] && mkdir -p "$base/backend" && cp -a "$backup/backend/requirements.txt" "$base/backend/requirements.txt" || true
  [ -f "$backup/backend/Dockerfile" ] && mkdir -p "$base/backend" && cp -a "$backup/backend/Dockerfile" "$base/backend/Dockerfile" || true
}}
mkdir -p "$base/backend"
rm -rf "$base/deploy" "$base/dist" "$base/backend/app" "$base/backend/requirements.txt" "$base/backend/Dockerfile"
mv "$staging/deploy" "$base/deploy"
mv "$staging/dist" "$base/dist"
mv "$staging/backend/app" "$base/backend/app"
mv "$staging/backend/requirements.txt" "$base/backend/requirements.txt"
mv "$staging/backend/Dockerfile" "$base/backend/Dockerfile"
if [ -f "$backup/deploy/.env" ] && [ ! -f "$base/deploy/.env" ]; then cp "$backup/deploy/.env" "$base/deploy/.env"; fi
if ! {config}; then restore; rm -rf "$staging"; exit 20; fi
if ! {runtime_image_command(settings)}; then restore; rm -rf "$staging"; exit 22; fi
if ! {up}; then restore; {up} || true; rm -rf "$staging"; exit 21; fi
rm -rf "$staging"
printf 'release applied'
"""
    code, stdout, stderr = client.exec(script, timeout=max(settings.ssh_timeout, 600))
    if code != 0:
        raise RuntimeError(f"NAS release failed and previous files were restored\n{clip(stderr or stdout)}")
    return {"output": clip(stdout), "backup": backup_name}


def rollback_release(settings: Settings, client: NasClient, backup_name: str) -> dict[str, Any]:
    """Restore a validated backup and recreate services with failure recovery."""
    if not BACKUP_PATTERN.fullmatch(backup_name):
        raise ValueError("backup_name must be a .backup-* directory name")
    recovery = create_backup(settings, client, prefix=".backup-mcp-before-rollback")
    base = q(settings.deploy_dir)
    selected = q(base_path(settings, backup_name))
    current = q(base_path(settings, recovery))
    config = compose_command(settings, "config")
    up = compose_command(settings, "up")
    script = f"""set -eu
base={base}
selected={selected}
current={current}
restore_current() {{
  rm -rf "$base/deploy" "$base/dist" "$base/backend/app" "$base/backend/requirements.txt" "$base/backend/Dockerfile"
  [ -d "$current/deploy" ] && cp -a "$current/deploy" "$base/deploy" || true
  [ -d "$current/dist" ] && cp -a "$current/dist" "$base/dist" || true
  [ -d "$current/backend/app" ] && mkdir -p "$base/backend" && cp -a "$current/backend/app" "$base/backend/app" || true
  [ -f "$current/backend/requirements.txt" ] && mkdir -p "$base/backend" && cp -a "$current/backend/requirements.txt" "$base/backend/requirements.txt" || true
  [ -f "$current/backend/Dockerfile" ] && mkdir -p "$base/backend" && cp -a "$current/backend/Dockerfile" "$base/backend/Dockerfile" || true
}}
test -f "$selected/deploy/docker-compose.yml"
test -d "$selected/dist"
test -d "$selected/backend/app"
rm -rf "$base/deploy" "$base/dist" "$base/backend/app" "$base/backend/requirements.txt" "$base/backend/Dockerfile"
cp -a "$selected/deploy" "$base/deploy"
cp -a "$selected/dist" "$base/dist"
mkdir -p "$base/backend"
cp -a "$selected/backend/app" "$base/backend/app"
if [ -f "$selected/backend/requirements.txt" ]; then cp -a "$selected/backend/requirements.txt" "$base/backend/requirements.txt"; elif [ -f "$current/backend/requirements.txt" ]; then cp -a "$current/backend/requirements.txt" "$base/backend/requirements.txt"; fi
if [ -f "$selected/backend/Dockerfile" ]; then cp -a "$selected/backend/Dockerfile" "$base/backend/Dockerfile"; else cp -a "$current/backend/Dockerfile" "$base/backend/Dockerfile"; fi
if ! {config}; then restore_current; exit 30; fi
if ! {runtime_image_command(settings)}; then restore_current; exit 32; fi
if ! {up}; then restore_current; {up} || true; exit 31; fi
printf 'rollback applied'
"""
    code, stdout, stderr = client.exec(script, timeout=max(settings.ssh_timeout, 600))
    if code != 0:
        raise RuntimeError(f"NAS rollback failed and current files were restored\n{clip(stderr or stdout)}")
    return {"output": clip(stdout), "recovery_backup": recovery}


def tool_health() -> dict[str, Any]:
    settings = Settings.from_env()
    result: dict[str, Any] = {"target": settings.host or "(not configured)", "http": http_health(settings)}
    try:
        with NasClient(settings) as client:
            code, stdout, stderr = client.exec("printf connected")
            result["ssh"] = {"ok": code == 0, "output": clip(stdout), "error": clip(stderr)}
    except Exception as exc:
        result["ssh"] = {"ok": False, "error": str(exc)}
    result["ok"] = bool(result["http"].get("ok")) and bool(result["ssh"].get("ok"))
    return result


def tool_status() -> dict[str, Any]:
    settings = Settings.from_env()
    with NasClient(settings) as client:
        code, stdout, stderr = client.exec(compose_command(settings, "ps"))
    return {"ok": code == 0, "exit_code": code, "output": clip(stdout), "error": clip(stderr)}


def tool_logs(service: str, tail: int) -> dict[str, Any]:
    settings = Settings.from_env()
    if service not in SERVICE_NAMES:
        raise ValueError("service must be backend, frontend, or all")
    tail = max(1, min(int(tail), 200))
    services = "backend frontend" if service == "all" else service
    command = f"sudo -n {settings.compose_bin} -f {q(base_path(settings, 'deploy', 'docker-compose.yml'))} logs --tail={tail} {services}"
    with NasClient(settings) as client:
        code, stdout, stderr = client.exec(command, timeout=max(settings.ssh_timeout, 60))
    return {"ok": code == 0, "exit_code": code, "output": clip(stdout), "error": clip(stderr)}


def tool_backup() -> dict[str, Any]:
    settings = Settings.from_env()
    with NasClient(settings) as client:
        name = create_backup(settings, client)
    return {"ok": True, "backup_name": name, "backup_path": base_path(settings, name), "data_volume_unchanged": True}


def tool_deploy(confirm: bool) -> dict[str, Any]:
    settings = Settings.from_env()
    plan = {
        "target": f"{settings.host}:{settings.ssh_port}",
        "deploy_dir": settings.deploy_dir,
        "actions": ["pnpm build", "upload dist/backend/app/backend/requirements.txt/backend/Dockerfile/deploy (including Dockerfile.runtime)", "create backup", "compose config", "build runtime image only if absent", "recreate backend/frontend", "HTTP health check"],
        "data_volume_unchanged": True,
    }
    if not confirm:
        return {"ok": True, "requires_confirmation": True, "plan": plan, "message": "Preview only. Call nas_deploy with confirm=true to execute."}
    build = local_build(settings)
    payload = local_payload(settings)
    staging_name, _ = release_names()
    with NasClient(settings) as client:
        try:
            sftp = client.sftp()
            try:
                staging_dir = base_path(settings, staging_name)
                for name, local_path in payload.items():
                    skip = {".env"} if name == "deploy" else set()
                    upload_path(sftp, local_path, posixpath.join(staging_dir, name), skip_names=skip)
            finally:
                sftp.close()
            backup_name = create_backup(settings, client)
            apply_result = apply_release(settings, client, staging_name, backup_name)
        except Exception:
            client.exec(f"rm -rf {q(base_path(settings, staging_name))}")
            raise
    health = wait_http_health(settings)
    return {"ok": bool(health.get("ok")), "plan": plan, "build": build, "backup_name": backup_name, "release": apply_result, "health": health}


def tool_rollback(backup_name: str, confirm: bool) -> dict[str, Any]:
    settings = Settings.from_env()
    if not BACKUP_PATTERN.fullmatch(backup_name):
        raise ValueError("backup_name must be a .backup-* directory name")
    if not confirm:
        return {"ok": True, "requires_confirmation": True, "backup_name": backup_name, "message": "Preview only. Call nas_rollback with confirm=true to execute."}
    with NasClient(settings) as client:
        result = rollback_release(settings, client, backup_name)
    health = wait_http_health(settings)
    return {"ok": bool(health.get("ok")), "backup_name": backup_name, "rollback": result, "health": health}
