"""飞书组织与消息能力适配器。

v2.0 不调用飞书审批 API。审批状态由本地服务维护，适配器只负责发送提醒，
并保留 mock/webhook/app 三种配置边界，避免把外部凭证写进业务逻辑。
"""

from dataclasses import dataclass
import json
import os
from urllib import parse, request
from urllib.error import HTTPError

from ..time_utils import now_local


@dataclass
class NotificationResult:
    status: str
    message_id: str | None = None
    error_message: str | None = None


@dataclass
class DirectoryUser:
    """飞书通讯录用户的最小同步快照。"""

    feishu_user_id: str
    open_id: str | None
    name: str
    email: str | None
    department_id: str | None
    department_name: str | None
    is_active: bool
    leader_user_id: str | None = None
    leader_name: str | None = None


@dataclass
class DirectoryDepartment:
    """飞书通讯录部门的最小同步快照。"""

    feishu_department_id: str
    name: str
    parent_department_id: str | None
    parent_name: str | None
    is_active: bool


class FeishuAdapter:
    """封装飞书消息发送和健康检查。"""

    def __init__(self) -> None:
        self.mode = os.getenv("FEISHU_MODE", "mock")
        self.notification_mode = os.getenv("FEISHU_NOTIFICATION_MODE", "mock")
        self.webhook = os.getenv("FEISHU_ROBOT_WEBHOOK", "")
        self.app_id = os.getenv("FEISHU_APP_ID", "")
        self.app_secret = os.getenv("FEISHU_APP_SECRET", "")
        self.api_base = os.getenv("FEISHU_API_BASE", "https://open.feishu.cn")

    def _selected_notification_mode(self, channel: str | None) -> str:
        """返回单次通知策略指定的通道；未指定时沿用部署环境默认通道。"""
        return channel or self.notification_mode

    def _json_request(self, method: str, url: str, payload: dict | None = None, headers: dict[str, str] | None = None) -> dict:
        """调用飞书 JSON API，并将网络或业务错误转换为可识别异常。"""
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req_headers = {"Content-Type": "application/json", **(headers or {})}
        req = request.Request(url, data=data, headers=req_headers, method=method)
        try:
            with request.urlopen(req, timeout=12) as response:
                result = json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # pragma: no cover - depends on external network
            raise RuntimeError(f"FEISHU_DIRECTORY_SYNC_FAILED:{str(exc)[:300]}") from exc
        if result.get("code", 0) != 0:
            raise RuntimeError(f"FEISHU_DIRECTORY_SYNC_FAILED:{result.get('msg', 'unknown error')}")
        return result

    def _tenant_access_token(self) -> str:
        """获取通讯录接口所需的租户访问令牌。"""
        if not self.app_id or not self.app_secret:
            raise RuntimeError("FEISHU_DIRECTORY_NOT_CONFIGURED")
        result = self._json_request(
            "POST",
            f"{self.api_base}/open-apis/auth/v3/tenant_access_token/internal",
            {"app_id": self.app_id, "app_secret": self.app_secret},
        )
        token = result.get("tenant_access_token")
        if not token:
            raise RuntimeError("FEISHU_DIRECTORY_SYNC_FAILED:tenant token missing")
        return token

    def _message_json_request(self, method: str, url: str, payload: dict, token: str) -> dict:
        """调用飞书消息 API，并将网络或业务错误转换为通知错误。"""
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
            method=method,
        )
        try:
            with request.urlopen(req, timeout=8) as response:
                result = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:  # pragma: no cover - depends on external network
            try:
                error_body = json.loads(exc.read().decode("utf-8"))
            except Exception:
                error_body = {}
            api_code = error_body.get("code")
            api_message = error_body.get("msg") or error_body.get("message")
            detail = f"HTTP_{exc.code}"
            if api_code is not None or api_message:
                detail = f"{detail}:{api_code or 'UNKNOWN'} {api_message or 'unknown error'}"
            raise RuntimeError(f"FEISHU_APP_MESSAGE_SEND_FAILED:{detail[:300]}") from exc
        except Exception as exc:  # pragma: no cover - depends on external network
            raise RuntimeError(f"FEISHU_APP_MESSAGE_SEND_FAILED:{str(exc)[:300]}") from exc
        if result.get("code", 0) != 0:
            raise RuntimeError(f"FEISHU_APP_MESSAGE_SEND_FAILED:{result.get('msg', 'unknown error')}")
        return result

    def _app_access_token(self) -> str:
        """获取 OAuth 授权码换取用户令牌所需的应用令牌。"""
        if not self.app_id or not self.app_secret:
            raise RuntimeError("FEISHU_OAUTH_NOT_CONFIGURED")
        result = self._auth_request(
            "POST",
            f"{self.api_base}/open-apis/auth/v3/app_access_token/internal",
            {"app_id": self.app_id, "app_secret": self.app_secret},
        )
        token = result.get("app_access_token")
        if not token:
            raise RuntimeError("FEISHU_OAUTH_FAILED:app access token missing")
        return token

    def _auth_request(self, method: str, url: str, payload: dict | None = None, headers: dict[str, str] | None = None) -> dict:
        """调用 OAuth API，保留飞书错误消息用于登录失败提示。"""
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = request.Request(url, data=data, headers={"Content-Type": "application/json", **(headers or {})}, method=method)
        try:
            with request.urlopen(req, timeout=12) as response:
                result = json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # pragma: no cover - depends on external network
            raise RuntimeError(f"FEISHU_OAUTH_FAILED:{str(exc)[:300]}") from exc
        if result.get("code", 0) != 0:
            raise RuntimeError(f"FEISHU_OAUTH_FAILED:{result.get('msg', 'unknown error')}")
        return result

    def exchange_oauth_code(self, code: str) -> dict:
        """使用 OAuth 授权码读取当前飞书用户信息。"""
        app_token = self._app_access_token()
        token_result = self._auth_request(
            "POST",
            f"{self.api_base}/open-apis/authen/v1/oidc/access_token",
            {"grant_type": "authorization_code", "code": code},
            {"Authorization": f"Bearer {app_token}"},
        )
        user_token = (token_result.get("data") or {}).get("access_token") or token_result.get("access_token")
        if not user_token:
            raise RuntimeError("FEISHU_OAUTH_FAILED:user access token missing")
        user_result = self._auth_request(
            "GET",
            f"{self.api_base}/open-apis/authen/v1/user_info",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        return user_result.get("data") or user_result

    def _list_pages(self, path: str, token: str, params: dict[str, str]) -> list[dict]:
        """读取飞书分页资源，兼容无分页令牌的响应。"""
        items: list[dict] = []
        page_token = ""
        while True:
            query = {**params}
            if page_token:
                query["page_token"] = page_token
            url = f"{self.api_base}{path}?{parse.urlencode(query)}"
            result = self._json_request("GET", url, headers={"Authorization": f"Bearer {token}"})
            data = result.get("data") or {}
            items.extend(data.get("items") or [])
            if not data.get("has_more"):
                return items
            next_token = data.get("page_token")
            if not next_token or next_token == page_token:
                return items
            page_token = next_token

    def fetch_directory(self) -> tuple[list[DirectoryDepartment], list[DirectoryUser]]:
        """递归读取飞书部门树，并按部门读取用户后去重。"""
        if self.mode != "app":
            raise RuntimeError("FEISHU_DIRECTORY_NOT_CONFIGURED")
        token = self._tenant_access_token()
        department_rows: list[dict] = []
        pending_department_ids = ["0"]
        seen_department_ids: set[str] = set()
        while pending_department_ids:
            parent_id = pending_department_ids.pop(0)
            if parent_id in seen_department_ids:
                continue
            seen_department_ids.add(parent_id)
            children = self._list_pages(
                f"/open-apis/contact/v3/departments/{parent_id}/children",
                token,
                {"page_size": "50", "department_id_type": "department_id"},
            )
            department_rows.extend(children)
            pending_department_ids.extend(str(row["department_id"]) for row in children if row.get("department_id"))
        departments: list[DirectoryDepartment] = []
        department_names: dict[str, str] = {}
        department_ids: list[str] = []
        for row in department_rows:
            department_id = row.get("department_id") or row.get("open_department_id")
            if not department_id or not row.get("name"):
                continue
            department_id = str(department_id)
            if department_id in department_names:
                continue
            parent_id = row.get("parent_department_id")
            parent_id = str(parent_id) if parent_id else None
            is_active = row.get("status", {}).get("is_deleted", False) is False if isinstance(row.get("status"), dict) else not bool(row.get("is_deleted", False))
            department_names[department_id] = str(row["name"])
            department_ids.append(department_id)
            departments.append(DirectoryDepartment(department_id, str(row["name"]), parent_id, None, bool(is_active)))
        for department in departments:
            department.parent_name = department_names.get(department.parent_department_id) if department.parent_department_id else None
        users_by_id: dict[str, DirectoryUser] = {}
        for current_department_id in department_ids:
            user_rows = self._list_pages(
                "/open-apis/contact/v3/users",
                token,
                {"page_size": "50", "department_id": current_department_id, "department_id_type": "department_id", "user_id_type": "open_id"},
            )
            for row in user_rows:
                user_id = row.get("user_id") or row.get("open_id")
                if not user_id or not row.get("name"):
                    continue
                row_department_ids = row.get("department_ids") or []
                department_id = str(row_department_ids[0]) if row_department_ids else current_department_id
                status = row.get("status")
                is_active = status.get("is_active", True) if isinstance(status, dict) else row.get("is_active", True)
                leader_user_id = row.get("leader_user_id") or row.get("leader_user") or row.get("manager_user_id")
                if isinstance(leader_user_id, dict):
                    leader_user_id = leader_user_id.get("user_id") or leader_user_id.get("open_id")
                users_by_id[str(user_id)] = DirectoryUser(
                    feishu_user_id=str(user_id),
                    open_id=row.get("open_id"),
                    name=str(row["name"]),
                    email=row.get("email"),
                    department_id=department_id,
                    department_name=department_names.get(department_id),
                    is_active=bool(is_active),
                    leader_user_id=str(leader_user_id) if leader_user_id else None,
                    leader_name=str(row.get("leader_name") or row.get("manager_name") or "") or None,
                )
        return departments, list(users_by_id.values())

    def fetch_directory_users(self) -> tuple[list[DirectoryUser], int]:
        """兼容旧调用方，仅返回用户和部门数量。"""
        departments, users = self.fetch_directory()
        return users, len(departments)

    @staticmethod
    def _feishu_webview_url(system_url: str) -> str:
        """将系统地址包装为飞书 AppLink，使客户端在内置 WebView 中打开。"""
        return "https://applink.feishu.cn/client/web_url/open?" + parse.urlencode({"mode": "window", "url": system_url})

    def notify_approval_submitted(
        self,
        serial_no: str,
        recipient_name: str,
        submitter_name: str,
        project_name: str,
        description: str,
        start_date: str,
        quantity: float,
        unit: str,
        system_url: str,
        recipient_open_id: str | None = None,
        channel: str | None = None,
    ) -> NotificationResult:
        """发送一条待审批提醒；返回发送状态，不改变本地审批事务。"""
        notification_mode = self._selected_notification_mode(channel)
        summary = (
            f"综合项目管理系统有新的待审批工时\n"
            f"单号：{serial_no}\n审批人：{recipient_name}\n提交人：{submitter_name}\n"
            f"项目：{project_name}\n日期：{start_date}\n工时：{quantity:g} {unit}\n"
            f"工作内容：{description}"
        )
        content = f"{summary}\n处理地址：{system_url}"
        if notification_mode == "mock":
            return NotificationResult(status="SENT", message_id=f"MOCK-MSG-{now_local():%Y%m%d%H%M%S}")
        if notification_mode == "webhook" and self.webhook:
            payload = json.dumps({"msg_type": "text", "content": {"text": content}}).encode("utf-8")
            try:
                req = request.Request(self.webhook, data=payload, headers={"Content-Type": "application/json"}, method="POST")
                with request.urlopen(req, timeout=8) as response:
                    if response.status >= 300:
                        return NotificationResult(status="FAILED", error_message=f"HTTP_{response.status}")
                return NotificationResult(status="SENT", message_id=f"WEBHOOK-{now_local():%Y%m%d%H%M%S}")
            except Exception as exc:  # pragma: no cover - depends on external network
                return NotificationResult(status="FAILED", error_message=str(exc)[:500])
        if notification_mode == "app":
            if not self.app_id or not self.app_secret:
                return NotificationResult(status="FAILED", error_message="FEISHU_APP_MESSAGE_NOT_CONFIGURED")
            if not recipient_open_id or not recipient_open_id.strip():
                return NotificationResult(status="FAILED", error_message="FEISHU_APP_RECIPIENT_OPEN_ID_MISSING")
            try:
                token = self._tenant_access_token()
            except Exception as exc:
                return NotificationResult(status="FAILED", error_message=f"FEISHU_APP_MESSAGE_TOKEN_FAILED:{str(exc)[:300]}")
            try:
                webview_url = self._feishu_webview_url(system_url)
                card = {
                    "config": {"wide_screen_mode": True},
                    "header": {
                        "template": "blue",
                        "title": {"tag": "plain_text", "content": "综合项目管理系统 · 待审批"},
                    },
                    "elements": [
                        {"tag": "div", "text": {"tag": "plain_text", "content": summary}},
                        {
                            "tag": "action",
                            "actions": [
                                {
                                    "tag": "button",
                                    "text": {"tag": "plain_text", "content": "打开综合项目管理系统"},
                                    "type": "primary",
                                    "behaviors": [{"type": "open_url", "default_url": webview_url}],
                                }
                            ],
                        },
                    ],
                }
                result = self._message_json_request(
                    "POST",
                    f"{self.api_base}/open-apis/im/v1/messages?{parse.urlencode({'receive_id_type': 'open_id'})}",
                    {
                        "receive_id": recipient_open_id.strip(),
                        "msg_type": "interactive",
                        "content": json.dumps(card, ensure_ascii=False),
                    },
                    token,
                )
            except Exception as exc:
                detail = str(exc)[:500]
                if "230013" in detail:
                    detail = "FEISHU_APP_MESSAGE_SEND_FAILED:230013 Bot has NO availability to this user; 请在飞书应用后台将该审批人加入应用可用范围"
                return NotificationResult(status="FAILED", error_message=detail)
            message_id = (result.get("data") or {}).get("message_id")
            if not message_id:
                return NotificationResult(status="FAILED", error_message="FEISHU_APP_MESSAGE_SEND_FAILED:message_id missing")
            return NotificationResult(status="SENT", message_id=str(message_id))
        return NotificationResult(status="FAILED", error_message="FEISHU_ROBOT_WEBHOOK_NOT_CONFIGURED")

    def notify_cash_approval_submitted(
        self,
        recipient_name: str,
        submitter_name: str,
        document_type: str,
        serial_no: str,
        project_name: str,
        amount: float,
        system_url: str,
        recipient_open_id: str | None = None,
        channel: str | None = None,
    ) -> NotificationResult:
        """发送收付款待出纳审批提醒；每个有权限的出纳单独接收。"""
        notification_mode = self._selected_notification_mode(channel)
        summary = (
            f"综合项目管理系统有新的待审批{document_type}\n"
            f"单号：{serial_no}\n审批人：{recipient_name}\n提交人：{submitter_name}\n"
            f"项目：{project_name}\n金额：{amount:,.2f} 元"
        )
        content = f"{summary}\n处理地址：{system_url}"
        if notification_mode == "mock":
            return NotificationResult(status="SENT", message_id=f"MOCK-CASH-APPROVAL-{now_local():%Y%m%d%H%M%S}")
        if notification_mode == "webhook" and self.webhook:
            payload = json.dumps({"msg_type": "text", "content": {"text": content}}).encode("utf-8")
            try:
                req = request.Request(self.webhook, data=payload, headers={"Content-Type": "application/json"}, method="POST")
                with request.urlopen(req, timeout=8) as response:
                    if response.status >= 300:
                        return NotificationResult(status="FAILED", error_message=f"HTTP_{response.status}")
                return NotificationResult(status="SENT", message_id=f"WEBHOOK-CASH-APPROVAL-{now_local():%Y%m%d%H%M%S}")
            except Exception as exc:  # pragma: no cover - depends on external network
                return NotificationResult(status="FAILED", error_message=str(exc)[:500])
        if notification_mode == "app":
            if not self.app_id or not self.app_secret:
                return NotificationResult(status="FAILED", error_message="FEISHU_APP_MESSAGE_NOT_CONFIGURED")
            if not recipient_open_id or not recipient_open_id.strip():
                return NotificationResult(status="FAILED", error_message="FEISHU_APP_RECIPIENT_OPEN_ID_MISSING")
            try:
                token = self._tenant_access_token()
                webview_url = self._feishu_webview_url(system_url)
                card = {
                    "config": {"wide_screen_mode": True},
                    "header": {
                        "template": "blue",
                        "title": {"tag": "plain_text", "content": f"综合项目管理系统 · 待审批{document_type}"},
                    },
                    "elements": [
                        {"tag": "div", "text": {"tag": "plain_text", "content": summary}},
                        {
                            "tag": "action",
                            "actions": [
                                {
                                    "tag": "button",
                                    "text": {"tag": "plain_text", "content": "打开综合项目管理系统"},
                                    "type": "primary",
                                    "behaviors": [{"type": "open_url", "default_url": webview_url}],
                                }
                            ],
                        },
                    ],
                }
                result = self._message_json_request(
                    "POST",
                    f"{self.api_base}/open-apis/im/v1/messages?{parse.urlencode({'receive_id_type': 'open_id'})}",
                    {
                        "receive_id": recipient_open_id.strip(),
                        "msg_type": "interactive",
                        "content": json.dumps(card, ensure_ascii=False),
                    },
                    token,
                )
            except Exception as exc:
                detail = str(exc)[:500]
                if "230013" in detail:
                    detail = "FEISHU_APP_MESSAGE_SEND_FAILED:230013 Bot has NO availability to this user; 请在飞书应用后台将该审批人加入应用可用范围"
                return NotificationResult(status="FAILED", error_message=detail)
            message_id = (result.get("data") or {}).get("message_id")
            if not message_id:
                return NotificationResult(status="FAILED", error_message="FEISHU_APP_MESSAGE_SEND_FAILED:message_id missing")
            return NotificationResult(status="SENT", message_id=str(message_id))
        return NotificationResult(status="FAILED", error_message="FEISHU_ROBOT_WEBHOOK_NOT_CONFIGURED")

    def notify_reminder(
        self,
        recipient_name: str,
        project_name: str,
        contract_name: str,
        stage_name: str,
        planned_date: str,
        amount: float,
        remaining: float,
        reminder_type: str,
        system_url: str,
        recipient_open_id: str | None = None,
        channel: str | None = None,
    ) -> NotificationResult:
        """发送合同阶段到期或逾期提醒。"""
        notification_mode = self._selected_notification_mode(channel)
        type_label = {"UPCOMING": "即将到期", "DUE": "已到期", "OVERDUE": "已逾期"}.get(reminder_type, "提醒")
        summary = (
            f"综合项目管理系统 · 合同阶段{type_label}\n"
            f"项目：{project_name}\n合同：{contract_name}\n阶段：{stage_name}\n"
            f"计划日期：{planned_date}\n计划金额：{amount:,.2f} 元\n剩余金额：{remaining:,.2f} 元\n"
            f"负责人：{recipient_name}"
        )
        content = f"{summary}\n处理地址：{system_url}"
        if notification_mode == "mock":
            return NotificationResult(status="SENT", message_id=f"MOCK-REMINDER-{now_local():%Y%m%d%H%M%S}")
        if notification_mode == "webhook" and self.webhook:
            payload = json.dumps({"msg_type": "text", "content": {"text": content}}).encode("utf-8")
            try:
                req = request.Request(self.webhook, data=payload, headers={"Content-Type": "application/json"}, method="POST")
                with request.urlopen(req, timeout=8) as response:
                    if response.status >= 300:
                        return NotificationResult(status="FAILED", error_message=f"HTTP_{response.status}")
                return NotificationResult(status="SENT", message_id=f"WEBHOOK-{now_local():%Y%m%d%H%M%S}")
            except Exception as exc:  # pragma: no cover - depends on external network
                return NotificationResult(status="FAILED", error_message=str(exc)[:500])
        if notification_mode == "app":
            if not self.app_id or not self.app_secret:
                return NotificationResult(status="FAILED", error_message="FEISHU_APP_MESSAGE_NOT_CONFIGURED")
            if not recipient_open_id or not recipient_open_id.strip():
                return NotificationResult(status="FAILED", error_message="FEISHU_APP_RECIPIENT_OPEN_ID_MISSING")
            try:
                token = self._tenant_access_token()
            except Exception as exc:
                return NotificationResult(status="FAILED", error_message=f"FEISHU_APP_MESSAGE_TOKEN_FAILED:{str(exc)[:300]}")
            try:
                webview_url = self._feishu_webview_url(system_url)
                template = "orange" if reminder_type == "OVERDUE" else "blue"
                card = {
                    "config": {"wide_screen_mode": True},
                    "header": {
                        "template": template,
                        "title": {"tag": "plain_text", "content": f"综合项目管理系统 · 合同阶段{type_label}"},
                    },
                    "elements": [
                        {"tag": "div", "text": {"tag": "plain_text", "content": summary}},
                        {
                            "tag": "action",
                            "actions": [
                                {
                                    "tag": "button",
                                    "text": {"tag": "plain_text", "content": "打开综合项目管理系统"},
                                    "type": "primary",
                                    "behaviors": [{"type": "open_url", "default_url": webview_url}],
                                }
                            ],
                        },
                    ],
                }
                result = self._message_json_request(
                    "POST",
                    f"{self.api_base}/open-apis/im/v1/messages?{parse.urlencode({'receive_id_type': 'open_id'})}",
                    {
                        "receive_id": recipient_open_id.strip(),
                        "msg_type": "interactive",
                        "content": json.dumps(card, ensure_ascii=False),
                    },
                    token,
                )
            except Exception as exc:
                return NotificationResult(status="FAILED", error_message=str(exc)[:500])
            message_id = (result.get("data") or {}).get("message_id")
            if not message_id:
                return NotificationResult(status="FAILED", error_message="FEISHU_APP_MESSAGE_SEND_FAILED:message_id missing")
            return NotificationResult(status="SENT", message_id=str(message_id))
        return NotificationResult(status="FAILED", error_message="FEISHU_ROBOT_WEBHOOK_NOT_CONFIGURED")

    def notify_project_warning(
        self,
        recipient_name: str,
        project_name: str,
        title: str,
        detail: str,
        system_url: str,
        recipient_open_id: str | None = None,
        channel: str | None = None,
    ) -> NotificationResult:
        """发送项目预算或待审批业务预警。"""
        notification_mode = self._selected_notification_mode(channel)
        summary = (
            f"综合项目管理系统 · {title}\n"
            f"项目：{project_name}\n{detail}\n负责人：{recipient_name}"
        )
        content = f"{summary}\n处理地址：{system_url}"
        if notification_mode == "mock":
            return NotificationResult(status="SENT", message_id=f"MOCK-PROJECT-WARNING-{now_local():%Y%m%d%H%M%S}")
        if notification_mode == "webhook" and self.webhook:
            payload = json.dumps({"msg_type": "text", "content": {"text": content}}).encode("utf-8")
            try:
                req = request.Request(self.webhook, data=payload, headers={"Content-Type": "application/json"}, method="POST")
                with request.urlopen(req, timeout=8) as response:
                    if response.status >= 300:
                        return NotificationResult(status="FAILED", error_message=f"HTTP_{response.status}")
                return NotificationResult(status="SENT", message_id=f"WEBHOOK-PROJECT-WARNING-{now_local():%Y%m%d%H%M%S}")
            except Exception as exc:  # pragma: no cover - depends on external network
                return NotificationResult(status="FAILED", error_message=str(exc)[:500])
        if notification_mode == "app":
            if not self.app_id or not self.app_secret:
                return NotificationResult(status="FAILED", error_message="FEISHU_APP_MESSAGE_NOT_CONFIGURED")
            if not recipient_open_id or not recipient_open_id.strip():
                return NotificationResult(status="FAILED", error_message="FEISHU_APP_RECIPIENT_OPEN_ID_MISSING")
            try:
                token = self._tenant_access_token()
                webview_url = self._feishu_webview_url(system_url)
                card = {
                    "config": {"wide_screen_mode": True},
                    "header": {
                        "template": "orange",
                        "title": {"tag": "plain_text", "content": f"综合项目管理系统 · {title}"},
                    },
                    "elements": [
                        {"tag": "div", "text": {"tag": "plain_text", "content": summary}},
                        {
                            "tag": "action",
                            "actions": [
                                {
                                    "tag": "button",
                                    "text": {"tag": "plain_text", "content": "打开综合项目管理系统"},
                                    "type": "primary",
                                    "behaviors": [{"type": "open_url", "default_url": webview_url}],
                                }
                            ],
                        },
                    ],
                }
                result = self._message_json_request(
                    "POST",
                    f"{self.api_base}/open-apis/im/v1/messages?{parse.urlencode({'receive_id_type': 'open_id'})}",
                    {
                        "receive_id": recipient_open_id.strip(),
                        "msg_type": "interactive",
                        "content": json.dumps(card, ensure_ascii=False),
                    },
                    token,
                )
            except Exception as exc:
                return NotificationResult(status="FAILED", error_message=str(exc)[:500])
            message_id = (result.get("data") or {}).get("message_id")
            if not message_id:
                return NotificationResult(status="FAILED", error_message="FEISHU_APP_MESSAGE_SEND_FAILED:message_id missing")
            return NotificationResult(status="SENT", message_id=str(message_id))
        return NotificationResult(status="FAILED", error_message="FEISHU_ROBOT_WEBHOOK_NOT_CONFIGURED")

    def notify_worklog_fill_reminder(
        self,
        recipient_name: str,
        work_date: str,
        system_url: str,
        recipient_open_id: str | None = None,
        channel: str | None = None,
    ) -> NotificationResult:
        """提醒成员及时填报当天工时；只做提醒，不判断填报结果。"""
        notification_mode = self._selected_notification_mode(channel)
        summary = (
            "综合项目管理系统 · 工时填报提醒\n"
            f"成员：{recipient_name}\n日期：{work_date}\n"
            "提醒：你当天还没有填报工时，请及时提交。"
        )
        content = f"{summary}\n填报地址：{system_url}"
        if notification_mode == "mock":
            return NotificationResult(status="SENT", message_id=f"MOCK-WORKLOG-FILL-{now_local():%Y%m%d%H%M%S}")
        if notification_mode == "webhook" and self.webhook:
            payload = json.dumps({"msg_type": "text", "content": {"text": content}}).encode("utf-8")
            try:
                req = request.Request(self.webhook, data=payload, headers={"Content-Type": "application/json"}, method="POST")
                with request.urlopen(req, timeout=8) as response:
                    if response.status >= 300:
                        return NotificationResult(status="FAILED", error_message=f"HTTP_{response.status}")
                return NotificationResult(status="SENT", message_id=f"WEBHOOK-WORKLOG-FILL-{now_local():%Y%m%d%H%M%S}")
            except Exception as exc:  # pragma: no cover - depends on external network
                return NotificationResult(status="FAILED", error_message=str(exc)[:500])
        if notification_mode == "app":
            if not self.app_id or not self.app_secret:
                return NotificationResult(status="FAILED", error_message="FEISHU_APP_MESSAGE_NOT_CONFIGURED")
            if not recipient_open_id or not recipient_open_id.strip():
                return NotificationResult(status="FAILED", error_message="FEISHU_APP_RECIPIENT_OPEN_ID_MISSING")
            try:
                token = self._tenant_access_token()
                webview_url = self._feishu_webview_url(system_url)
                card = {
                    "config": {"wide_screen_mode": True},
                    "header": {
                        "template": "blue",
                        "title": {"tag": "plain_text", "content": "综合项目管理系统 · 工时填报提醒"},
                    },
                    "elements": [
                        {"tag": "div", "text": {"tag": "plain_text", "content": summary}},
                        {
                            "tag": "action",
                            "actions": [
                                {
                                    "tag": "button",
                                    "text": {"tag": "plain_text", "content": "去填报工时"},
                                    "type": "primary",
                                    "behaviors": [{"type": "open_url", "default_url": webview_url}],
                                }
                            ],
                        },
                    ],
                }
                result = self._message_json_request(
                    "POST",
                    f"{self.api_base}/open-apis/im/v1/messages?{parse.urlencode({'receive_id_type': 'open_id'})}",
                    {
                        "receive_id": recipient_open_id.strip(),
                        "msg_type": "interactive",
                        "content": json.dumps(card, ensure_ascii=False),
                    },
                    token,
                )
            except Exception as exc:
                return NotificationResult(status="FAILED", error_message=str(exc)[:500])
            message_id = (result.get("data") or {}).get("message_id")
            if not message_id:
                return NotificationResult(status="FAILED", error_message="FEISHU_APP_MESSAGE_SEND_FAILED:message_id missing")
            return NotificationResult(status="SENT", message_id=str(message_id))
        return NotificationResult(status="FAILED", error_message="FEISHU_ROBOT_WEBHOOK_NOT_CONFIGURED")

    def notify_worklog_fill_reminder_t1(
        self,
        recipient_name: str,
        work_date: str,
        system_url: str,
        recipient_open_id: str | None = None,
        channel: str | None = None,
    ) -> NotificationResult:
        """提醒成员补填上一个工作日漏填的工时；只做提醒，不判断填报结果。"""
        notification_mode = self._selected_notification_mode(channel)
        summary = (
            "综合项目管理系统 · 工时补填提醒\n"
            f"成员：{recipient_name}\n日期：{work_date}\n"
            "提醒：你这一天还没有填报工时，请在今天补填提交。"
        )
        content = f"{summary}\n填报地址：{system_url}"
        if notification_mode == "mock":
            return NotificationResult(status="SENT", message_id=f"MOCK-WORKLOG-FILL-T1-{now_local():%Y%m%d%H%M%S}")
        if notification_mode == "webhook" and self.webhook:
            payload = json.dumps({"msg_type": "text", "content": {"text": content}}).encode("utf-8")
            try:
                req = request.Request(self.webhook, data=payload, headers={"Content-Type": "application/json"}, method="POST")
                with request.urlopen(req, timeout=8) as response:
                    if response.status >= 300:
                        return NotificationResult(status="FAILED", error_message=f"HTTP_{response.status}")
                return NotificationResult(status="SENT", message_id=f"WEBHOOK-WORKLOG-FILL-T1-{now_local():%Y%m%d%H%M%S}")
            except Exception as exc:  # pragma: no cover - depends on external network
                return NotificationResult(status="FAILED", error_message=str(exc)[:500])
        if notification_mode == "app":
            if not self.app_id or not self.app_secret:
                return NotificationResult(status="FAILED", error_message="FEISHU_APP_MESSAGE_NOT_CONFIGURED")
            if not recipient_open_id or not recipient_open_id.strip():
                return NotificationResult(status="FAILED", error_message="FEISHU_APP_RECIPIENT_OPEN_ID_MISSING")
            try:
                token = self._tenant_access_token()
                webview_url = self._feishu_webview_url(system_url)
                card = {
                    "config": {"wide_screen_mode": True},
                    "header": {
                        "template": "orange",
                        "title": {"tag": "plain_text", "content": "综合项目管理系统 · 工时补填提醒"},
                    },
                    "elements": [
                        {"tag": "div", "text": {"tag": "plain_text", "content": summary}},
                        {
                            "tag": "action",
                            "actions": [
                                {
                                    "tag": "button",
                                    "text": {"tag": "plain_text", "content": "去补填工时"},
                                    "type": "primary",
                                    "behaviors": [{"type": "open_url", "default_url": webview_url}],
                                }
                            ],
                        },
                    ],
                }
                result = self._message_json_request(
                    "POST",
                    f"{self.api_base}/open-apis/im/v1/messages?{parse.urlencode({'receive_id_type': 'open_id'})}",
                    {
                        "receive_id": recipient_open_id.strip(),
                        "msg_type": "interactive",
                        "content": json.dumps(card, ensure_ascii=False),
                    },
                    token,
                )
            except Exception as exc:
                return NotificationResult(status="FAILED", error_message=str(exc)[:500])
            message_id = (result.get("data") or {}).get("message_id")
            if not message_id:
                return NotificationResult(status="FAILED", error_message="FEISHU_APP_MESSAGE_SEND_FAILED:message_id missing")
            return NotificationResult(status="SENT", message_id=str(message_id))
        return NotificationResult(status="FAILED", error_message="FEISHU_ROBOT_WEBHOOK_NOT_CONFIGURED")

    def notify_settlement_result(
        self,
        recipient_name: str,
        document_type: str,
        serial_no: str,
        project_name: str,
        amount: float,
        status: str,
        system_url: str,
        recipient_open_id: str | None = None,
        channel: str | None = None,
        approver_name: str | None = None,
    ) -> NotificationResult:
        """通知申请人：合同收款或合同付款单已审批通过。"""
        notification_mode = self._selected_notification_mode(channel)
        summary = (
            f"综合项目管理系统 · {document_type}审批通过\n"
            f"单号：{serial_no}\n项目：{project_name}\n金额：{amount:,.2f} 元\n"
            f"处理结果：{status}\n审批人：{approver_name or '出纳'}\n申请人：{recipient_name}"
        )
        content = f"{summary}\n查看地址：{system_url}"
        if notification_mode == "mock":
            return NotificationResult(status="SENT", message_id=f"MOCK-SETTLEMENT-{now_local():%Y%m%d%H%M%S}")
        if notification_mode == "webhook" and self.webhook:
            payload = json.dumps({"msg_type": "text", "content": {"text": content}}).encode("utf-8")
            try:
                req = request.Request(self.webhook, data=payload, headers={"Content-Type": "application/json"}, method="POST")
                with request.urlopen(req, timeout=8) as response:
                    if response.status >= 300:
                        return NotificationResult(status="FAILED", error_message=f"HTTP_{response.status}")
                return NotificationResult(status="SENT", message_id=f"WEBHOOK-{now_local():%Y%m%d%H%M%S}")
            except Exception as exc:  # pragma: no cover - depends on external network
                return NotificationResult(status="FAILED", error_message=str(exc)[:500])
        if notification_mode == "app":
            if not self.app_id or not self.app_secret:
                return NotificationResult(status="FAILED", error_message="FEISHU_APP_MESSAGE_NOT_CONFIGURED")
            if not recipient_open_id or not recipient_open_id.strip():
                return NotificationResult(status="FAILED", error_message="FEISHU_APP_RECIPIENT_OPEN_ID_MISSING")
            try:
                token = self._tenant_access_token()
            except Exception as exc:
                return NotificationResult(status="FAILED", error_message=f"FEISHU_APP_MESSAGE_TOKEN_FAILED:{str(exc)[:300]}")
            try:
                webview_url = self._feishu_webview_url(system_url)
                card = {
                    "config": {"wide_screen_mode": True},
                    "header": {
                        "template": "green",
                        "title": {"tag": "plain_text", "content": f"综合项目管理系统 · {document_type}审批通过"},
                    },
                    "elements": [
                        {"tag": "div", "text": {"tag": "plain_text", "content": summary}},
                        {
                            "tag": "action",
                            "actions": [
                                {
                                    "tag": "button",
                                    "text": {"tag": "plain_text", "content": "打开综合项目管理系统"},
                                    "type": "primary",
                                    "behaviors": [{"type": "open_url", "default_url": webview_url}],
                                }
                            ],
                        },
                    ],
                }
                result = self._message_json_request(
                    "POST",
                    f"{self.api_base}/open-apis/im/v1/messages?{parse.urlencode({'receive_id_type': 'open_id'})}",
                    {
                        "receive_id": recipient_open_id.strip(),
                        "msg_type": "interactive",
                        "content": json.dumps(card, ensure_ascii=False),
                    },
                    token,
                )
            except Exception as exc:
                return NotificationResult(status="FAILED", error_message=str(exc)[:500])
            message_id = (result.get("data") or {}).get("message_id")
            if not message_id:
                return NotificationResult(status="FAILED", error_message="FEISHU_APP_MESSAGE_SEND_FAILED:message_id missing")
            return NotificationResult(status="SENT", message_id=str(message_id))
        return NotificationResult(status="FAILED", error_message="FEISHU_ROBOT_WEBHOOK_NOT_CONFIGURED")

    def health(self) -> dict[str, str]:
        """返回组织适配器和通知通道的配置健康状态。"""
        notification = self.notification_mode
        if notification == "webhook" and not self.webhook:
            notification = "webhook-not-configured"
        if notification == "app" and (not self.app_id or not self.app_secret):
            notification = "app-not-configured"
        directory = "mock-ok" if self.mode == "mock" else ("app-configured" if self.app_id and self.app_secret else "app-not-configured")
        return {
            "mode": self.mode,
            "oauth": "mock-ok" if self.mode == "mock" else directory,
            "directory": directory,
            "approval": "local-only",
            "notification": notification,
        }
