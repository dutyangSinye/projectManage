"""Validate and import worklog rows copied from the Feishu Bitable.

The script is intentionally read-only unless ``--apply`` is supplied. It is
designed to run against the SQLite database inside the API container.
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


HEADERS = [
    "项目", "关联项目", "项目阶段", "工时类型", "开始时间", "结束时间",
    "工作描述", "提交人", "二级部门", "一级部门", "状态", "填报日期",
    "审批状态", "审核意见", "工时核算", "项目负责人", "审批人",
    "审批通知状态", "结果通知状态",
]

STATUS_MAP = {"已通过": "APPROVED", "待审核": "PENDING_APPROVAL", "": "DRAFT"}
WORK_TYPE_MAP = {"项目工时": "PROJECT", "管理工时": "MANAGEMENT", "其它工时": "OTHER"}
WORK_STATUS_MAP = {"本地": "LOCAL", "出差": "BUSINESS_TRIP", "异地办公": "REMOTE", "休假": "LEAVE"}

# The Bitable displays this user's mobile number in the submitter/owner field.
SOURCE_USER_ALIASES = {"18583790091": "牛智祥"}


def parse_date(value: str, field: str) -> str:
    try:
        return datetime.strptime(value.strip(), "%Y/%m/%d").strftime("%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"{field} 日期格式错误: {value!r}") from exc


def parse_timestamp(value: str, field: str) -> str:
    return parse_date(value, field) + " 00:00:00"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle, delimiter="\t"))
    if any(len(row) != len(HEADERS) for row in rows):
        bad = next((index + 1 for index, row in enumerate(rows) if len(row) != len(HEADERS)), None)
        raise ValueError(f"第 {bad} 行不是 {len(HEADERS)} 列")
    return [dict(zip(HEADERS, row)) for row in rows]


def load_lookup(conn: sqlite3.Connection) -> tuple[list[dict], dict[str, dict]]:
    users = [dict(row) for row in conn.execute("SELECT id, name, feishu_user_id, department_id FROM users WHERE employment_status = 'ACTIVE'")]
    departments = {row["id"]: row["name"] for row in conn.execute("SELECT id, name FROM departments")}
    projects = {row["name"]: dict(row) for row in conn.execute("SELECT id, name, code FROM projects WHERE status != 'DELETED'")}
    for user in users:
        user["department_name"] = departments.get(user["department_id"], "")
    return users, projects


def find_user(value: str, department_name: str, users: list[dict], field: str) -> dict:
    normalized = SOURCE_USER_ALIASES.get(value.strip(), value.strip())
    candidates = [user for user in users if user["name"] == normalized]
    if department_name:
        department_matches = [user for user in candidates if user["department_name"] == department_name]
        if department_matches:
            candidates = department_matches
    # Prefer a real synced user when old demo seed data has the same display name.
    real_users = [user for user in candidates if not str(user["feishu_user_id"]).startswith("ou_demo_")]
    if real_users:
        candidates = real_users
    if len(candidates) != 1:
        ids = ", ".join(str(user["id"]) for user in candidates) or "未找到"
        raise ValueError(f"{field} 无法唯一匹配 {value!r}（候选用户 ID: {ids}）")
    return candidates[0]


def validate(rows: list[dict[str, str]], conn: sqlite3.Connection) -> list[dict]:
    users, projects = load_lookup(conn)
    prepared: list[dict] = []
    errors: list[str] = []
    for index, row in enumerate(rows, start=1):
        try:
            project_name = row["关联项目"].strip() or row["项目"].strip()
            project = projects.get(project_name)
            if not project:
                raise ValueError(f"项目不存在: {project_name!r}")
            status = STATUS_MAP.get(row["审批状态"].strip())
            if not status:
                raise ValueError(f"未知审批状态: {row['审批状态']!r}")
            work_type = WORK_TYPE_MAP.get(row["工时类型"].strip())
            if not work_type:
                raise ValueError(f"未知工时类型: {row['工时类型']!r}")
            work_status = WORK_STATUS_MAP.get(row["状态"].strip())
            if not work_status:
                raise ValueError(f"未知工作状态: {row['状态']!r}")
            submitter = find_user(row["提交人"], row["二级部门"].strip(), users, "提交人")
            approver = None
            if status != "DRAFT":
                if not row["审批人"].strip():
                    raise ValueError("非草稿记录缺少审批人")
                approver = find_user(row["审批人"], "", users, "审批人")
            quantity = float(row["工时核算"].strip())
            if quantity <= 0:
                raise ValueError(f"工时核算必须大于 0: {row['工时核算']!r}")
            start_date = parse_date(row["开始时间"], "开始时间")
            end_date = parse_date(row["结束时间"], "结束时间")
            filled_at = parse_timestamp(row["填报日期"], "填报日期")
            if start_date > end_date:
                raise ValueError("开始时间晚于结束时间")
            prepared.append({
                "row_number": index,
                "project": project,
                "project_name": project_name,
                "submitter": submitter,
                "approver": approver,
                "stage": row["项目阶段"].strip(),
                "work_type": work_type,
                "work_status": work_status,
                "start_date": start_date,
                "end_date": end_date,
                "quantity": quantity,
                "description": row["工作描述"].strip(),
                "status": status,
                "filled_at": filled_at,
                "comment": row["审核意见"].strip() or None,
            })
        except (ValueError, KeyError) as exc:
            errors.append(f"第 {index} 行: {exc}")
    if errors:
        raise ValueError("\n".join(errors))
    return prepared


def print_summary(prepared: list[dict], prefix: str = "") -> None:
    counts = {status: sum(item["status"] == status for item in prepared) for status in ("APPROVED", "PENDING_APPROVAL", "DRAFT")}
    total = sum(item["quantity"] for item in prepared)
    print(f"{prefix}输入 {len(prepared)} 条，工时 {total:g} 天；已通过 {counts['APPROVED']}，待审核 {counts['PENDING_APPROVAL']}，草稿 {counts['DRAFT']}")


def apply_import(prepared: list[dict], conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("BEGIN")
    try:
        # Clear only worklog business data; users, departments, projects and audit logs remain.
        # Worklogs reference timesheets, so remove the child rows before legacy period rows.
        for table in ("notifications", "approval_tasks", "worklogs", "timesheets"):
            conn.execute(f"DELETE FROM {table}")
        for item in prepared:
            status = item["status"]
            submitted_at = item["filled_at"] if status != "DRAFT" else None
            approved_at = item["filled_at"] if status == "APPROVED" else None
            approver = item["approver"]
            cursor = conn.execute(
                """INSERT INTO worklogs
                (user_id, user_name_snapshot, project_id, project_name_snapshot, stage,
                 work_type, work_status, start_date, end_date, quantity, unit, description,
                 status, timesheet_id, approver_user_id, approver_name_snapshot,
                 submitted_at, approved_at, rejection_reason, approval_comment,
                 approval_version, last_notified_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'DAY', ?, ?, NULL, ?, ?, ?, ?, NULL, ?, 1, NULL, ?, ?)""",
                (item["submitter"]["id"], item["submitter"]["name"], item["project"]["id"], item["project_name"],
                 item["stage"], item["work_type"], item["work_status"], item["start_date"], item["end_date"],
                 item["quantity"], item["description"], status, approver["id"] if approver else None,
                 approver["name"] if approver else None, submitted_at, approved_at, item["comment"],
                 item["filled_at"], item["filled_at"]),
            )
            worklog_id = cursor.lastrowid
            if status != "DRAFT":
                task_status = "APPROVED" if status == "APPROVED" else "PENDING"
                conn.execute(
                    """INSERT INTO approval_tasks
                    (worklog_id, version, serial_no, submitter_user_id, approver_user_id,
                     status, comment, submitted_at, processed_at, processed_by, created_at)
                    VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (worklog_id, f"WL-{item['filled_at'][:10].replace('-', '')}-{worklog_id:04d}-V1",
                     item["submitter"]["id"], approver["id"], task_status, item["comment"],
                     item["filled_at"], item["filled_at"] if task_status == "APPROVED" else None,
                     approver["id"] if task_status == "APPROVED" else None, item["filled_at"]),
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tsv", type=Path)
    parser.add_argument("database", type=Path)
    parser.add_argument("--apply", action="store_true", help="清理旧工时并写入导入数据")
    args = parser.parse_args()
    rows = read_rows(args.tsv)
    conn = sqlite3.connect(args.database)
    conn.row_factory = sqlite3.Row
    try:
        prepared = validate(rows, conn)
        print_summary(prepared, prefix="校验通过：")
        if not args.apply:
            print("试运行未写入数据库；确认后追加 --apply 执行导入。")
            return 0
        apply_import(prepared, conn)
        print_summary(prepared, prefix="导入完成：")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"导入失败: {exc}", file=sys.stderr)
        raise SystemExit(1)
