# OpenSTAAD PTC v1 使用说明

本分支在 Bentley OpenSTAAD MCP 上增加本地 Programmatic Tool Calling：
模型通过一次 `execute_ptc` 提交 Python，代码调用注册的 `tools.*`，
在本机筛选、组合和汇总结果，最终只将选定结果交给客户端。
这是通过普通 MCP 使用的自托管实现，不需要 Anthropic API 密钥或云端代码执行容器。

当前共 31 个查询接口：下文介绍原 14 个接口，新增 17 个接口及底层方法映射见
[OpenStaadPython 参考功能扩展](PTC-extensions.zh-CN.md)。

## 启动

Windows PowerShell，在项目目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\openstaad-mcp.exe --help
```

以下是客户端通用的 stdio 配置示例。请将路径替换为实际克隆目录。
配置文件仅供参考，本次改造不会自动修改任何客户端配置。

```json
{
  "mcpServers": {
    "openstaad-ptc": {
      "command": "D:\\GPT\\openstaad-mcp-PTC\\.venv\\Scripts\\openstaad-mcp.exe",
      "args": ["--allowed-dirs", "D:\\GPT\\openstaad-mcp-PTC"]
    }
  }
}
```

STAAD.Pro 应已打开独立模型。服务保留原来的 stdio/HTTP、实例发现、认证及版本警告机制。
`--allowed-dirs` 控制 CSV/XLSX 读写范围；也可使用客户端提供的 MCP roots。

## 调用顺序

1. `discover_ptc()`：读取全部接口及严格参数 schema；也可按 `namespace` 查询。
2. `list_instances()`：确定模型。多个实例运行时，必须显式传入别名。
3. `execute_ptc(code=..., instance="staadPro1")`：运行一段同步 Python。

沙箱提供 `tools`、`input_data`、`math`、`json` 和原有允许的 Python 内置函数。
查询返回原生字典和列表，使用 `member["id"]`，不使用 `member.id`。
最终 `result = ...` 优先于最后一条表达式；两者都没有时结果为 `null`。
`stdout` 也会回传，因此不要打印中间的大数据集。

PTC 不注入 `staad`，只提供明确注册的查询方法。已有 `execute_code`、
`discover_api`、`read_skills`、`list_instances`、`get_status` 仍然可用。
建模、修改荷载、启动分析等操作继续通过原有 `execute_code` 使用。

## 查询接口

| 命名空间 | 方法 | 主要返回内容 |
| --- | --- | --- |
| geometry | `get_base_units()` | Metric/English，以及基础长度、力单位 |
| geometry | `get_node_count()`、`get_member_count()` | 节点或梁杆件数量 |
| geometry | `get_nodes(node_ids=None)` | id、x、y、z |
| geometry | `get_members(member_ids=None, up_axis="Y", tolerance=1e-6)` | 起终节点、坐标差、长度、是否水平 |
| properties | `get_member_properties(member_ids=None)` | 截面名、材料名、宽高、面积和惯性参数 |
| loads | `get_load_cases(include_combinations=True)` | 工况编号、标题、是否组合 |
| supports | `get_supports(node_ids=None)` | 支座节点、类型、释放和弹簧信息 |
| analysis | `are_results_available()` | 是否存在分析结果 |
| analysis | `get_units()` | 力、弯矩、位移、应力、尺寸、转角输出单位 |
| analysis | `get_member_forces(member_ids, load_cases, ends=None, coordinate_system="local")` | 杆端六分量内力；默认两个端点 |
| analysis | `get_node_displacements(node_ids, load_cases)` | 全局位移及转角 |
| analysis | `get_support_reactions(node_ids, load_cases)` | 全局支座反力及力矩 |
| design | `get_utilization(member_ids=None)` | 最后钢设计参数块的利用率及可用性 |

可省略的 ID 参数传入 `None` 表示全部，`[]` 表示不选择任何对象。
编号必须为正整数，不能是布尔值或字符串。重复 ID 在执行时去重。
实际方法参数及字段解释以 `discover_ptc` 返回的 schema、description 为准。

## 工程语义

- 基础单位：Metric 为 m、kN，English 为 in、kip。几何和截面参数使用基础单位；
  截面面积为长度平方，惯性矩及扭转常数为长度四次方。调用 `geometry.get_base_units()` 确认。
- 水平判断：默认以 Y 为竖向；`SET Z UP` 模型应传 `up_axis="Z"`。
  `tolerance` 是基础长度单位下的绝对容差；零长度杆件不视为水平杆。
- 杆端内力：`end=0` 为起端，`end=1` 为末端；`local`/`global` 映射底层参数 0/1。
  分量顺序为 FX、FY、FZ、MX、MY、MZ。不同端点的符号约定需按 STAAD 定义解释。
- 钢设计利用率来自 `GetMemberSteelDesignRatio`，对应该杆件最后一个钢设计参数块。
  它不是指定分析工况的应力比，也不是从杆端内力自行算得。
  负返回值（例如 -999、-1）保留在 `source_code`，同时返回 `ratio=null, available=false`。
  接口不根据某个固定阈值自动声明 PASS/FAIL，因为设计允许值可能不同。
- 查询分析/设计结果前检查结果是否存在；存在结果不代表结果已反映未保存的模型修改。
  由操作者确认模型保存、分析及设计状态。查询过程不会自动重新计算。

## 示例：水平杆件设计利用率筛选

将 [examples/ptc/critical_members.py](../examples/ptc/critical_members.py) 的代码作为
`execute_ptc` 的 `code` 参数。它先在本地筛选水平杆件，再读取设计利用率，
最终仅返回超过筛选阈值的杆件及缺少设计结果的杆件编号。
阈值 0.9 是筛选条件，不是对所有规范通用的失效判据。

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

[examples/ptc/member_forces.py](../examples/ptc/member_forces.py) 展示按工况读取内力，
代码不假定工况编号为 201，也不假定构件编号连续。

## 大结果导出与输入

`execute_ptc` 的 `input_data_path`、`output_data_path`、`overwrite` 与原工具一致。
CSV 输入是包含可选表头的行列表；XLSX 输入是按工作表名组织的
`{"columns": [...], "rows": [...]}` 字典。每次执行获得新副本。

导出 CSV 或单工作表 XLSX 时，令结果为行列表：

```python
rows = tools.geometry.get_members()
result = [["member_id", "length"]] + [[r["id"], r["length"]] for r in rows]
```

调用时指定 `output_data_path` 为允许目录下的 `.csv` 或 `.xlsx` 文件。
多工作表 XLSX 可令结果为 `{sheet_name: {"columns": [...], "rows": [...]}}`。
输出只回传文件摘要。已有文件默认拒绝覆盖，显式 `overwrite=True` 才替换。
输入与输出同一路径会拒绝执行。

## 架构与限制

```text
MCP execute_ptc
  → 共用请求处理（实例选择、受控文件输入）
  → connect_and_run 的 STA 线程
  → PTCRuntime + 原 Executor（AST 校验、执行锁、受限内置函数）
  → 不可变 ToolNamespace / ToolCallable
  → ToolRegistry（严格参数校验、调用预算）
  → OpenSTAADAdapter → COMProxy → Bentley openstaadpy → OpenSTAAD
  → 最终结果或受控文件导出摘要
```

参考 OpenStaadPython 的领域组织方式，底层继续使用项目已固定的 Bentley
`openstaadpy 26.0.0.62`，没有替换依赖或引入第二个 COM 连接模型。
内部不会重新通过 MCP 网络调用自己。

- 每次程序最多 1000 次工具调用，每个 ID 列表最多 10000 项，每次结果批量最多 100000 行。
  超限应缩小 ID/工况批次，不会悄悄丢弃数据。
- 最终内联结果 JSON 上限 65536 UTF-8 字节；超限返回错误并提示聚合或导出。
  文件导出沿用现有文件大小、行列及路径限制。原执行器仍会截断过长的单个字符串。
- 返回 `ptc.tool_calls` 和 `ptc.calls_by_tool` 统计，不包含中间数据。它们统计领域工具调用，
  不等于底层 COM 调用次数，也不是 token 节省的实测值。
- 不支持 async、跨调用缓存、持久化句柄。所有 COM 查询在一次请求的 STA 线程串行运行，
  两个执行入口共用原执行锁。
- 保留原连接层默认 120 秒等待超时。超时不能安全中止正在执行的 COM 调用；
  纯 Python 死循环也没有进程级强制隔离。若执行持续占用锁，应重启服务。
  该版本没有把原有 Python 沙箱升级为操作系统级隔离环境。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest -m "not integration" -q
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
```

可选覆盖率检查：安装 `pytest-cov` 后执行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ptc -m "not integration" --cov=openstaad_mcp.ptc --cov-branch --cov-report=term-missing
```

真实模型验收需要 STAAD.Pro 中打开独立、已保存的测试模型。指定完整路径以避免选错模型：

```powershell
$env:OPENSTAAD_PTC_TEST_MODEL = 'D:\models\ptc-test.std'
.\.venv\Scripts\python.exe -m pytest tests/ptc/test_server.py -m integration -v
```

真实集成测试只读检查杆件计数与枚举一致，不修改模型。
本次开发环境检查未发现运行中的 STAAD 实例，真实 COM 返回值与设计结果仍需在目标 STAAD 版本中验收。
Mock 测试通过不代表已完成真实结构模型验证。
