# 综合项目管理系统 NAS 部署 MCP

这是一个运行在开发机上的 stdio MCP Server，通过 SSH 管理 NAS 上的综合项目管理系统。

## 安装

在本目录执行：

~~~powershell
.\install.ps1 -Python "C:\path\to\python.exe"
Copy-Item .env.example .env
~~~

填写 .env 中的 NAS 连接信息。优先使用 NAS_PRIVATE_KEY；如果使用密码，密码只保存在本机 .env，不会写入源码。

启动：

~~~powershell
.\run.ps1
~~~

## MCP 客户端配置

以支持 stdio MCP 的客户端为例，使用绝对路径：

~~~json
{
  "mcpServers": {
    "xinye-nas-deploy": {
      "command": "C:\\path\\to\\tools\\nas-deploy-mcp\\.venv\\Scripts\\python.exe",
      "args": ["-m", "nas_deploy_mcp.server"],
      "cwd": "C:\\path\\to\\tools\\nas-deploy-mcp"
    }
  }
}
~~~

也可以将 .env 中的变量放到客户端配置的 env 字段；不要把密码提交到配置仓库。

## 工具

- nas_health：检查 SSH 和 HTTP 健康状态。
- nas_status：查看 backend/frontend Docker Compose 状态。
- nas_logs(service, tail)：查看最近日志，service 为 backend、frontend 或 all。
- nas_backup：创建部署文件备份，Docker 数据卷不受影响。
- nas_deploy(confirm)：不确认时只返回发布预览；confirm=true 才会构建和发布。
- nas_rollback(backup_name, confirm)：不确认时只预览；confirm=true 才会回滚。

发布会先构建前端、上传到临时目录、创建远端备份、校验 Compose，再检查固定标签的后端运行时镜像。运行时镜像不存在时才构建一次，其中包含 LibreOffice 和中文字体；已存在时直接复用。随后重建两个应用容器并访问 /health。失败时恢复上一版部署文件；数据库 Docker volume 不参与替换。

应用构建和 LibreOffice 运行时构建已经分离：修改业务代码时只会重建应用镜像层，修改 `requirements.txt` 时只会重新安装 Python 包。只有升级 Python、LibreOffice 或字体时，才需要修改 `NAS_RUNTIME_IMAGE` 标签并重新构建运行时镜像。
