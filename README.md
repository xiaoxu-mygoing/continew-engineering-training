# ContiNew Admin 工程实训

本项目包含人脸活体登录、私人资料管理、RAG 问答和 GraphRAG 图谱问答。后端在 `continew-admin`，前端在 `continew-admin-ui`。

## Windows 环境

安装以下依赖。主流程适用于 Windows x64，数据库也在 Windows 原生运行。

| 依赖 | 用途与版本 |
| --- | --- |
| Git、PowerShell 7 | 下载源码和执行项目脚本。本机使用 Git 2.55 和 PowerShell 7.6。[Git 安装](https://git-scm.com/install/windows) · [PowerShell 安装](https://learn.microsoft.com/powershell/scripting/install/install-powershell-on-windows) |
| JDK 21 x64 | Java 后端和 Neo4j。本机使用 JDK 21.0.7。设置 `JAVA_HOME` 并将 `%JAVA_HOME%\bin` 加入 `Path`。仓库的 Maven Wrapper 会下载 Maven 3.9.16。[JDK 下载](https://adoptium.net/temurin/releases/?version=21) |
| Node.js 24 LTS、pnpm 9.3.0 | Vue 前端。本机使用 Node.js 24.18.0。执行 `npm install -g pnpm@9.3.0` 安装 pnpm。[Node.js 下载](https://nodejs.org/en/download) |
| MySQL Community Server 8.0 | 保存账号、元数据和私有资料，本机版本为 8.0.46。[MySQL 版本归档](https://downloads.mysql.com/archives/community/) |
| 带密码的 Redis | 保存验证码、会话、限流计数和活体临时状态。本机使用 Redis 8.10.3 的社区 Windows 构建。[Windows 构建发布页](https://github.com/redis-windows/redis-windows/releases) |
| Python x64 | 人脸、向量索引和图谱。新建环境可选 Python 3.11，本机既有服务虚拟环境为 3.9.13。保留 Windows 的 `py` 启动器。[Python 下载](https://www.python.org/downloads/windows/) |
| C++ Build Tools、Windows SDK | InsightFace 从源码构建时使用。选择「使用 C++ 的桌面开发」。[Microsoft 下载](https://visualstudio.microsoft.com/downloads/) |
| Ollama for Windows | 本地问答与向量模型服务。本机使用 0.40.15。[Ollama 下载](https://ollama.com/download/windows) |
| Neo4j Community 5.26.0 | GraphRAG 图数据库，首次使用 `-Graph` 时脚本下载并校验 Windows 安装包。[Neo4j 初始化脚本](Setup-Graph.ps1) |
| Chrome 或 Edge、摄像头 | 浏览器访问本机系统并允许摄像头，用于录入和刷脸登录。 |

前端用 `pnpm install --frozen-lockfile` 安装依赖。启动脚本为人脸和问答分别创建 Python 虚拟环境。[前端依赖锁文件](continew-admin-ui/pnpm-lock.yaml) · [人脸 Python 依赖](continew-admin/training-face/ciao_requirements.txt) · [RAG 与 GraphRAG Python 依赖](continew-admin/training-rag/requirements.txt)

### 本地模型

| 模型 | 用途及获取方式 |
| --- | --- |
| InsightFace `buffalo_l` | 检测、姿态估计、512 维人脸特征。服务首次启动下载，解压后本机约 325 MiB，位于 `local-runtime/face-ciao/models/buffalo_l`。 |
| `nomic-embed-text` | 生成 768 维文档和图谱实体向量。通过 `ollama pull nomic-embed-text` 下载，本机约 274 MB。 |
| `qwen2.5:3b` | 本地问答和图谱关系抽取。通过 `ollama pull qwen2.5:3b` 下载，本机约 1.93 GB。 |

通过 `-Rag` 或 `-Graph` 启动时会拉取两个 Ollama 模型。要把模型放到 D 盘，可在启动 Ollama 进程前设置 `$env:OLLAMA_MODELS = 'D:\OllamaModels'`。源码仓库包含虚构演示文件和下载配置，模型权重、本机数据库、真实资料、密码和人脸模板由各自电脑保管。首次安装需访问 Maven Central、npm、PyPI、Neo4j 下载站、InsightFace 模型源和 Ollama 模型库。

## 使用 Windows 原生数据库

安装并启动本机 MySQL 8.0 与带密码的 Redis。新建库时用 MySQL 管理账号执行下面的 SQL，替换密码占位符。Liquibase 会在首次启动时建表。

```sql
CREATE DATABASE IF NOT EXISTS continew_admin CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'training'@'127.0.0.1' IDENTIFIED BY '<MySQL 应用账号密码>';
GRANT ALL PRIVILEGES ON continew_admin.* TO 'training'@'127.0.0.1';
```

使用 Redis 社区 Windows ZIP 版时，可在程序目录创建 `redis-local.conf`，替换密码后运行 `redis-server.exe redis-local.conf`。

```conf
bind 127.0.0.1
port 6379
requirepass "<Redis 密码>"
```

## 首次启动全部功能

在 PowerShell 7 中克隆项目，核对工具版本。数据库端口填写实际监听值。本机演示数据使用的端口是 MySQL `13306` 和 Redis `16379`。

```powershell
git clone https://github.com/xiaoxu-mygoing/continew-engineering-training.git
Set-Location .\continew-engineering-training

java -version
node --version
pnpm --version
$python = (py -3.11 -X utf8 -c "import sys; print(sys.executable)").Trim()
& $python --version

$env:DB_HOST = '127.0.0.1'
$env:DB_NAME = 'continew_admin'
$env:DB_USER = 'training'
$env:DB_PORT = '3306'
$env:DB_PWD = Read-Host 'MySQL 应用账号密码' -MaskInput
$env:REDIS_HOST = '127.0.0.1'
$env:REDIS_PORT = '6379'
$env:REDIS_PWD = Read-Host 'Redis 密码' -MaskInput
```

启动 Ollama，运行 `ollama list` 确认能连接服务。命令行安装可在另一终端运行 `ollama serve`。然后回到项目终端执行以下命令。

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\Start-Team.ps1 -Native -Face -Rag -Graph -Python $python
```

`-Python` 可填所选 64 位 `python.exe` 的绝对路径，用于创建虚拟环境。已有虚拟环境继续沿用自己的解释器。`-Face` 准备人脸服务，`-Rag` 准备资料问答，`-Graph` 额外准备 Neo4j。终端显示 `Ready` 后打开 [实训工作台](http://localhost:5173/)。首次启动人脸服务时可访问 `http://127.0.0.1:18100/health`，等 `ready` 为 `true` 再录入。

全新数据库的本地初始管理员为 `admin`，初始密码是 `admin123`，请在首次登录后修改。成员分别在自己的库里建演示账号并录入人脸。旧模型的特征需要重新录入。双账号联调可用 Chrome 登录 A、Edge 登录 B，两个浏览器都访问 `5173`。

### 后续启动和升级

- 已初始化全部功能时，启动 MySQL、Redis 和 Ollama，在当前终端配置数据库变量，然后运行 `pwsh -NoProfile -ExecutionPolicy Bypass -File .\Start-Team.ps1 -Native`。脚本复用虚拟环境和本机数据。
- 升级时，在 `main` 分支执行 `git pull --ff-only`。关闭本项目的 Java、Vite 和人脸服务进程，再用 `-Native -Build` 运行启动脚本。Liquibase 会自动应用数据库迁移。Python 清单有更新时，按首次启动命令加上对应功能参数安装新依赖。
- Docker Desktop 可用于承载数据库。去掉 `-Native` 后，Compose 启动 MySQL 8.0 和 Redis 7 容器，映射到宿主机的 `13306` 和 `16379`。[数据库 Compose 配置](compose.yaml)
- Dify 用于课程加分演示，模板可导入 Dify 工作室测试分支。[工作流模板](任务2演示资料/Dify问答分支演示.yml)

### 端口与排查

| 端口 | 服务 |
| --- | --- |
| `5173`、`8000` | Vite 前端和 Java 后端。Vite 将 `/dev-api` 转发到后端。 |
| `18100` | InsightFace，访问 `/health` 检查模型状态。 |
| `11434` | Ollama 本地模型服务。 |
| `7474`、`7687` | Neo4j HTTP 和 Bolt。 |
| `3306`、`6379` | Windows MySQL 和 Redis 的常用端口，按实际端口配置。 |

启动失败时先查看 `local-runtime/backend-errors.log`、`local-runtime/frontend-errors.log`、`local-runtime/face-ciao/service-errors.log` 和 `local-runtime/neo4j/start-errors.log`。端口冲突时可用 `Get-NetTCPConnection -State Listen -LocalPort 5173,8000,18100` 查进程。

## 验收说明

- [人脸活体验收](人脸活体检测验收.md)
- [私人资料与 RAG 说明](任务2演示资料/资料问答使用说明.md)
- [GraphRAG 与知识图谱验收](任务3图谱问答验收.md)

## 三人协作

每人从 main 新建自己的功能分支，例如 `git switch -c feature/face-login`。提交后推送分支，在 GitHub 发起 Pull Request 合并。仓库所有者在 Settings → Collaborators 邀请组员后，两人即可直接推送各自的分支。具体分工见[三人并行开发计划](阶段2三人并行开发计划.md)。

本项目基于 [ContiNew Admin](https://github.com/continew-org/continew-admin) 和 [ContiNew Admin UI](https://github.com/continew-org/continew-admin-ui)，许可证保留在各自目录。
