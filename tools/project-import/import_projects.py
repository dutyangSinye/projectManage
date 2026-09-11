"""从 xls 台账把项目导入生产系统。

用法:
    # 1) 先备份生产库（默认执行），再 dry-run 校验
    python tools/project-import/import_projects.py --xls <台账.xls>

    # 2) 确认计划无误后真正写入
    python tools/project-import/import_projects.py --xls <台账.xls> --apply

    # 跳过备份
    python tools/project-import/import_projects.py --xls <台账.xls> --apply --no-backup

台账列顺序（首行为表头）:
    项目大类 | 合同类型 | 项目名称 | 项目编号 | 项目负责人 | 工时审批人 | 主管领导 | 所属部门 | 项目状态

设计要点:
- 解析在本地做（xlrd 只在本地 venv），远程容器只接收 JSON 行数据与执行逻辑。
- 远程执行体经 base64 走 stdin 送入容器内的 python，规避多层 shell 引号转义。
- 写入走与 POST /api/v1/admin/projects 相同的业务函数，预算项会自动按大类带出。
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "nas-deploy-mcp"))

from dotenv import load_dotenv  # noqa: E402

from nas_deploy_mcp import core  # noqa: E402

load_dotenv(ROOT / "tools" / "nas-deploy-mcp" / ".env", override=True)
SETTINGS = core.Settings.from_env()

BODY = ROOT / "tools" / "project-import" / "remote_body.py"
CONTAINER = "xinye-workhours-api"
EXPECTED_HEADERS = [
    "项目大类",
    "合同类型",
    "项目名称",
    "项目编号",
    "项目负责人",
    "工时审批人",
    "主管领导",
    "所属部门",
    "项目状态",
]


def read_rows(xls: Path) -> list[list[str]]:
    import xlrd

    book = xlrd.open_workbook(str(xls))
    sheet = book.sheet_by_index(0)
    header = [str(sheet.cell(0, c).value).strip() for c in range(sheet.ncols)]
    if header[: len(EXPECTED_HEADERS)] != EXPECTED_HEADERS:
        print("表头与预期不符：")
        print("  实际:", header)
        print("  预期:", EXPECTED_HEADERS)
        raise SystemExit(1)

    rows: list[list[str]] = []
    for r in range(1, sheet.nrows):
        values: list[str] = []
        for c in range(9):
            v = sheet.cell(r, c).value
            if isinstance(v, float) and v == int(v):
                v = int(v)
            values.append(str(v).strip() if v is not None else "")
        if not any(values):
            continue
        rows.append([v or None for v in values])
    return rows


def backup(client: core.NasClient) -> None:
    import datetime

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    name = f"workhours-preimport-{stamp}.db"
    remote = f"/app/data/backups/{name}"
    sql = (
        "import sqlite3;"
        "src=sqlite3.connect('file:/app/data/workhours.db?mode=ro',uri=True);"
        f"dst=sqlite3.connect('{remote}');"
        "src.backup(dst);"
        "print('backup rows(users)=', dst.execute('select count(*) from users').fetchone()[0]);"
    )
    code, out, err = client.exec(
        f"sudo -n docker exec {CONTAINER} python -c {core.q(sql)}", timeout=180
    )
    print(f"[备份] exit={code} {out.strip()[:200]}")
    if err.strip():
        print("STDERR:", err.strip()[:300])
    if code != 0:
        raise SystemExit("备份失败，终止导入。")


def run_remote(client: core.NasClient, rows: list[list[str]], apply: bool) -> int:
    body = BODY.read_text(encoding="utf-8")
    body = body.replace("__ROWS_JSON__", json.dumps(rows, ensure_ascii=False))
    if "__ROWS_JSON__" in body:
        raise SystemExit("ROWS_JSON 注入失败")
    payload = base64.b64encode(body.encode("utf-8")).decode("ascii")
    flag = "--apply" if apply else ""
    command = (
        f"sudo -n docker exec -i {CONTAINER} sh -c 'base64 -d | python - {flag}' <<'WBEOF'\n"
        f"{payload}\n"
        f"WBEOF"
    )
    code, out, err = client.exec(command, timeout=300)
    print("exit:", code)
    if out.strip():
        print(out.strip()[:12000])
    if err.strip():
        print("STDERR:", err.strip()[:4000])
    return code


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--xls", required=True, help="项目台账 .xls 路径")
    parser.add_argument("--apply", action="store_true", help="真正写入（默认 dry-run）")
    parser.add_argument("--no-backup", action="store_true", help="跳过导入前备份")
    args = parser.parse_args()

    xls = Path(args.xls)
    if not xls.exists():
        print("文件不存在:", xls)
        return 1

    rows = read_rows(xls)
    print(f"从 {xls.name} 读到 {len(rows)} 行项目数据\n")

    with core.NasClient(SETTINGS) as client:
        if args.apply and not args.no_backup:
            backup(client)
        return run_remote(client, rows, args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
