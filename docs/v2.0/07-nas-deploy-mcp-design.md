# NAS 部署 MCP 设计说明

- 版本：v2.0.1
- 日期：2026-08-26
- 状态：已实现，测试通过
- 变更：新增独立 NAS 部署运维 MCP，不修改工时系统业务功能

## 1. 目标

在开发机上运行一个基于 stdio 的 MCP Server，通过 SSH 连接 NAS，封装芯烨工时管理系统的常用部署运维动作。MCP 只管理固定项目目录 `/volume1/docker/xinye-workhours`，不提供任意远程 Shell。

## 2. 工具范围

| 工具 | 作用 | 是否变更远端 |
| --- | --- | --- |
| `nas_health` | 检查 NAS SSH、HTTP 健康接口和产品版本 | 否 |
| `nas_status` | 查看 Compose 服务状态 | 否 |
| `nas_logs` | 查看 backend/frontend 最近日志 | 否 |
| `nas_backup` | 创建部署目录备份，不包含 Docker 数据卷 | 是 |
| `nas_deploy` | 本地构建、打包、上传、备份、校验 Compose、重建容器、健康检查 | 是，需确认 |
| `nas_rollback` | 从指定备份恢复部署文件并重建容器 | 是，需确认 |

## 3. 安全边界

1. NAS 主机、SSH 端口、用户名、密码或私钥路径全部从 MCP 启动环境读取，禁止写入源码、示例配置和日志。
2. 默认只允许目标目录 `/volume1/docker/xinye-workhours`，远端命令由服务端固定模板生成。
3. 发布和回滚必须传入 `confirm=true`，否则只返回预览信息。
4. 备份名称使用时间戳生成并限制为安全字符；回滚只允许选择目标目录下的 `.backup-*` 目录。
5. 上传先进入远端临时目录，Compose 校验和文件替换成功后才重建服务；失败时保留现有版本和备份。
6. 日志结果截断为有限长度，避免把环境变量或大段数据返回给 MCP 客户端。

## 4. 发布流程

```text
检查本地目录 -> pnpm build -> 准备 dist/backend/deploy
    -> 上传到 NAS 临时目录 -> 远端创建备份
    -> 替换部署文件 -> docker compose config -q
    -> docker compose up -d --build --force-recreate backend frontend
    -> HTTP /health 验证 -> 返回发布结果
```

当前数据库 Docker volume 不参与文件替换和备份恢复，避免误覆盖业务数据。

## 5. 配置

MCP 使用 `.env.example` 说明配置，实际配置放在 MCP 启动器或客户端配置的 `env` 中：

```dotenv
NAS_HOST=192.168.112.188
NAS_SSH_PORT=10000
NAS_USERNAME=
NAS_PASSWORD=
NAS_PRIVATE_KEY=
NAS_DEPLOY_DIR=/volume1/docker/xinye-workhours
NAS_HTTP_URL=http://192.168.112.188:8088
PROJECT_ROOT=D:\\myproject
```

优先使用 SSH 私钥；密码仅作为兼容选项。MCP 的 stdio 输出只写 JSON-RPC，诊断信息写 stderr。

## 6. 交付与验证

交付目录包含 MCP Server、启动脚本、配置示例、客户端配置片段和使用说明。验证包括：静态编译、工具清单握手、参数校验、预览模式、远端只读状态/健康检查，以及本地构建流程的失败保护。真实发布仍需显式调用 `confirm=true`。

已完成验证：

- MCP `initialize` 握手成功，协议版本为 `2025-06-18`。
- `tools/list` 正常返回 6 个工具。
- Python 编译、依赖一致性检查、3 项单元测试全部通过。
- `nas_deploy(confirm=false)` 只返回发布计划，不执行构建、上传或重建。
- 回滚目录名路径穿越校验通过。
- 真实 NAS 发布未在本次 MCP 验证中触发，避免在未配置本机凭据时产生远端变更。
