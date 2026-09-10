# OpenSTAAD MCP · PTC-V1

通过 **Codex 桌面端 / Codex CLI**（及兼容 MCP 客户端），让 GPT 直接操控与读取本机的 Bentley STAAD.Pro 结构模型。

本项目基于 [Bentley OpenSTAAD MCP](https://github.com/BentleySystems/openstaad-mcp) 深度扩展，引入本地 **Programmatic Tool Calling (PTC)** 机制：GPT 只需提交一段 Python 代码，即可在本机靠近 STAAD.Pro COM 接口的环境下连续执行多步查询、数据筛选与统计汇总，最终仅向客户端返回精炼摘要或导出 CSV/XLSX 报表。

> **仓库与分支**：[wenlong888442/openstaad-mcp · PTC-V1](https://github.com/wenlong888442/openstaad-mcp/tree/PTC-V1)  
> **核心组件**：本分支包含专有 PTC 查询引擎 `src/openstaad_mcp/ptc/` 及一键安装脚本 `scripts/install-codex.ps1`。如从上游官方仓库下载，将不包含 PTC 功能。

---

## 目录

- [核心特性与优势](#核心特性与优势)
- [环境要求](#环境要求)
- [快速安装与配置 (Codex)](#快速安装与配置-codex)
  - [1. 获取分支源码](#1-获取分支源码)
  - [2. 运行自动化安装脚本](#2-运行自动化安装脚本)
  - [3. 配置 Codex 客户端](#3-配置-codex-客户端)
  - [4. 验证服务与连接](#4-验证服务与连接)
- [客户端接入说明](#客户端接入说明)
  - [标准 STDIO 模式 (推荐)](#标准-stdio-模式-推荐)
  - [可选 HTTP 模式](#可选-http-模式)
- [可用 MCP 工具](#可用-mcp-工具)
  - [MCP 顶层工具](#mcp-顶层工具)
  - [PTC 查询命名空间 (31 个方法)](#ptc-查询命名空间-31-个方法)
- [PTC 代码示例](#ptc-代码示例)
  - [示例 1：模型基础信息与规模统计](#示例-1模型基础信息与规模统计)
  - [示例 2：筛选水平受力临界构件的设计利用率](#示例-2筛选水平受力临界构件的设计利用率)
  - [示例 3：多工况杆端内力包络分析](#示例-3多工况杆端内力包络分析)
- [CSV / XLSX 文件工作流](#csv--xlsx-文件工作流)
- [安全、隐私与执行边界](#安全隐私与执行边界)
- [命令行参数参考](#命令行参数参考)
- [常见问题与排查 (FAQ)](#常见问题与排查-faq)
- [开发与测试验证](#开发与测试验证)
- [项目结构与开源许可](#项目结构与开源许可)

---

## 核心特性与优势

传统 MCP 交互中，大语言模型对每个查询都需要进行一次网络往返，且动辄返回成千上万个节点或内力数据，极易撑爆上下文窗口（Context Window）并消耗大量 Token。**PTC-V1** 通过在服务侧本地执行查询程序，彻底解决了该痛点：

- **31 个只读 PTC 领域查询**：全面覆盖几何节点、杆件构件、板单元、实体、截面属性、材料常数、分组、荷载工况与组合、支座约束、有限元分析结果与钢结构规范设计结果。
- **单次交互完成复合分析**：通过 `execute_ptc` 调用沙箱内注册的 `tools.*`，中间海量数据在本机内存中完成筛选、排序和统计，仅回传必要的结果摘要。
- **大容量文件读写与报表导出**：支持在受控安全目录内读取 CSV/XLSX 作为 `input_data`，或将复杂分析结果直接导出为多工作表 Excel 报表。
- **多 STAAD 实例精准路由**：自动扫描 Windows 运行对象表 (ROT)，识别多开的 STAAD.Pro 窗口及各自模型路径，按实例别名指定操作对象。
- **双模并存，能力不减**：
  - **PTC 模式 (`execute_ptc`)**：严格只读，专注于大规模数据的高效查询与聚合分析。
  - **原生代码模式 (`execute_code`)**：保留完整建模、荷载施加、约束调整和启动计算求解的原生 OpenSTAAD 能力。
- **自托管标准协议**：完全基于标准 Model Context Protocol (MCP)，无需 Anthropic 云端容器或特定云厂商闭源 API，无附加 API 密钥要求。

---

## 环境要求

| 项目 | 要求 | 说明 |
| --- | --- | --- |
| **操作系统** | Windows 11 / Windows 10 (64 位) | OpenSTAAD 依赖 Windows COM 组件，必须运行在本机 Windows 环境 |
| **STAAD.Pro** | 2025 或更新版本 | 查询时 STAAD.Pro 需处于运行状态并已打开 `.std` 模型文件 |
| **Python** | **3.11 或更新版本 (64 位)** | **必须为 64 位 Python**（与 STAAD.Pro 进程架构匹配），已配置在 PATH 中或提供完整路径 |
| **客户端** | Codex 桌面端 / Codex CLI | 或任意兼容本地 STDIO / HTTP MCP 的客户端 (如 Claude Code, Cursor 等) |
| **网络** | 首次安装时需联网 | 用于安装 Python 依赖及下载 GitHub Release 上的 Bentley `openstaadpy-26.0.0.62` wheel |

> [!IMPORTANT]
> 安装脚本负责部署 **OpenSTAAD MCP 服务及其专属 Python 虚拟环境**；STAAD.Pro、Python 解释器与 Codex 客户端需事先就绪。

---

## 快速安装与配置 (Codex)

### 1. 获取分支源码

在 Windows PowerShell 中克隆 `PTC-V1` 分支：

```powershell
git clone --branch PTC-V1 --single-branch https://github.com/wenlong888442/openstaad-mcp.git openstaad-mcp-PTC
cd openstaad-mcp-PTC

# 验证关键文件是否存在
Test-Path .\scripts\install-codex.ps1
Test-Path .\src\openstaad_mcp\ptc\adapter.py
```

两个检测输出均应为 `True`。若从网页端下载，请通过分支页面的 **Code → Download ZIP** 下载解压。

### 2. 运行自动化安装脚本

在项目根目录下执行安装脚本：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-codex.ps1
```

> **执行说明**：`-ExecutionPolicy Bypass` 仅对当前执行进程有效。脚本执行完毕后将完成：
> 1. 在项目目录内自动创建专属虚拟环境 `.venv-codex`，并校验 Python 版本（3.11+ 且为 64 位）。
> 2. 以可编辑模式 (`pip install -e .`) 部署项目及依赖，校验依赖一致性。
> 3. 验证命令行工具、PTC 31 个查询模块及文件访问安全边界。
> 4. 在 `.venv-codex\openstaad-codex.toml` 生成包含机器绝对路径的配置片段。

- 如需指定特定的 64 位 Python 解释器或安装开发调试依赖：
  ```powershell
  .\scripts\install-codex.ps1 -Python 'C:\Python311\python.exe' -Dev
  ```
- 如需额外允许模型与报表所在目录的 CSV/XLSX 读写权限：
  ```powershell
  .\scripts\install-codex.ps1 -AllowedDirectories 'D:\STAAD\Models', 'D:\STAAD\Reports'
  ```

安装成功后终端会提示 `PTC queries: 31`，并给出生成的配置文件位置。

### 3. 配置 Codex 客户端

打开生成的 `.venv-codex\openstaad-codex.toml`，将对应配置合并到 Codex 配置文件中：

- **用户全局配置**：`%USERPROFILE%\.codex\config.toml`（或 `$env:CODEX_HOME\config.toml`）。
- **项目局部配置**：当前项目根目录下的 `.codex\config.toml`（仅对受信任工作区生效）。

**配置内容示例**（完整模板参见 [examples/codex/config.toml](examples/codex/config.toml)）：

```toml
[mcp_servers.openstaad-ptc]
command = 'D:\GPT\openstaad-mcp-PTC\.venv-codex\Scripts\python.exe'
args = ['-m', 'openstaad_mcp.main', '--allowed-dirs', 'D:\GPT\openstaad-mcp-PTC']
cwd = 'D:\GPT\openstaad-mcp-PTC'
startup_timeout_sec = 30
tool_timeout_sec = 180
```

> [!TIP]
> **使用 Codex CLI 时**，也可直接在项目根目录下运行一条命令完成注册：
> ```powershell
> codex mcp add openstaad-ptc -- "$PWD\.venv-codex\Scripts\python.exe" -m openstaad_mcp.main --allowed-dirs "$PWD"
> codex mcp list
> ```

配置保存后，重启 Codex 客户端或在设置中重启 MCP 服务器。

### 4. 验证服务与连接

1. **基础验证**：在 Codex 中让其调用 `discover_ptc`。该工具无需开启 STAAD.Pro 即可返回 31 个只读查询方法的 schema 定义。
2. **联动测试**：
   - 启动 STAAD.Pro 并打开任一测试结构模型（`.std` 文件）。
   - 在 Codex 对话框中发送如下提示词：
   > 请使用 openstaad-ptc 工具：先列出运行中的 STAAD 实例及模型路径。确认连接后，统计当前模型的节点总数、杆件总数和基础长度/力单位，返回简洁摘要。

若存在多个打开的模型，在调用时明确传入 `list_instances` 返回的实例别名（如 `instance="staadPro1"`）。

---

## 客户端接入说明

| 接入场景 | 推荐方式 | 接入说明 |
| --- | --- | --- |
| **本机 Codex 桌面端 / CLI** | **STDIO (推荐)** | 由客户端本地直接启动 `.venv-codex` 中的 Python 进程，无需占用端口 |
| **通用本地 MCP 客户端** | STDIO / 本机 HTTP | 支持 Claude Code, Cursor, Windsurf, Claude Desktop 等标准 MCP 客户端 |
| **ChatGPT 网页端 / 云端** | 暂不支持直接连接 | STAAD.Pro 依托 Windows 局域/单机 COM 机制，云端服务无法穿透访问本机桌面应用 |

### 标准 STDIO 模式 (推荐)

STDIO 是本机集成的标准方式，生命周期由客户端完全托管，零网络端口暴露，安全性最高。

### 可选 HTTP 模式

当需要长期作为独立后台服务运行，或供局域网内受信任客户端连接时：

```powershell
.\.venv-codex\Scripts\openstaad-mcp.exe --transport http --allowed-dirs "$PWD"
```

默认监听地址为 `http://127.0.0.1:18120/mcp`。控制台将输出启动生成的 Bearer Token。在客户端配置：

```toml
[mcp_servers.openstaad-ptc]
url = 'http://127.0.0.1:18120/mcp'
bearer_token_env_var = 'OPENSTAAD_MCP_TOKEN'
startup_timeout_sec = 30
tool_timeout_sec = 180
```

服务内置 `SecFetchMiddleware`，默认仅绑定回环地址并对 Host 及浏览器跨源请求进行严格校验。

---

## 可用 MCP 工具

### MCP 顶层工具

客户端在 MCP 协议层可见 7 个顶层核心工具：

| 工具名称 | 权限属性 | 功能简述 |
| --- | --- | --- |
| `discover_ptc` | 只读 | 查询全部 31 个 PTC 接口或指定命名空间的详细参数 Schema 与文档说明 |
| `execute_ptc` | 只读沙箱 | 接收并运行包含 `tools.*` 调用的 Python 复合查询脚本，返回分析结果或报表摘要 |
| `list_instances` | 只读 | 扫描 Windows ROT，枚举运行中的 STAAD 进程实例名、版本及当前打开的文件路径 |
| `get_status` | 只读 | 查看目标实例的连接就绪状态、版本兼容性、模型路径及计算分析状态 |
| `discover_api` | 只读 | 检索原生 OpenSTAAD API 知识库与技能指导列表 |
| `read_skills` | 只读 | 按需查阅特定 OpenSTAAD API 技能手册与参考文档 |
| `execute_code` | 读写执行 | 在受控沙箱中直接通过 `staad` 原生对象操作 OpenSTAAD，支持修改模型与运行求解 |

### PTC 查询命名空间 (31 个方法)

在 `execute_ptc` 脚本内部，可通过 `tools.<命名空间>.<方法>` 访问 31 个高能效只读接口：

| 命名空间 | 覆盖范围与关键方法 |
| --- | --- |
| **`geometry`** | 基础单位 (`get_base_units`)、节点/杆件/板/实体数量与坐标详情、节点连接拓扑、实体分组 (`get_groups`) 等 |
| **`properties`** | 截面几何尺寸与特性 (`get_member_properties`)、材料常数、板单元厚度分布、杆端自由度释放 (`get_member_releases`) 等 |
| **`loads`** | 主荷载工况、荷载组合与分项系数、参考荷载定义 (`get_load_cases`) 等 |
| **`supports`** | 支座节点定义、约束类型（固定/铰接）、各方向释放及弹性弹簧刚度 (`get_supports`) 等 |
| **`analysis`** | 分析结果可用性、力与位移输出单位、杆端内力 (六分量)、杆件包络极值、节点位移、支座反力、板应力等 |
| **`design`** | 钢结构设计利用率（应力比）、控制工况、设计规范条文、临界截面及详细计算结果 (`get_utilization`) 等 |

> 详细参数类型、字段说明与工程解释详见：  
> 📖 [PTC 详细使用说明 (PTC.zh-CN.md)](docs/PTC.zh-CN.md)  
> 📖 [OpenStaadPython 扩展接口映射 (PTC-extensions.zh-CN.md)](docs/PTC-extensions.zh-CN.md)

---

## PTC 代码示例

以下代码块均作为 `execute_ptc` 工具的 `code` 字符串参数传入。  
沙箱环境已预置 `tools`、`input_data`、`math`、`json`，无需也无法直接调用底层未经审计的 `staad` COM 指针。

### 示例 1：模型基础信息与规模统计

```python
# 获取全局单位制度及几何规模
units = tools.geometry.get_base_units()
node_count = tools.geometry.get_node_count()
member_count = tools.geometry.get_member_count()

result = {
    "units": units,
    "summary": {
        "total_nodes": node_count,
        "total_members": member_count,
    },
}
```

### 示例 2：筛选水平受力临界构件的设计利用率

```python
# 1. 批量读取所有杆件，根据 Y 轴竖向规则自动判定水平杆件
members = tools.geometry.get_members(up_axis="Y")
horizontal_ids = [m["id"] for m in members if m["is_horizontal"]]

# 2. 仅针对水平杆件查询最新的钢结构设计利用率（应力比）
ratios = tools.design.get_utilization(horizontal_ids)

# 3. 本地筛选超过 0.9 的临界杆件，避免将数千条数据全部回传
critical = [r for r in ratios if r.get("available") and r.get("ratio", 0) > 0.9]
unavailable = [r["member_id"] for r in ratios if not r.get("available")]

result = {
    "total_horizontal_members": len(horizontal_ids),
    "critical_count": len(critical),
    "critical_members": critical,
    "missing_design_results": unavailable,
}
```

> [!NOTE]
> 若模型为 `SET Z UP` 坐标体系，请传入 `up_axis="Z"`。利用率直接取自 STAAD 计算内核生成的最新设计参数块。

### 示例 3：多工况杆端内力包络分析

```python
# 查询指定荷载工况下指定构件的杆端六分量内力
member_ids = [101, 102, 103]
load_cases = [1, 2, 101]  # 工况与组合编号

forces = tools.analysis.get_member_forces(
    member_ids=member_ids,
    load_cases=load_cases,
    coordinate_system="local",
)

# 本地快速找出每根构件的最大弯矩 MZ
envelopes = {}
for f in forces:
    mid = f["member_id"]
    mz = abs(f["mz"])
    if mid not in envelopes or mz > envelopes[mid]["max_mz"]:
        envelopes[mid] = {"max_mz": mz, "load_case": f["load_case"], "end": f["end"]}

result = envelopes
```

更多完整工程案例可参考：
- 杆端内力详查：[examples/ptc/member_forces.py](examples/ptc/member_forces.py)
- 跨工况内力包络：[examples/ptc/member_envelope.py](examples/ptc/member_envelope.py)
- 板单元应力报表：[examples/ptc/plate_report.py](examples/ptc/plate_report.py)
- 钢构件设计详情：[examples/ptc/design_details.py](examples/ptc/design_details.py)

---

## CSV / XLSX 文件工作流

`execute_ptc` 与 `execute_code` 均支持**服务端数据文件直通机制**：

| 控制参数 | 类型 | 行为说明 |
| --- | --- | --- |
| `input_data_path` | 字符串 | 从指定路径读取 CSV 或 XLSX 文件，解析并注入沙箱变量 `input_data` |
| `output_data_path` | 字符串 | 将脚本的 `result` 导出保存为 CSV 或 XLSX 文件，仅向客户端返回文件行数与大小摘要 |
| `overwrite` | 布尔值 | 默认 `false`；设为 `true` 时允许覆盖已存在的输出文件 |

### 导出示例 (输出为 CSV)

```python
# 构造表格行列表：首行为表头
members = tools.geometry.get_members()
result = [["member_id", "length", "is_horizontal"]] + [[m["id"], m["length"], m["is_horizontal"]] for m in members]
```

### 多工作表导出 (输出为 XLSX)

将 `result` 设置为形如 `{ "SheetName": { "columns": [...], "rows": [...] } }` 的字典格式，即可一次性导出结构规整的多 Sheet Excel 工程报表。

> **安全规则**：
> - 读写路径必须落在 `--allowed-dirs` 允许目录或客户端 MCP roots 边界内。
> - 严禁读写系统敏感目录（如 `Windows/`, `Program Files/`）或 UNC 共享网络路径。
> - 单个数据文件硬性限制：最大 50 MB、行数不超过 100,000 行、列数不超过 500 列。

---

## 安全、隐私与执行边界

1. **执行边界分明**：PTC 查询（`tools.*`）全量为只读设计；模型的几何修改、荷载施加与分析运行仅能通过 `execute_code` 执行。
2. **本地数据隔离**：STAAD 原始数据全部保留在本机内存中进行运算处理，仅通过最后明确指定的 `result`、`stdout` 以及导出文件向大模型返回摘要。
3. **AST 静态安全沙箱**：执行前通过 Python AST 解析器进行静态语法与属性检查，阻断内置危险模块（`os`, `sys`, `subprocess` 等）、禁止访问私有 COM 属性（如 `_oleobj_`）。
4. **并发与线程安全**：Windows COM API 要求 STA (Single-Threaded Apartment) 运行机制。服务通过专用的 STA 线程池调度所有 COM 调用，默认 COM 挂起超时为 120 秒。
5. **内联回传阈值**：内联 JSON 结果上限为 64 KB (65,536 字节)；超过此规模应在 Python 内部进行数据聚合或使用 `output_data_path` 导出为文件。

---

## 命令行参数参考

```powershell
openstaad-mcp [OPTIONS]
```

| 参数选项 | 默认值 | 说明 |
| --- | --- | --- |
| `--transport {stdio,http}` | `stdio` | MCP 通信传输方式 |
| `--allowed-dirs DIR [...]` | 无限制 (需明确设置) | 允许读写 CSV/XLSX 的目录白名单 |
| `--log-level {DEBUG,INFO,WARNING,ERROR}` | `INFO` | 输出至 stderr 的日志级别 |
| `--port PORT` | `18120` | HTTP 传输模式监听的 TCP 端口 |
| `--token TOKEN` | 随机生成或环境变量 | HTTP 认证 Bearer Token，支持 `OPENSTAAD_MCP_TOKEN` |

---

## 常见问题与排查 (FAQ)

### 安装与运行环境

| 常见问题 | 原因分析与排查方案 |
| --- | --- |
| **下载后找不到安装脚本或 `ptc/` 目录** | 请确认克隆的是本仓库的 `PTC-V1` 分支；上游官方仓库尚未合并本分支改动。 |
| **`python` 命令未识别或版本低于 3.11** | 请安装 64 位 Python 3.11+ 并添加至 PATH，或通过 `-Python 'C:\Path\python.exe'` 指定。 |
| **PowerShell 提示禁止运行脚本** | 使用推荐的临时授权指令：`powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-codex.ps1`。 |
| **依赖安装报 WinError 32 文件被占用** | 客户端正在运行该虚拟环境中的 Python 进程。请先关闭 Codex 或重启 MCP 进程后重新运行安装。 |
| **pip 无法下载 `openstaadpy` wheel** | 检查机器对 GitHub Releases 的网络连接；依赖固定为 Bentley 官方发布的 `openstaadpy-26.0.0.62`。 |

### 客户端连接与工具发现

| 常见问题 | 原因分析与排查方案 |
| --- | --- |
| **Codex 中只显示原版的 5 个工具，缺少 PTC** | 检查 Codex 配置中 `command` 是否精确指向 `.venv-codex\Scripts\python.exe`，更新后完全重启 Codex。 |
| **Codex 提示配置文件解析失败** | 检查 TOML 文件是否存在重复的 `[mcp_servers.openstaad-ptc]` 表头；Windows 路径请使用单引号或转义双引号 `\\`。 |
| **提示找不到 STAAD 实例** | 确保 STAAD.Pro 已经启动、在同一 Windows 用户会话下运行，并且已经打开了一个已保存的模型文件。 |
| **多模型打开时操作了错误的结构** | 先调用 `list_instances` 查看模型路径与实例别名，在调用 `execute_ptc` 或 `execute_code` 时显式传入 `instance="staadPro1"`。 |

### 查询执行与结果

| 常见问题 | 原因分析与排查方案 |
| --- | --- |
| **钢结构设计利用率返回空或不可用** | 确认该模型在 STAAD 中已定义钢结构设计参数块并成功运行分析；未进行设计的杆件无法读取有效应力比。 |
| **提示返回结果过大 (Exceeds 65536 bytes)** | 避免打印大量调试中间数据；在 Python 中筛选核心指标，或指定 `output_data_path` 导出报表。 |
| **文件导出提示路径越界被拒绝** | 检查目标路径是否已被包含在启动参数 `--allowed-dirs` 中，且不属于系统敏感保留目录。 |
| **工具调用超时 (Timeout)** | 复杂模型单次查询建议分批传入 ID 或缩小工况范围；客户端等待时间可通过 `tool_timeout_sec = 180` 调大。 |

---

## 开发与测试验证

针对开发者与二次维护人员：

```powershell
# 1. 安装开发与调试依赖
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-codex.ps1 -Dev

# 2. 执行全量单元测试 (纯 Mock 环境，无需开启 STAAD.Pro)
.\.venv-codex\Scripts\python.exe -m pytest -o cache_dir="$env:TEMP\pytest_cache" -m "not integration" -q

# 3. 代码规范与格式检查
.\.venv-codex\Scripts\ruff.exe check .
.\.venv-codex\Scripts\ruff.exe format --check .
```

### 真实 STAAD.Pro 联动测试 (可选)

在本机 STAAD.Pro 中打开一个专用的测试模型后，指定其绝对路径执行集成测试：

```powershell
$env:OPENSTAAD_PTC_TEST_MODEL = 'D:\STAAD\Models\ptc-test.std'
.\.venv-codex\Scripts\python.exe -m pytest tests/ptc/test_server.py -m integration -v
```

---

## 项目结构与开源许可

```text
openstaad-mcp/
├── scripts/
│   └── install-codex.ps1         # Windows 本地自动化部署与 Codex 配置生成脚本
├── examples/
│   ├── codex/config.toml         # 标准可移植 Codex 配置范例
│   └── ptc/                      # 典型工程场景下的 PTC 查询脚本示例
├── docs/
│   ├── PTC.zh-CN.md              # PTC 核心接口与工程语义规范
│   └── PTC-extensions.zh-CN.md   # OpenStaadPython 扩展接口映射详情
├── src/openstaad_mcp/
│   ├── ptc/                      # PTC 引擎：命名空间、注册表、参数校验与运行上下文
│   ├── sandbox/                  # 代码沙箱：AST 语法校验、COM 属性代理与路径白名单
│   ├── file_io/                  # 安全 CSV/XLSX 读写器与数据验证
│   ├── server.py                 # MCP 协议处理与顶层工具定义
│   └── main.py                   # 服务入口与命令行配置解析
└── tests/
    └── ptc/                      # PTC 单元与集成测试用例
```

- **上游基础**：本项目基于 Bentley Systems 官方开源的 [OpenSTAAD MCP](https://github.com/BentleySystems/openstaad-mcp)，底层采用 Bentley 发布的 `openstaadpy` 库。
- **分支定位**：本 `PTC-V1` 分支扩展及 Codex 适配由社区维护，不代表 Bentley Systems 或 OpenAI 的官方发布。
- **协议说明**：本项目遵循 [MIT 许可证](LICENSE.md)，欢迎提交 Issue 与 Pull Request 共同完善。
