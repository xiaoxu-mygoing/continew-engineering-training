# ContiNew Admin 工程实训

三人小组的 Windows 开发仓库。后端在 `continew-admin`，前端在 `continew-admin-ui`。当前可演示指定账号和免输账号刷脸登录，以及私人资料上传、检索、问答和来源引用。

## 第一次启动

1. 安装 Git、JDK 21（设置 JAVA_HOME）、Node.js 20 和 pnpm 9.3.0（可运行 `npm install -g pnpm@9.3.0`）。数据库可以使用 Docker Desktop 的 Linux 容器，也可以使用 Windows 已有的 MySQL 和 Redis。
2. 在 PowerShell 中克隆项目，进入仓库根目录：

   ```powershell
   git clone https://github.com/xiaoxu-mygoing/continew-engineering-training.git
   cd continew-engineering-training
   ```

3. **使用 Docker 管理数据库**时，先启动 Docker Desktop，然后执行：

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\Start-Team.ps1
   ```

   脚本会生成每台电脑独立的数据库密码，初始化 MySQL 和 Redis，构建后端并安装前端依赖。首次需要联网，端口 13306、16379、8000 和 5173 应可用。请先停止占用这些端口的其他项目实例。

4. 显示 Ready 后打开 http://localhost:5173/ 。全新数据库的初始管理员是 `admin`，密码是 `admin123`，登录后请修改。每位成员在自己的数据库中创建测试用户并录入自己的人脸。登录页开启摄像头后自动开始随机动作活体验证，通过后自动识别并登录；免输账号需要先在个人中心的安全设置中开启。
5. 后续运行相同命令即可。后端改动后先停止当前 Java 服务，再加 `-Build` 重新构建。日志和私有运行数据在本机的 `local-runtime`。

## 使用 Windows 原生数据库

安装并启动 MySQL 8 和带密码的 Redis。创建 UTF-8 数据库 `continew_admin`，给应用账号授予这个数据库的权限（首次启动时 Liquibase 会建表）。在当前 PowerShell 设置下列变量，用你自己设置的密码替换占位符：

```powershell
$env:DB_USER = 'training'
$env:DB_PWD = '<MySQL 应用账号密码>'
$env:REDIS_PWD = '<Redis 密码>'
$env:DB_PORT = '3306'
$env:REDIS_PORT = '6379'
powershell -ExecutionPolicy Bypass -File .\Start-Team.ps1 -Native
```

## 按需启用课程功能

- **人脸识别**：安装 64 位 Python 3.11 或 3.12，确认 `py --version`，启动命令追加 `-Face`。脚本创建虚拟环境，下载并校验检测和识别模型。浏览器使用 localhost，并允许摄像头。首次或升级安装会准备 MediaPipe 和约 3.6 MB 的活体动作模型。操作与边界见[活体检测验收说明](人脸活体检测验收.md)。
- **私人资料问答**：安装 Python 和 Ollama，先启动 Ollama，再给启动命令追加 `-Rag`。脚本安装解析依赖并下载嵌入模型和问答模型。准备完毕后可用仓库中的 TXT、PDF、DOCX 验证。[问答演示步骤](任务2演示资料/资料问答使用说明.md)
- 两个参数可以同时使用；原生数据库模式保留 `-Native`。已下载的模型下次启动无需重新安装。Dify 工作流模板随附在演示目录中，运行主项目无需安装 Dify。

## 三人协作

每人从 main 新建自己的功能分支，例如 `git switch -c feature/face-login`。提交后推送分支，在 GitHub 发起 Pull Request 合并。仓库所有者在 Settings → Collaborators 邀请组员后，两人即可直接推送各自的分支。具体分工见[三人并行开发计划](阶段2三人并行开发计划.md)。

本项目基于 [ContiNew Admin](https://github.com/continew-org/continew-admin) 和 [ContiNew Admin UI](https://github.com/continew-org/continew-admin-ui)，许可证保留在各自目录。

## 任务三

已接入 Windows 原生 Neo4j 与本地模型的图谱问答。首次启动追加 `-Graph`，操作步骤和核心代码见[任务三图谱问答验收](任务3图谱问答验收.md)。
