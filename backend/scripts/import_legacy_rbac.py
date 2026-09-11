"""Replace current RBAC configuration with mappings from a legacy SQLite database."""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


def rows(connection: sqlite3.Connection, query: str, parameters: tuple[object, ...] = ()) -> list[dict[str, object]]:
    cursor = connection.execute(query, parameters)
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def lookup_target(
    source: dict[str, object],
    target_rows: list[dict[str, object]],
    keys: tuple[str, ...],
) -> dict[str, object] | None:
    for key in keys:
        value = str(source.get(key) or "").strip()
        if not value:
            continue
        match = next((item for item in target_rows if str(item.get(key) or "").strip() == value), None)
        if match:
            return match
    return None


def import_rbac(source_path: Path, target_path: Path, backup_path: Path) -> dict[str, object]:
    if target_path.exists():
        shutil.copy2(target_path, backup_path)
    source = sqlite3.connect(f"file:{source_path.resolve()}?mode=ro", uri=True)
    target = sqlite3.connect(target_path)
    source.row_factory = sqlite3.Row
    target.row_factory = sqlite3.Row
    target.execute("PRAGMA foreign_keys = ON")
    try:
        source_users = {int(item["id"]): item for item in rows(source, "SELECT * FROM users")}
        source_departments = {int(item["id"]): item for item in rows(source, "SELECT * FROM departments")}
        target_users = rows(target, "SELECT * FROM users")
        target_departments = rows(target, "SELECT * FROM departments")
        target_menus = {str(item["code"]): item for item in rows(target, "SELECT * FROM menus")}
        source_roles = rows(source, "SELECT * FROM roles ORDER BY id")
        source_role_by_id = {int(item["id"]): item for item in source_roles}
        source_menus = {int(item["id"]): item for item in rows(source, "SELECT * FROM menus")}

        missing_users: list[str] = []
        user_map: dict[int, int] = {}
        for source_user_id in {
            int(item["user_id"])
            for table in ("user_roles", "user_role_scopes")
            for item in rows(source, f"SELECT user_id FROM {table}")
        }:
            source_user = source_users[source_user_id]
            match = lookup_target(source_user, target_users, ("open_id", "feishu_user_id", "name"))
            if not match:
                missing_users.append(str(source_user.get("name") or source_user_id))
            else:
                user_map[source_user_id] = int(match["id"])
        if missing_users:
            raise ValueError("target users are missing: " + ", ".join(sorted(missing_users)))

        department_map: dict[int, int] = {}
        referenced_department_ids = {
            int(item["department_id"])
            for table in ("role_data_scopes", "user_role_scopes")
            for item in rows(source, f"SELECT department_id FROM {table} WHERE department_id IS NOT NULL")
        }
        for source_department_id in referenced_department_ids:
            source_department = source_departments[source_department_id]
            match = lookup_target(source_department, target_departments, ("feishu_department_id", "name"))
            if not match:
                raise ValueError(f"target department is missing: {source_department.get('name') or source_department_id}")
            department_map[source_department_id] = int(match["id"])

        missing_menus = sorted(
            {
                str(source_menus[int(item["menu_id"])]["code"])
                for item in rows(source, "SELECT menu_id FROM role_permissions")
                if str(source_menus[int(item["menu_id"])]["code"]) not in target_menus
            }
        )
        if missing_menus:
            raise ValueError("target menus are missing: " + ", ".join(missing_menus))

        target.execute("BEGIN")
        target.execute("DELETE FROM user_role_scopes")
        target.execute("DELETE FROM user_roles")
        target.execute("DELETE FROM role_data_scopes")
        target.execute("DELETE FROM role_permissions")
        target.execute("DELETE FROM roles WHERE code <> ?", ("system_admin",))

        role_map: dict[int, int] = {}
        for source_role in source_roles:
            existing = target.execute("SELECT id FROM roles WHERE code = ?", (source_role["code"],)).fetchone()
            if existing:
                role_id = int(existing[0])
                target.execute(
                    "UPDATE roles SET name = ?, description = ?, is_active = ?, updated_at = ? WHERE id = ?",
                    (source_role["name"], source_role.get("description"), source_role["is_active"], source_role.get("updated_at"), role_id),
                )
            else:
                cursor = target.execute(
                    "INSERT INTO roles (code, name, description, is_builtin, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        source_role["code"], source_role["name"], source_role.get("description"),
                        source_role["is_builtin"], source_role["is_active"],
                        source_role.get("created_at"), source_role.get("updated_at"),
                    ),
                )
                role_id = int(cursor.lastrowid)
            role_map[int(source_role["id"])] = role_id

        for item in rows(source, "SELECT * FROM role_permissions ORDER BY id"):
            menu_code = str(source_menus[int(item["menu_id"])]["code"])
            target.execute(
                "INSERT INTO role_permissions (role_id, menu_id, actions) VALUES (?, ?, ?)",
                (role_map[int(item["role_id"])], int(target_menus[menu_code]["id"]), item["actions"]),
            )

        for item in rows(source, "SELECT * FROM role_data_scopes ORDER BY id"):
            source_department_id = int(item["department_id"]) if item.get("department_id") is not None else None
            target.execute(
                "INSERT INTO role_data_scopes (role_id, resource, scope_type, department_id) VALUES (?, ?, ?, ?)",
                (
                    role_map[int(item["role_id"])], item["resource"], item["scope_type"],
                    department_map.get(source_department_id) if source_department_id is not None else None,
                ),
            )

        for item in rows(source, "SELECT * FROM user_roles ORDER BY id"):
            target.execute(
                "INSERT INTO user_roles (user_id, role_id, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (
                    user_map[int(item["user_id"])], role_map[int(item["role_id"])], item["is_active"],
                    item.get("created_at"), item.get("updated_at"),
                ),
            )

        for item in rows(source, "SELECT * FROM user_role_scopes ORDER BY id"):
            source_department_id = int(item["department_id"]) if item.get("department_id") is not None else None
            target.execute(
                "INSERT INTO user_role_scopes (user_id, role_id, resource, scope_type, department_id) VALUES (?, ?, ?, ?, ?)",
                (
                    user_map[int(item["user_id"])], role_map[int(item["role_id"])], item["resource"], item["scope_type"],
                    department_map.get(source_department_id) if source_department_id is not None else None,
                ),
            )

        foreign_keys = target.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_keys:
            raise ValueError(f"foreign key check failed: {foreign_keys[:3]}")
        target.commit()
        return {
            "roles": len(source_roles),
            "role_permissions": len(rows(source, "SELECT id FROM role_permissions")),
            "role_data_scopes": len(rows(source, "SELECT id FROM role_data_scopes")),
            "user_roles": len(rows(source, "SELECT id FROM user_roles")),
            "user_role_scopes": len(rows(source, "SELECT id FROM user_role_scopes")),
            "mapped_users": len(user_map),
            "mapped_departments": len(department_map),
            "foreign_key_errors": 0,
            "backup": str(backup_path) if backup_path.exists() else None,
        }
    except Exception:
        target.rollback()
        raise
    finally:
        source.close()
        target.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Replace RBAC configuration from a legacy database")
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--backup", type=Path, default=None)
    args = parser.parse_args()
    backup = args.backup or args.target.with_name(f"workhours-before-rbac-import-{datetime.now():%Y%m%d-%H%M%S}.db")
    print(json.dumps(import_rbac(args.source, args.target, backup), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
