"""客户、供应商和合同导入接口回归测试。"""

import os
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path


class ImportApiTests(unittest.TestCase):
    """使用临时数据库验证导入不会影响现有业务库。"""

    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[2]
        cls.temp_dir = tempfile.TemporaryDirectory(prefix="xinye-import-test-")
        cls.db_path = Path(cls.temp_dir.name) / "workhours.db"
        shutil.copyfile(cls.root / "backend" / "data" / "workhours.db", cls.db_path)
        os.environ["DATABASE_URL"] = f"sqlite:///{cls.db_path}"
        os.environ["FEISHU_MODE"] = "mock"
        os.environ["SYSTEM_ADMIN_USER_IDS"] = "1"
        from fastapi.testclient import TestClient
        from backend.app.main import app

        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()
        cls.headers = {"X-Demo-User-Id": "1"}

    @classmethod
    def tearDownClass(cls):
        cls.client_context.__exit__(None, None, None)
        from backend.app.db.session import engine

        engine.dispose()
        cls.temp_dir.cleanup()

    def test_customer_supplier_contract_csv_and_duplicate_validation(self):
        project_response = self.client.get("/api/v1/projects", headers=self.headers)
        self.assertEqual(project_response.status_code, 200, project_response.text)
        project = project_response.json()[0]
        suffix = uuid.uuid4().hex[:8]
        customer_name = f"导入测试客户-{suffix}"
        supplier_name = f"导入测试供应商-{suffix}"
        contract_code = f"TEST-CT-{suffix}"
        customer_csv = f"客户名称,付款银行,付款账号\n{customer_name},测试银行,62220001\n".encode("utf-8-sig")
        supplier_csv = f"供应商名称\n{supplier_name}\n".encode("utf-8-sig")

        preview = self.client.post("/api/v1/imports/customers/preview", headers=self.headers, files={"file": ("customers.csv", customer_csv, "text/csv")})
        self.assertEqual(preview.status_code, 200, preview.text)
        self.assertEqual(preview.json()["valid_rows"], 1)
        imported = self.client.post("/api/v1/imports/customers", headers=self.headers, files={"file": ("customers.csv", customer_csv, "text/csv")})
        self.assertEqual(imported.status_code, 200, imported.text)
        self.assertEqual(imported.json()["imported"], 1)
        imported_customer = next(item for item in self.client.get("/api/v1/customers?active_only=true", headers=self.headers).json() if item["name"] == customer_name)
        self.assertTrue(imported_customer["code"].startswith("CUS-"), imported_customer["code"])

        duplicate = self.client.post("/api/v1/imports/customers/preview", headers=self.headers, files={"file": ("customers.csv", customer_csv, "text/csv")})
        self.assertEqual(duplicate.status_code, 200, duplicate.text)
        self.assertTrue(any(item["field"] == "客户名称" for item in duplicate.json()["errors"]))

        imported = self.client.post("/api/v1/imports/suppliers", headers=self.headers, files={"file": ("suppliers.csv", supplier_csv, "text/csv")})
        self.assertEqual(imported.status_code, 200, imported.text)
        self.assertEqual(imported.json()["imported"], 1)
        imported_supplier = next(item for item in self.client.get("/api/v1/suppliers?active_only=true", headers=self.headers).json() if item["name"] == supplier_name)
        self.assertTrue(imported_supplier["code"].startswith("SUP-"), imported_supplier["code"])

        contract_csv = f"合同编号*,合同名称*,项目名称*,合同类型*,往来单位名称*,合同金额*\n{contract_code},导入测试合同-{suffix},{project['name']},收入合同,{customer_name},1000\n".encode("utf-8-sig")
        preview = self.client.post("/api/v1/imports/contracts/preview", headers=self.headers, files={"file": ("contracts.csv", contract_csv, "text/csv")})
        self.assertEqual(preview.status_code, 200, preview.text)
        self.assertEqual(preview.json()["valid_rows"], 1)
        imported = self.client.post("/api/v1/imports/contracts", headers=self.headers, files={"file": ("contracts.csv", contract_csv, "text/csv")})
        self.assertEqual(imported.status_code, 200, imported.text)
        self.assertEqual(imported.json()["imported"], 1)
        contracts = self.client.get(f"/api/v1/contracts?keyword={contract_code}", headers=self.headers)
        self.assertEqual(contracts.status_code, 200, contracts.text)
        self.assertEqual(contracts.json()[0]["counterparty_name"], customer_name)
        self.assertEqual(contracts.json()[0]["counterparty_id"], imported_customer["id"])

        mismatch_csv = f"合同编号*,合同名称*,项目名称*,合同类型*,往来单位名称*,合同金额*\nTEST-CT-BAD-{suffix},错误合同-{suffix},{project['name']},收入合同,{supplier_name},1000\n".encode("utf-8-sig")
        preview = self.client.post("/api/v1/imports/contracts/preview", headers=self.headers, files={"file": ("bad.csv", mismatch_csv, "text/csv")})
        self.assertEqual(preview.status_code, 200, preview.text)
        self.assertTrue(any(item["field"] == "往来单位名称" for item in preview.json()["errors"]))
        rejected = self.client.post("/api/v1/imports/contracts", headers=self.headers, files={"file": ("bad.csv", mismatch_csv, "text/csv")})
        self.assertEqual(rejected.status_code, 422, rejected.text)
        self.assertEqual(self.client.get(f"/api/v1/contracts?keyword=错误合同-{suffix}", headers=self.headers).json(), [])

        unmatched_project_csv = f"合同编号*,合同名称*,项目名称*,合同类型*,往来单位名称*,合同金额*\nTEST-CT-NO-PROJECT-{suffix},项目匹配失败-{suffix},不存在的项目,支出合同,{supplier_name},1000\n".encode("utf-8-sig")
        preview = self.client.post("/api/v1/imports/contracts/preview", headers=self.headers, files={"file": ("unmatched-project.csv", unmatched_project_csv, "text/csv")})
        self.assertEqual(preview.status_code, 200, preview.text)
        self.assertTrue(any(item["field"] == "项目名称" for item in preview.json()["errors"]))

    def test_counterparty_xlsx_templates_are_readable_without_code_column(self):
        for resource, filename in (("customers", "customer-import-template.xlsx"), ("suppliers", "supplier-import-template.xlsx")):
            template = self.root / "frontend" / "public" / "templates" / filename
            response = self.client.post(
                f"/api/v1/imports/{resource}/preview",
                headers=self.headers,
                files={"file": (template.name, template.read_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["resource"], resource)
            self.assertFalse(
                any("缺少此列" in str(item["message"]) for item in response.json()["errors"]),
                response.json()["errors"],
            )

    def test_counterparty_code_auto_generated_and_preserved_on_update(self):
        suffix = uuid.uuid4().hex[:8]
        customer_name = f"自动编码客户-{suffix}"
        created = self.client.post(
            "/api/v1/customers",
            headers=self.headers,
            json={"name": customer_name},
        )
        self.assertEqual(created.status_code, 201, created.text)
        customer = created.json()
        self.assertTrue(customer["code"].startswith("CUS-"), customer["code"])

        updated = self.client.patch(
            f"/api/v1/customers/{customer['id']}",
            headers=self.headers,
            json={"name": f"{customer_name}-改名", "status": "ACTIVE"},
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["code"], customer["code"])
        self.assertEqual(updated.json()["name"], f"{customer_name}-改名")

        supplier_name = f"自动编码供应商-{suffix}"
        created = self.client.post(
            "/api/v1/suppliers",
            headers=self.headers,
            json={"name": supplier_name},
        )
        self.assertEqual(created.status_code, 201, created.text)
        self.assertTrue(created.json()["code"].startswith("SUP-"), created.json()["code"])


if __name__ == "__main__":
    unittest.main()
