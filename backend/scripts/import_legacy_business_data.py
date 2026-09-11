"""Merge legacy customers, suppliers, projects, contracts and attachments into SQLite.

This is an explicit one-time migration utility. It never imports users, departments,
worklogs, notifications or audit data from the source database.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


PROJECT_COLUMNS = (
    "code", "name", "project_type", "owner_name", "owner_user_id", "owner_open_id",
    "approver_name", "approver_user_id", "approver_open_id", "leader_user_id",
    "leader_name", "leader_open_id", "department_id", "department_name", "customer_id",
    "customer_name", "start_date", "planned_end_date", "description", "budget_days",
    "budget_cost", "status", "allow_worklog", "source_record_id", "updated_at",
)
PARTY_COLUMNS = (
    "code", "name", "short_name", "unified_credit_code", "contact_name", "contact_phone",
    "contact_email", "address", "office_address", "license_expiry_date", "bank_name",
    "bank_branch", "bank_account", "invoice_title", "taxpayer_id", "invoice_address",
    "invoice_phone", "notes", "status", "updated_at",
)
CONTRACT_COLUMNS = (
    "contract_no", "name", "project_id", "contract_type", "counterparty_type",
    "counterparty_id", "counterparty_name", "amount", "sign_date", "start_date",
    "end_date", "status", "description", "created_at", "updated_at",
)
STAGE_COLUMNS = (
    "contract_id", "name", "amount", "planned_date", "remind_days_before",
    "reminder_paused", "sort_order", "status", "created_at", "updated_at",
)
ATTACHMENT_COLUMNS = (
    "contract_id", "file_name", "storage_name", "mime_type", "file_size", "uploaded_by",
    "created_at",
)


def rows(connection: sqlite3.Connection, table: str) -> list[dict[str, object]]:
    cursor = connection.execute(f"SELECT * FROM {table}")
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def lookup_user(target_users: list[dict[str, object]], source: dict[str, object] | None) -> dict[str, object] | None:
    if not source:
        return None
    candidates = ("open_id", "feishu_user_id", "name")
    for key in candidates:
        value = str(source.get(key) or "").strip()
        if value:
            match = next((item for item in target_users if str(item.get(key) or "").strip() == value), None)
            if match:
                return match
    return None


def lookup_department(target_departments: list[dict[str, object]], source: dict[str, object] | None) -> dict[str, object] | None:
    if not source:
        return None
    for key in ("feishu_department_id", "name"):
        value = str(source.get(key) or "").strip()
        if value:
            match = next((item for item in target_departments if str(item.get(key) or "").strip() == value), None)
            if match:
                return match
    return None


def party_upsert(connection: sqlite3.Connection, table: str, source: dict[str, object]) -> int:
    existing = connection.execute(
        f"SELECT id FROM {table} WHERE code = ? OR name = ? ORDER BY CASE WHEN code = ? THEN 0 ELSE 1 END LIMIT 1",
        (source["code"], source["name"], source["code"]),
    ).fetchone()
    values = [source.get(column) for column in PARTY_COLUMNS]
    if existing:
        assignments = ", ".join(f"{column} = ?" for column in PARTY_COLUMNS)
        connection.execute(f"UPDATE {table} SET {assignments} WHERE id = ?", (*values, existing[0]))
        return int(existing[0])
    placeholders = ", ".join("?" for _ in PARTY_COLUMNS)
    cursor = connection.execute(f"INSERT INTO {table} ({', '.join(PARTY_COLUMNS)}) VALUES ({placeholders})", values)
    return int(cursor.lastrowid)


def upsert_by_key(connection: sqlite3.Connection, table: str, columns: tuple[str, ...], key_column: str, key_value: object, source: dict[str, object]) -> int:
    existing = connection.execute(f"SELECT id FROM {table} WHERE {key_column} = ?", (key_value,)).fetchone()
    values = [source.get(column) for column in columns]
    if existing:
        assignments = ", ".join(f"{column} = ?" for column in columns)
        connection.execute(f"UPDATE {table} SET {assignments} WHERE id = ?", (*values, existing[0]))
        return int(existing[0])
    placeholders = ", ".join("?" for _ in columns)
    cursor = connection.execute(f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})", values)
    return int(cursor.lastrowid)


def attachment_path(root: Path, storage_name: str) -> Path:
    direct = root / storage_name
    if direct.is_file():
        return direct
    matches = list(root.rglob(storage_name))
    if len(matches) == 1 and matches[0].is_file():
        return matches[0]
    raise FileNotFoundError(f"legacy attachment is missing: {storage_name}")


def copy_attachment(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if source.stat().st_size == target.stat().st_size and hashlib.sha256(source.read_bytes()).digest() == hashlib.sha256(target.read_bytes()).digest():
            return
        raise ValueError(f"target attachment differs: {target.name}")
    shutil.copy2(source, target)


def remove_demo_data(connection: sqlite3.Connection) -> dict[str, int]:
    """Remove records created by the built-in demonstration seed."""
    removed = {}
    cursor = connection.execute("DELETE FROM projects WHERE code = ?", ("PRJ-2025-017",))
    removed["demo_projects"] = cursor.rowcount
    cursor = connection.execute("DELETE FROM customers WHERE code = ?", ("CUS-DEMO-001",))
    removed["demo_customers"] = cursor.rowcount
    cursor = connection.execute("DELETE FROM users WHERE feishu_user_id LIKE ?", ("ou_demo_%",))
    removed["demo_users"] = cursor.rowcount
    cursor = connection.execute("DELETE FROM departments WHERE feishu_department_id LIKE ?", ("dept-demo-%",))
    removed["demo_departments"] = cursor.rowcount
    return removed


def import_data(source_path: Path, target_path: Path, attachments_dir: Path, target_attachments_dir: Path, backup_path: Path, projects_only: bool = False, remove_demo: bool = False) -> dict[str, object]:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists():
        shutil.copy2(target_path, backup_path)
    source = sqlite3.connect(f"file:{source_path.resolve()}?mode=ro", uri=True)
    target = sqlite3.connect(target_path)
    source.row_factory = sqlite3.Row
    target.row_factory = sqlite3.Row
    target.execute("PRAGMA foreign_keys = ON")
    counts = {"customers": 0, "suppliers": 0, "projects": 0, "contracts": 0, "contract_stages": 0, "contract_attachments": 0}
    project_map: dict[int, int] = {}
    contract_map: dict[int, int] = {}
    customer_map: dict[int, int] = {}
    supplier_map: dict[int, int] = {}
    try:
        target.execute("BEGIN")
        target_users = rows(target, "users")
        target_departments = rows(target, "departments")
        source_users = {int(item["id"]): item for item in rows(source, "users")}
        source_departments = {int(item["id"]): item for item in rows(source, "departments")}

        if not projects_only:
            for source_party in rows(source, "customers"):
                customer_map[int(source_party["id"])] = party_upsert(target, "customers", source_party)
                counts["customers"] += 1
            for source_party in rows(source, "suppliers"):
                supplier_map[int(source_party["id"])] = party_upsert(target, "suppliers", source_party)
                counts["suppliers"] += 1

        for source_project in rows(source, "projects"):
            if source_project.get("status") == "DELETED":
                continue
            owner = lookup_user(target_users, source_users.get(int(source_project["owner_user_id"])))
            approver = lookup_user(target_users, source_users.get(int(source_project["approver_user_id"])))
            leader = lookup_user(target_users, source_users.get(int(source_project["leader_user_id"])))
            department = lookup_department(target_departments, source_departments.get(int(source_project["department_id"])))
            customer_id = customer_map.get(int(source_project["customer_id"])) if source_project.get("customer_id") else None
            customer = target.execute("SELECT name FROM customers WHERE id = ?", (customer_id,)).fetchone() if customer_id else None
            project = dict(source_project)
            project.update(
                owner_user_id=owner["id"] if owner else None,
                owner_open_id=owner["open_id"] if owner else source_project.get("owner_open_id"),
                approver_user_id=approver["id"] if approver else None,
                approver_open_id=approver["open_id"] if approver else source_project.get("approver_open_id"),
                leader_user_id=leader["id"] if leader else None,
                leader_open_id=leader["open_id"] if leader else source_project.get("leader_open_id"),
                department_id=department["id"] if department else None,
                department_name=department["name"] if department else source_project.get("department_name"),
                customer_id=None if projects_only else customer_id,
                customer_name=source_project.get("customer_name") if projects_only else (customer["name"] if customer else source_project.get("customer_name")),
            )
            project_map[int(source_project["id"])] = upsert_by_key(target, "projects", PROJECT_COLUMNS, "code", project["code"], project)
            counts["projects"] += 1

        if projects_only:
            removed = remove_demo_data(target) if remove_demo else {}
            foreign_keys = target.execute("PRAGMA foreign_key_check").fetchall()
            if foreign_keys:
                raise ValueError(f"foreign key check failed: {foreign_keys[:3]}")
            target.commit()
            return {"counts": counts, "removed": removed, "backup": str(backup_path) if backup_path.exists() else None, "projects_only": True}

        source_contracts = {int(item["id"]): item for item in rows(source, "contracts")}
        for source_contract in source_contracts.values():
            project_id = project_map.get(int(source_contract["project_id"]))
            if not project_id:
                raise ValueError(f"contract {source_contract['contract_no']} references a project that was not imported")
            party_map = customer_map if source_contract["counterparty_type"] == "CUSTOMER" else supplier_map
            party_id = party_map.get(int(source_contract["counterparty_id"]))
            if not party_id:
                raise ValueError(f"contract {source_contract['contract_no']} references a missing counterparty")
            party_table = "customers" if source_contract["counterparty_type"] == "CUSTOMER" else "suppliers"
            party = target.execute(f"SELECT name FROM {party_table} WHERE id = ?", (party_id,)).fetchone()
            contract = dict(source_contract)
            contract.update(project_id=project_id, counterparty_id=party_id, counterparty_name=party["name"])
            contract_map[int(source_contract["id"])] = upsert_by_key(target, "contracts", CONTRACT_COLUMNS, "contract_no", contract["contract_no"], contract)
            counts["contracts"] += 1

        for source_stage in rows(source, "contract_stages"):
            contract_id = contract_map.get(int(source_stage["contract_id"]))
            if not contract_id:
                raise ValueError(f"stage {source_stage['id']} references a missing contract")
            stage = dict(source_stage)
            stage["contract_id"] = contract_id
            existing = target.execute(
                "SELECT id FROM contract_stages WHERE contract_id = ? AND name = ? AND sort_order = ? LIMIT 1",
                (contract_id, stage["name"], stage["sort_order"]),
            ).fetchone()
            values = [stage.get(column) for column in STAGE_COLUMNS]
            if existing:
                assignments = ", ".join(f"{column} = ?" for column in STAGE_COLUMNS)
                target.execute(f"UPDATE contract_stages SET {assignments} WHERE id = ?", (*values, existing[0]))
            else:
                placeholders = ", ".join("?" for _ in STAGE_COLUMNS)
                target.execute(f"INSERT INTO contract_stages ({', '.join(STAGE_COLUMNS)}) VALUES ({placeholders})", values)
            counts["contract_stages"] += 1

        fallback_user = next((item for item in target_users if item.get("employment_status") == "ACTIVE"), None)
        for source_attachment in rows(source, "contract_attachments"):
            contract_id = contract_map.get(int(source_attachment["contract_id"]))
            if not contract_id:
                raise ValueError(f"attachment {source_attachment['file_name']} references a missing contract")
            uploader = lookup_user(target_users, source_users.get(int(source_attachment["uploaded_by"]))) or fallback_user
            if not uploader:
                raise ValueError("no active target user is available for contract attachment ownership")
            source_file = attachment_path(attachments_dir, str(source_attachment["storage_name"]))
            if source_file.stat().st_size != int(source_attachment["file_size"]):
                raise ValueError(f"attachment size mismatch: {source_attachment['file_name']}")
            target_file = target_attachments_dir / str(source_attachment["storage_name"])
            copy_attachment(source_file, target_file)
            attachment = dict(source_attachment)
            attachment.update(contract_id=contract_id, uploaded_by=uploader["id"])
            upsert_by_key(target, "contract_attachments", ATTACHMENT_COLUMNS, "storage_name", attachment["storage_name"], attachment)
            counts["contract_attachments"] += 1

        foreign_keys = target.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_keys:
            raise ValueError(f"foreign key check failed: {foreign_keys[:3]}")
        target.commit()
        return {"counts": counts, "backup": str(backup_path) if backup_path.exists() else None}
    except Exception:
        target.rollback()
        raise
    finally:
        source.close()
        target.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge legacy business data into the current system database")
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--attachments", required=True, type=Path)
    parser.add_argument("--target-attachments", required=True, type=Path)
    parser.add_argument("--projects-only", action="store_true")
    parser.add_argument("--remove-demo-data", action="store_true")
    parser.add_argument("--backup", type=Path, default=None)
    args = parser.parse_args()
    backup = args.backup or args.target.with_name(f"workhours-before-legacy-import-{datetime.now():%Y%m%d-%H%M%S}.db")
    result = import_data(args.source, args.target, args.attachments, args.target_attachments, backup, projects_only=args.projects_only, remove_demo=args.remove_demo_data)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
