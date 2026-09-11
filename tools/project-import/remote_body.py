"""容器内执行体：把项目台账导入生产库。

由 tools/project-import/import_projects.py 注入 ROWS_JSON 后经 base64 送入容器。
默认 dry-run；加 --apply 才写库。

走与 POST /api/v1/admin/projects 完全相同的业务函数：
    resolve_project_classification -> active_org_department -> Project(...)
    -> apply_project_users -> ensure_project_budget_items -> audit
"""
import json
import sqlite3
import sys

APPLY = "--apply" in sys.argv
DB_PATH = "/app/data/workhours.db"

ROWS_JSON = r"""__ROWS_JSON__"""
ROWS = [tuple(row) for row in json.loads(ROWS_JSON)]

# 台账中文标签 -> 系统内部编码
MAJOR_MAP = {"经营项目": "BUSINESS_PROJECT", "研发项目": "RND_PROJECT"}
SUB_MAP = {
    "委托研发": "ENTRUSTED_RND",
    "设备销售": "EQUIPMENT_SALES",
    "技术服务": "TECHNICAL_SERVICE",
    "机器人施工": "ROBOT_CONSTRUCTION",
    "设备租赁": "EQUIPMENT_RENTAL",
    "外部申报项目": "EXTERNAL_DECLARATION",
    "外部申报": "EXTERNAL_DECLARATION",
    "自主研发": "SELF_DEVELOPED_RND",
}
STATUS_MAP = {"进行中": "ACTIVE", "验收中": "ACCEPTANCE", "已暂停": "PAUSED", "已完成": "COMPLETED"}

con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)

users = {name: uid for uid, name in con.execute("SELECT id, name FROM users")}
depts = {name: did for did, name in con.execute("SELECT id, name FROM departments WHERE is_active = 1")}
dept_names = {did: name for did, name in con.execute("SELECT id, name FROM departments")}
status_values = {v for (v,) in con.execute("SELECT value FROM config_options WHERE category = 'project_status'")}
major_ids = {v: cid for cid, v in con.execute("SELECT id, value FROM config_options WHERE category = 'project_category'")}
sub_info = {
    v: (cid, parent)
    for cid, v, _label, parent in con.execute(
        "SELECT id, value, label, parent_id FROM config_options "
        "WHERE category = 'project_sub_category' AND is_active = 1"
    )
}

print(f"模式: {'APPLY（会写库）' if APPLY else 'DRY-RUN（只校验）'}")
print(f"源数据 {len(ROWS)} 行\n")

errors: list[str] = []
plan: list[dict] = []

for index, row in enumerate(ROWS, start=1):
    major_label, sub_label, name, code, owner, approver, leader, dept, status = row
    item: dict = {"index": index, "code": code, "name": name}

    major = MAJOR_MAP.get(major_label)
    if not major:
        errors.append(f"[{index}] 未知项目大类 {major_label!r}")
        continue

    sub = SUB_MAP.get(sub_label) if sub_label else None
    if sub_label and not sub:
        errors.append(f"[{index}] 未知项目小类 {sub_label!r}")
        continue
    if sub and sub not in sub_info:
        errors.append(f"[{index}] 系统内无此小类 {sub}")
        continue
    if sub and sub_info[sub][1] != major_ids.get(major):
        errors.append(f"[{index}] 小类 {sub}({sub_label}) 不属于大类 {major}({major_label})")
        continue
    item["major"] = major
    item["sub"] = sub

    if con.execute("SELECT COUNT(*) FROM projects WHERE code = ?", (code,)).fetchone()[0]:
        errors.append(f"[{index}] 项目编号已存在: {code}")
        continue

    dept_id = depts.get(dept) if dept else None
    if dept and dept_id is None:
        errors.append(f"[{index}] 部门未启用或不存在: {dept}")
        continue
    item["dept_id"] = dept_id
    item["dept_name"] = dept_names.get(dept_id)

    people: dict = {}
    for key, who in (("owner", owner), ("approver", approver), ("leader", leader)):
        if not who:
            people[key] = None
            continue
        uid = users.get(who)
        if uid is None:
            errors.append(f"[{index}] 用户不存在: {who}")
            people[key] = "ERROR"
        else:
            people[key] = uid
    if any(v == "ERROR" for v in people.values()):
        continue
    item.update(people)

    status_value = STATUS_MAP.get(status) if status else "ACTIVE"
    if status_value not in status_values:
        errors.append(f"[{index}] 项目状态非法: {status_value}")
        continue
    item["status"] = status_value

    plan.append(item)

print("=== 导入计划 ===")
for item in plan:
    print(
        f"  [{item['index']:>2}] {item['code']:<16} {item['major']:<17} {str(item['sub']):<20}"
        f" 负责人={item['owner'] or '-':<5} 审批={item['approver'] or '-':<5} 领导={item['leader'] or '-':<5}"
        f" 部门={item['dept_name']}({item['dept_id']}) 状态={item['status']}"
    )
    print(f"        {item['name']}")

if errors:
    print("\n=== 校验失败 ===")
    for e in errors:
        print("  ", e)
    print(f"\n共 {len(errors)} 项错误，未写入任何数据。")
    sys.exit(1)

print(f"\n校验通过 {len(plan)} 条。")

if not APPLY:
    print("DRY-RUN 结束，未写库。加 --apply 执行导入。")
    sys.exit(0)

# ---------------------------------------------------------------- 正式写入
sys.path.insert(0, "/app")
from sqlalchemy import func, select  # noqa: E402

from app.db.models import Project, ProjectBudgetItem  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.main import (  # noqa: E402
    active_org_department,
    apply_project_users,
    audit,
    ensure_project_budget_items,
    resolve_project_classification,
    system_admin_user_ids,
)

db = SessionLocal()
try:
    admins = sorted(system_admin_user_ids(db))
    actor = admins[0] if admins else None
    print(f"\n审计操作人 id={actor}")

    created = []
    for item in plan:
        major, sub = resolve_project_classification(db, item["major"], item["sub"])
        department = active_org_department(db, item["dept_id"]) if item["dept_id"] else None

        project = Project(
            code=item["code"],
            name=item["name"],
            project_type=major,
            project_sub_category=sub,
            owner_name="",
            department_id=department.id if department else None,
            department_name=department.name if department else None,
            budget_days=0,
            budget_cost=0,
            expense_budget=0,
            status=item["status"],
            allow_worklog=True,
        )
        if item["owner"] and item["approver"] and item["leader"]:
            apply_project_users(project, db, item["owner"], item["approver"], item["leader"])
        db.add(project)
        db.flush()
        ensure_project_budget_items(db, project)
        audit(db, "project", project.id, "CREATE", actor, None, project.status, "台账导入")
        db.flush()
        created.append(project)

    db.commit()
    print(f"\n已提交 {len(created)} 个项目。")
    for p in created:
        budget_count = db.scalar(
            select(func.count(ProjectBudgetItem.id)).where(ProjectBudgetItem.project_id == p.id)
        )
        print(
            f"  id={p.id:<3} {p.code:<16} {p.project_type:<17} {str(p.project_sub_category):<20}"
            f" 负责人={p.owner_name or '-':<6} 审批={p.approver_name or '-':<6} 领导={p.leader_name or '-':<6}"
            f" 部门={p.department_name} 状态={p.status} 预算项={budget_count}"
        )
finally:
    db.close()

print("\n导入完成。")
