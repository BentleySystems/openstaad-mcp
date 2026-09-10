# OpenSTAAD MCP · PTC-V1

通过 **Codex 桌面端 / Codex CLI**，让 GPT 使用本机的 Bentley STAAD.Pro 模型。
本项目基于 [Bentley OpenSTAAD MCP](https://github.com/BentleySystems/openstaad-mcp)，
增加本地 Programmatic Tool Calling（PTC）：GPT 提交一段 Python，在本机连续查询、筛选和汇总模型数据，最后返回摘要或导出 CSV/XLSX。

本分支仓库：[wenlong888442/openstaad-mcp · PTC-V1](https://github.com/wenlong888442/openstaad-mcp/tree/PTC-V1)。
安装目标是包含 `src/openstaad_mcp/ptc/` 和 `scripts/install-codex.ps1` 的完整工作副本。
如果从远程下载后缺少这些文件，说明该副本尚未包含这里描述的 PTC 改动，不能用上游安装包代替。

## 功能与适用范围

- **31 个只读 PTC 查询**：覆盖节点、杆件、板、实体、分组、截面、材料、荷载、支座、分析和钢设计结果。
- **一次程序完成多步查询**：通过 `execute_ptc` 调用注册的 `tools.*`，中间数据保留在本机；最终结果和 stdout 会返回客户端。
- **文件输入输出**：在允许目录内读写 CSV/XLSX，适合批量数据和多工作表报告。
- **多个 STAAD 实例**：先枚举模型，再按实例别名选择目标。
- **保留原 OpenSTAAD 能力**：建模、修改荷载和启动分析等操作继续通过 `execute_code` 使用。

PTC 通过标准 MCP 提供，不需要 Claude、Anthropic API 密钥或 Anthropic 的云端执行容器。
服务本身不要求 OpenAI API 密钥；GPT 的登录、模型和计费由客户端配置决定。
这也不是 OpenAI API 原生 PTC 接口，而是本项目自己的本地查询执行层。

## 环境要求

| 项目 | 要求 |
| --- | --- |
| 操作系统 | Windows 11 或更新版本；COM 服务必须运行在本机 Windows 环境 |
| STAAD.Pro | 2025 或更新版本；查询时需已启动并打开模型，具体接口以目标版本验证为准 |
| Python | 3.11 或更新版本，并能通过 `python` 启动；也可向安装脚本传入完整路径 |
| GPT 客户端 | 支持本地 MCP 的 Codex 桌面端或 Codex CLI |
| 下载工具 | Git；也可下载分支 ZIP 后解压 |
| 网络 | 首次安装需能访问 Python 包索引和 GitHub 上的 Bentley `openstaadpy` wheel |

安装脚本安装的是 **OpenSTAAD MCP 服务及其 Python 依赖**；Codex、Python 和 STAAD.Pro 需要预先安装。
下载与使用 Codex 见 [OpenAI 官方入门文档](https://developers.openai.com/codex/quickstart/)。

## 快速安装：Codex + 本地 PTC

### 1. 获取 PTC-V1

在 Windows PowerShell 中执行：

```powershell
git clone --branch PTC-V1 --single-branch https://github.com/wenlong888442/openstaad-mcp.git openstaad-mcp-PTC
cd openstaad-mcp-PTC
Test-Path .\scripts\install-codex.ps1
Test-Path .\src\openstaad_mcp\ptc\adapter.py
```

两个检查应均为 `True`。也可从该分支页面选择 **Code → Download ZIP**，解压后进入项目目录。
已有完整工作副本时，直接使用其目录；更新前先保存已有本地改动。

### 2. 安装服务并生成配置

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-codex.ps1
```

`Bypass` 仅作用于本次 PowerShell 进程。脚本会：

1. 创建或复用项目内专用于 Codex 的 `.venv-codex`，检查 Python 版本。
2. 以 editable 模式安装当前项目及依赖，执行依赖一致性检查。
3. 检查 CLI、允许目录和 PTC 查询目录。
4. 生成 `.venv-codex\openstaad-codex.toml`，其中包含实际安装路径。

脚本不会自动修改个人 Codex 配置。再次运行会刷新项目安装及生成的配置片段。
已有开发环境 `.venv` 不受这套安装流程影响。更新前先在客户端停止使用 `.venv-codex` 的 MCP 服务，避免 Windows 文件占用。
成功时应看到 `PTC queries: 31` 及配置文件路径。

指定 Python，或同时安装开发依赖：

```powershell
.\scripts\install-codex.ps1 -Python 'C:\Python311\python.exe' -Dev
```

`-Python` 仅用于新建虚拟环境；已有 `.venv-codex` 时继续使用其中的 Python。
默认允许 CSV/XLSX 访问项目目录；如需模型或报告目录，先确保这些目录存在，再在 PowerShell 中传入：

```powershell
.\scripts\install-codex.ps1 -AllowedDirectories 'D:\STAAD\Models', 'D:\STAAD\Reports'
```

### 3. 添加到 Codex

打开生成的 `.venv-codex\openstaad-codex.toml`，将其中的表合并到 Codex 配置中：

- 默认用户配置：`%USERPROFILE%\.codex\config.toml`；若设置了 `CODEX_HOME`，使用该目录下的配置。
- 项目配置：项目内 `.codex\config.toml`，仅对受信任项目生效。

保留文件中已有的其他配置。如果已经存在 `[mcp_servers.openstaad-ptc]`，更新该表，不要重复添加。
以下是可复制的格式示例，路径需替换为实际目录；完整文件见 [Codex 配置示例](examples/codex/config.toml)。

```toml
[mcp_servers.openstaad-ptc]
command = 'C:\Projects\openstaad-mcp-PTC\.venv-codex\Scripts\python.exe'
args = ['-m', 'openstaad_mcp.main', '--allowed-dirs', 'C:\Projects\openstaad-mcp-PTC']
cwd = 'C:\Projects\openstaad-mcp-PTC'
startup_timeout_sec = 30
tool_timeout_sec = 180
```

也可在桌面端 **Settings → MCP servers → Add server** 中选择 STDIO，填写相同的命令和参数。
保存后重启 MCP 服务或重启客户端。配置字段以 [OpenAI 官方 MCP 文档](https://developers.openai.com/codex/mcp/) 为准。

使用 Codex CLI 时，也可以在项目目录执行以下注册命令，代替手动添加服务器表：

```powershell
codex mcp add openstaad-ptc -- "$PWD\.venv-codex\Scripts\python.exe" -m openstaad_mcp.main --allowed-dirs "$PWD"
codex mcp list
```

CLI 注册后，如需更长的工具等待时间，可在对应配置表中设置 `tool_timeout_sec = 180`。
客户端等待时间不会改变服务内部 COM 调用的超时机制。

### 4. 验证连接

先让 Codex 调用 `discover_ptc`。这个工具无需运行 STAAD.Pro，应该返回 31 个查询定义。
再启动 STAAD.Pro，打开一个已保存的测试模型，在 Codex 中输入：

> 使用 openstaad-ptc：先列出 STAAD 实例，并核对模型路径。读取 PTC 接口说明后，统计该模型的节点数、杆件数和基础单位，只返回摘要。

存在多个实例时，明确指定 `list_instances` 返回的实例别名，例如 `staadPro1`。
检查分析或钢设计结果时，需先确认模型已有相应结果。

## GPT 客户端接入说明

| 使用方式 | 本项目接入方式 |
| --- | --- |
| 本机 Codex 桌面端 / CLI | 推荐 STDIO，由客户端通过本机 Python 启动 `openstaad_mcp.main` |
| 使用同一 Codex 主机配置的其他受支持客户端 | 使用该主机的 MCP 配置；具体支持范围以官方文档为准 |
| ChatGPT 网页版 / 云端会话 | 不会读取本机 `config.toml` 或直接启动本机 EXE；需要其支持的远程 MCP / 插件接入方案，本项目安装脚本不部署该方案 |
| Claude Desktop `.mcpb` | 原有 Claude 扩展打包格式，不是本项目推荐的 Codex 安装入口 |

STAAD.Pro 依赖 Windows COM。把客户端换为 GPT 不需要替换底层 COM 库，也不需要把模型搬到云端。
本地 STDIO 接入不需要开放 HTTP 端口。

### 可选：本机 HTTP

服务支持带 Bearer token 的 HTTP 模式。需要独立运行服务进程时，在项目目录启动：

```powershell
.\.venv-codex\Scripts\openstaad-mcp.exe --transport http --allowed-dirs "$PWD"
```

默认地址为 `http://127.0.0.1:18120/mcp`。未指定 token 时，终端会显示本次启动生成的 token。
将该值设置为 **启动 Codex 的环境中** 的 `OPENSTAAD_MCP_TOKEN`，使用以下服务器配置替换 STDIO 表：

```toml
[mcp_servers.openstaad-ptc]
url = 'http://127.0.0.1:18120/mcp'
bearer_token_env_var = 'OPENSTAAD_MCP_TOKEN'
startup_timeout_sec = 30
tool_timeout_sec = 180
```

服务也支持从 `OPENSTAAD_MCP_TOKEN` 环境变量读取固定 token。
默认 HTTP 仅绑定本机回环地址，并启用 Host / 浏览器跨源校验；这个地址不是 ChatGPT 云端可访问的部署地址。

## 可用 MCP 工具

| 工具 | 作用 |
| --- | --- |
| `discover_ptc` | 列出全部 PTC 查询，或按命名空间返回参数 schema 和说明 |
| `execute_ptc` | 执行调用注册 `tools.*` 的同步 Python，返回最终结果或文件摘要 |
| `list_instances` | 枚举运行中的 STAAD 实例、模型路径和版本 |
| `get_status` | 查看连接、版本、模型路径和分析状态 |
| `discover_api` | 查找原 OpenSTAAD API 技能与使用指导 |
| `read_skills` | 读取指定 API 技能文档 |
| `execute_code` | 使用受限 Python 和 `staad` 访问原 OpenSTAAD API，可能修改模型 |

31 个 PTC 查询通过 `execute_ptc` 内的 `tools.*` 调用，并不是 31 个单独注册的 MCP 顶层工具。

| PTC 命名空间 | 查询内容 |
| --- | --- |
| `geometry` | 单位、节点、杆件、板、实体、分组、节点连接杆件 |
| `properties` | 截面、材料、板厚、杆端释放 |
| `loads` | 荷载工况、组合及系数、参考荷载 |
| `supports` | 支座节点、类型、释放和弹簧 |
| `analysis` | 结果可用性、单位、杆件内力和极值、位移、支反力、板应力 |
| `design` | 钢设计利用率、控制工况、条文、截面和详细结果 |

完整参数与工程语义见 [PTC 使用说明](docs/PTC.zh-CN.md) 和 [扩展接口映射](docs/PTC-extensions.zh-CN.md)。
运行时以 `discover_ptc` 返回的 schema 为准。

## PTC 示例

以下代码作为 `execute_ptc` 的 `code` 参数提交，不能直接当作普通 Python 脚本运行。
PTC 沙箱提供 `tools`、`input_data`、`math`、`json` 和允许的内置函数，不提供 `staad`。

### 模型摘要

```python
result = {
    "units": tools.geometry.get_base_units(),
    "node_count": tools.geometry.get_node_count(),
    "member_count": tools.geometry.get_member_count(),
}
```

### 筛选水平杆件的设计利用率

```python
members = tools.geometry.get_members(up_axis="Y")
horizontal_ids = [m["id"] for m in members if m["is_horizontal"]]
ratios = tools.design.get_utilization(horizontal_ids)
result = {
    "horizontal_count": len(horizontal_ids),
    "critical": [r for r in ratios if r["available"] and r["ratio"] > 0.9],
    "unavailable": [r["member_id"] for r in ratios if not r["available"]],
}
```

`SET Z UP` 模型应使用 `up_axis="Z"`。阈值 `0.9` 只是筛选条件，不能替代设计规范判定。
钢设计结果来自实际设计参数块，不是通过某个分析工况自行计算的应力比。

更多示例：[杆端内力](examples/ptc/member_forces.py)、[跨工况包络](examples/ptc/member_envelope.py)、
[板应力报告](examples/ptc/plate_report.py)、[设计详情](examples/ptc/design_details.py)。

## CSV / XLSX 文件工作流

`execute_ptc` 和 `execute_code` 都支持：

| 参数 | 作用 |
| --- | --- |
| `input_data_path` | 读取服务所在机器上的 CSV/XLSX，注入 `input_data` |
| `output_data_path` | 将最终结果导出为 CSV/XLSX，向客户端返回文件摘要 |
| `overwrite` | 默认 `false`；只有明确设为 `true` 才覆盖已有输出文件 |

CSV 输入是行列表，若检测到表头则表头位于第一行；XLSX 输入为
`{sheet_name: {"columns": [...], "rows": [...]}}`。每次执行获得独立副本，修改副本不会改变源文件。

导出示例：

```python
members = tools.geometry.get_members()
result = [["member_id", "length"]] + [[m["id"], m["length"]] for m in members]
```

调用时将 `output_data_path` 指向允许目录下的 `.csv` 或 `.xlsx`。
多工作表 XLSX 使用 `{sheet_name: {"columns": [...], "rows": [...]}}` 作为结果。

路径必须位于服务的 `--allowed-dirs` 或客户端提供的 MCP roots 范围内。
输入与输出不能是同一个文件；UNC 路径及受保护系统目录写入被拒绝。
文件限制为 50 MB、100000 行、500 列、50 个输入工作表。

## 安全、隐私与运行限制

- PTC 的注册查询只读，但 `execute_code` 可以修改模型，PTC 也可按请求导出文件。
- 模型查询与中间数据处理在本机完成；最终结果、stdout 及客户端选择的上下文可能发送给模型服务。不要把“本机执行”理解为整个对话不出本机。
- Python 执行前进行 AST 校验，并限制内置函数、COM 内部属性及文件访问。这不是操作系统级隔离沙箱。
- 每次 PTC 程序最多 1000 次工具调用；每个 ID 列表最多 10000 项；每次结果批量最多 100000 行。
- 最终内联结果上限为 65536 个 UTF-8 字节；大结果应先聚合或通过文件导出。避免打印大量中间数据。
- COM 查询经专用 STA 线程执行。服务的默认 COM 等待超时为 120 秒，超时不能安全终止正在执行的 COM 调用；持续占用执行锁时需重启服务。
- PTC 不自动重新分析模型。工程结果需核对基础单位、局部/全局坐标、模型保存状态及分析、设计状态。

## CLI 参数

| 参数 | 默认值 | 含义 |
| --- | --- | --- |
| `--transport {stdio,http}` | `stdio` | MCP 传输方式 |
| `--allowed-dirs DIR [DIR ...]` | 未配置 | 允许的文件访问目录；也可使用客户端 MCP roots |
| `--log-level {DEBUG,INFO,WARNING,ERROR}` | `INFO` | stderr 日志级别 |
| `--port PORT` | `18120` | HTTP 监听端口 |
| `--token TOKEN` | 环境变量或自动生成 | HTTP Bearer token，也支持 `OPENSTAAD_MCP_TOKEN` |

以 `.\.venv-codex\Scripts\openstaad-mcp.exe --help` 的实际输出为准。

## 常见问题

| 现象 | 处理方式 |
| --- | --- |
| 下载后没有安装脚本或 PTC 目录 | 核对分支及提交是否包含完整 PTC 改动；Bentley 上游发布包不包含本分支的本地改动 |
| `python` 无法识别或版本低于 3.11 | 安装受支持的 Python，或通过 `-Python` 指定完整可执行文件路径 |
| PowerShell 禁止运行脚本 | 使用快速安装中的单进程 `-ExecutionPolicy Bypass` 命令 |
| pip 无法下载 `openstaadpy` | 检查 GitHub Releases 网络访问；依赖固定为 Bentley `26.0.0.62` wheel |
| 安装报 WinError 32 / 文件正在使用 | 在客户端停止使用 `.venv-codex` 的 MCP 服务后重新安装 |
| Codex 中只有原来的 5 个工具 | 核对 command 是否指向本项目 `.venv-codex`，重新安装并重启 MCP 服务 |
| Codex 配置解析失败 | 检查重复服务器表；Windows 路径使用 TOML 单引号或正确转义的双引号 |
| 没有发现 STAAD 实例 | 在同一 Windows 用户会话中启动 STAAD.Pro 并打开模型；核对进程权限和模型路径 |
| 多个模型无法确定目标 | 先调用 `list_instances`，再显式传入实例别名 |
| 导出路径被拒绝 | 检查目录存在且属于允许边界；更改启动参数后重启 MCP 服务 |
| 返回结果过大 | 在程序内筛选、汇总，或使用 `output_data_path` |
| 设计结果不可用 | 确认目标杆件已完成钢设计；不能将缺失结果当作零利用率 |
| 工具超时 | 缩小查询批次；客户端超时与 COM 等待超时不同，重启服务可释放被持续占用的执行环境 |

## 开发与验证

```powershell
# 安装开发依赖
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-codex.ps1 -Dev

# 单元测试，无需运行 STAAD.Pro
.\.venv-codex\Scripts\python.exe -m pytest -m "not integration" -q

# 代码检查
.\.venv-codex\Scripts\ruff.exe check .
.\.venv-codex\Scripts\ruff.exe format --check .
```

真实 COM 集成测试需先在 STAAD.Pro 中打开独立、已保存的测试模型，明确指定其路径：

```powershell
$env:OPENSTAAD_PTC_TEST_MODEL = 'D:\STAAD\Models\ptc-test.std'
.\.venv-codex\Scripts\python.exe -m pytest tests/ptc/test_server.py -m integration -v
```

该 PTC 集成测试只读检查杆件计数与枚举结果；Mock 测试不能替代真实模型验收。
原来的 `mcpb/` 保留为 Claude 扩展构建资源；Codex 使用上述本地安装脚本与 TOML 配置。

## 项目结构与来源

| 路径 | 内容 |
| --- | --- |
| `scripts/install-codex.ps1` | Windows 本地安装、依赖与目录校验、Codex 配置生成 |
| `examples/codex/config.toml` | 可移植的 Codex 配置模板 |
| `src/openstaad_mcp/server.py` | MCP 工具与请求处理 |
| `src/openstaad_mcp/ptc/` | 注册表、领域查询、参数校验和 PTC 运行时 |
| `src/openstaad_mcp/sandbox/` | AST、执行器、COM 代理与路径保护 |
| `docs/`、`examples/ptc/` | 工程语义、接口映射和查询程序示例 |
| `tests/ptc/` | PTC 单元测试与可选真实模型测试 |

项目基于 Bentley Systems 的 OpenSTAAD MCP，底层继续使用 Bentley `openstaadpy`。
本分支的 PTC 扩展及 Codex 安装适配不代表 Bentley 或 OpenAI 官方发布包。
版权与许可见 [LICENSE.md](LICENSE.md)，贡献方式见 [CONTRIBUTING.md](CONTRIBUTING.md)。
