# 综合项目管理系统 v3.0.33：LibreOffice 运行时镜像复用

- 版本：v3.0.33
- 日期：2026-09-05
- 状态：已确认，进入实现

## 1. 需求

LibreOffice、中文字体等系统依赖只在 NAS 首次构建运行时基础镜像时安装；后续应用发布仅重建 Python 依赖和业务代码层，避免重复下载安装 LibreOffice。

## 2. 方案

- 新增固定标签的后端运行时基础镜像，集中安装 Python、LibreOffice Writer/Calc/Impress 和中文字体。
- 应用镜像通过 `FROM` 复用该基础镜像，不在应用 Dockerfile 中重复执行 `apt-get install`。
- NAS MCP 发布时先检查运行时镜像是否存在；不存在时只构建一次，存在时直接复用。
- 运行时镜像使用日期固定标签，不使用 `latest`，避免基础镜像标签变化导致依赖层意外失效。
- 保留 Docker 的常规构建缓存；修改 `requirements.txt` 时只重新安装 Python 包，修改业务代码时只复制新的应用代码。
- 不把系统依赖安装到业务数据卷；数据库和附件数据卷继续保持不变。

## 3. 受影响模块

- `deploy/Dockerfile.runtime`：新增运行时依赖镜像定义。
- `deploy/Dockerfile.backend`：改为基于运行时镜像构建应用层。
- `deploy/docker-compose.yml`：声明运行时镜像标签和应用构建参数。
- `tools/nas-deploy-mcp/nas_deploy_mcp/core.py`：发布前按需构建运行时镜像，并将文件纳入备份/恢复。
- NAS 发布说明和变更记录。

## 4. 验收标准

1. 首次发布且运行时镜像不存在时，NAS MCP 能先完成运行时镜像构建，再启动应用。
2. 后续发布运行时镜像已存在时，构建日志不再执行 LibreOffice 安装步骤。
3. 后端容器内 `soffice --version` 可用，旧版 Office 附件预览不受影响。
4. 后续修改后端代码仍会更新应用镜像，不会误用旧代码。
5. `/health` 返回 200，前端、后端容器均正常运行。
6. 发布失败时能恢复部署文件，业务数据卷不被删除或替换。

## 5. 变更记录

| 日期 | 变更 | 影响 |
| --- | --- | --- |
| 2026-09-05 | 将 LibreOffice 系统依赖从应用构建层拆出为可复用运行时镜像 | Docker 构建与 NAS MCP 发布效率，不改变业务功能 |
| 2026-09-05 | 修复发布包遗漏 `backend/requirements.txt` 导致后端镜像构建失败的问题 | NAS MCP 发布与回滚 |
| 2026-09-05 | 兼容 Docker 28 与旧版 docker-compose 重建容器时的 `ContainerConfig` 错误 | NAS MCP 发布与容器重建 |
| 2026-09-05 | 清理旧版 Compose 生成的带前缀应用容器残留，避免重建时再次读取失效容器配置 | NAS MCP 发布与容器重建 |

## 6. 发布记录

- 发布目标：`116.169.217.29:22`
- 部署目录：`/opt/xinye-project-management`
- 运行时镜像：`xinye-project-management_runtime:20260905`
- 后端容器内 LibreOffice：`25.2.3`
- 前后端容器：均为运行状态
- 数据卷：`deploy_xinye-workhours-data`，未删除或替换
- 数据库项目记录：19 条，可正常读取
- 健康检查：`http://116.169.217.29:8088/health` 返回 HTTP 200
