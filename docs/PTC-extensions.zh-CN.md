# OpenStaadPython 参考功能扩展

本次在原 14 个 PTC 查询上新增 17 个接口，共 31 个。
参考源是 [OpenStaad/OpenStaadPython](https://github.com/OpenStaad/OpenStaadPython/tree/46109adf794071ec5f1aa83f9ad33e8c33c3574a)，
固定核对提交 `46109adf794071ec5f1aa83f9ad33e8c33c3574a` 的 `openstaad/ops`。
PTC 实现独立编写，没有复制该仓库的实现代码；底层仍为项目已安装的 Bentley `openstaadpy 26.0.0.62`。

## 方法映射

所有方法通过 `execute_ptc` 中的 `tools.*` 使用。`discover_ptc(namespace=...)` 返回完整参数 schema 和字段说明。

| PTC 方法 | 对应 OpenSTAAD/OpenStaadPython 方法 | 返回内容 |
| --- | --- | --- |
| `geometry.get_plates(plate_ids=None)` | `GetPlateList`、`GetPlateIncidence` | 板编号、有序节点、节点数 |
| `geometry.get_solids(solid_ids=None)` | `GetSolidList`、`GetSolidIncidence` | 实体编号和 A 到 H 八个节点槽 |
| `geometry.get_groups(entity_type="members")` | `GetGroupNames`、`GetGroupEntities` | 组名、类型、实体编号 |
| `geometry.get_connected_members(node_ids)` | `GetBeamsConnectedAtNode` | 节点及其连接杆件 |
| `properties.get_member_properties_full(member_ids=None)` | `GetBeamPropertyAll`、`GetBeamSectionName`、`GetBeamMaterialName` | 原八项参数加翼缘厚度和腹板厚度 |
| `properties.get_plate_properties(plate_ids=None)` | `GetPlateThickness`、`GetPlateMaterialName`、`GetPlateIncidence` | 板材料及角点节点—厚度对应关系 |
| `properties.get_material_properties(material_names)` | `GetMaterialProperty` | 弹性模量、泊松比、密度、热膨胀系数、阻尼比 |
| `properties.get_member_releases(member_ids, ends=None)` | `GetMemberReleaseSpecEx` | 释放码、弹簧常数、统一及分方向部分弯矩释放系数 |
| `loads.get_combinations(combination_ids=None)` | `GetLoadCombinationCaseNumbers`、`GetLoadAndFactorForCombination` | 组合条目及系数、额外尾部系数 |
| `loads.get_reference_load_cases()` | `GetReferenceLoadCaseNumbers`、`GetReferenceLoadCaseTitle`、`GetReferenceLoadType` | 参考荷载编号、标题和类型 |
| `analysis.get_member_forces_at_distance(member_ids, load_cases, distances)` | `GetIntermediateMemberForcesAtDistance` | 各位置局部六分量内力 |
| `analysis.get_member_force_extrema(member_ids, load_cases, components=None)` | `GetMinMaxAxialForce`、`GetMinMaxShearForce`、`GetMinMaxBendingMoment` | 每杆件、工况、分量的有符号最小/最大值及位置 |
| `analysis.get_max_section_displacements(member_ids, load_cases, directions=None)` | `GetMaxSectionDisplacement` | 全局方向最大截面位移及位置 |
| `analysis.get_plate_center_results(plate_ids, load_cases)` | `GetAllPlateCenterStressesAndMoments` | SQX、SQY、MX、MY、MXY、SX、SY、SXY |
| `analysis.get_plate_principal_stresses(plate_ids, load_cases)` | `GetPlateCenterNormalPrincipalStresses` | 板中心上下表面最大/最小面内主应力 |
| `analysis.get_plate_von_mises_stresses(plate_ids, load_cases)` | `GetPlateCenterVonMisesStresses` | 板中心上下表面等效应力 |
| `design.get_member_results(member_ids=None)` | `GetMemberSteelDesignResults` | 规范、状态、利用率、允许值、控制工况/位置/条文/截面、设计力和长细比 |

## 需要保留的工程含义

**几何与属性**：三角板的第四节点为零时，从有效角点中去掉该槽，厚度也与前三个角点对应。
实体保留全部八个槽位，包括重复节点和零占位，不自行推断实体类型。
混合 `geometry` 组可能含杆、板、实体，不能把组内编号全部作为杆件编号传给分析接口。
分组类型支持 `nodes`、`members`、`plates`、`solids`、`geometry`、`floor`。

完整杆件属性使用具有固定字段顺序的十项 `GetBeamPropertyAll`：
`width, depth, AX, AY, AZ, IZ, IY, IX, flange_thickness, web_thickness`。
类型相关的 24 槽截面参数尚未映射，不能套用这十项字段顺序。
几何、截面和材料值沿用基础单位；材料密度是 STAAD 原生材料密度，不自动转换成质量密度。
热膨胀参数沿用模型温度约定。材料名区分大小写。

**杆端释放**：底层 docstring 的部分名称与实现不一致，已按实现的 COM 出参核对。
`release_codes` 和 `spring_constants` 均按局部 FX、FY、FZ、MX、MY、MZ 排列；
`mp_factor` 是一个数，`mp_factors` 是 MX、MY、MZ 三个方向的系数。
释放码：0 为未释放/无弹簧，1 为释放，-1 为弹簧，-3 为 MP，-2 为 MPX/MPY/MPZ。
不存在可读取释放规格时底层可能报错，PTC 不会自动填零假定为刚接。

**组合与参考荷载**：`terms` 保留工况编号、系数及顺序，不递归展开组合。
Bentley 包为组合系数数组额外分配一个槽；`trailing_factor` 保留该槽值，SRSS 中可能是总乘数。
仅凭有这个槽无法判断组合是否为 SRSS，也不能把它当作额外工况系数。
没有额外槽时返回 `null`。参考荷载是定义，不应直接当作已分析工况读取结果。
上述查询不切换 STAAD 当前活动荷载。

**内力与位移**：`distances` 是从起节点沿杆量取的基础长度距离，必须适用于所有选定杆件。
PTC 先检查全部杆长，再读取沿程内力；超出任何杆长就拒绝该批次。
沿程内力是局部坐标，最大截面位移是全局 X/Y/Z。
极值接口支持 FX、FY、FZ、MY、MZ，默认全部五项；该底层极值 API 不支持 MX。
返回值保留符号和控制位置，程序可继续聚合跨工况包络。
力、弯矩和位移值保留原 API 输出单位，不进行单位换算；位置沿杆从起点量取。
实际目标 STAAD 版本的位置单位和符号仍应通过已知模型核验。

**板应力**：板中心 MX、MY、MXY 是单位宽度弯矩，不能作为杆端弯矩使用；其余所列分量是应力。
主应力与等效应力明确区分局部上、下表面，不混合两面的控制值。

**设计结果**：返回最后一个实际设计该杆件的参数块结果，不接受“指定分析工况”过滤。
位置与设计力 FX、MY、MZ 使用基础单位。原样保留 STAAD 的状态和允许利用率，
不会因为利用率大于 1 就覆写真实状态；允许值可能不等于 1。
对未设计的构件，建议先调用 `get_utilization` 筛选 `available`，再查询详细结果。
详细结果查询中遇到缺少结果、负利用率或底层错误，会让整次调用失败，不返回貌似完整的部分清单。
多设计参数块专用接口本轮未接入。

## 示例

- [member_envelope.py](../examples/ptc/member_envelope.py)：跨工况局部 MY 包络，保留符号、工况和位置。
- [plate_report.py](../examples/ptc/plate_report.py)：板中心等效应力表，可通过 CSV/XLSX 导出。
- [design_details.py](../examples/ptc/design_details.py)：按真实设计状态筛选，并列出缺少结果的杆件。

这些代码用作 `execute_ptc.code`，不能当作普通 Python 文件直接启动；启动与客户端配置见
[PTC 使用说明](PTC.zh-CN.md)。示例不会自动启动分析或修改模型。

## 兼容性与验证

原 14 个接口保留原名称、参数和返回结构。原 `adapter.py` 现在负责显式注册，
各领域实现在 `geometry.py`、`properties.py`、`loads.py`、`supports.py`、`analysis.py`、`design.py`；
共同校验与 COM 调用封装位于 `base.py`。仍经过原有工具代理、AST 校验和 STA 线程。
新接口未扩大到任意 COM 方法调用。

ID 列表、批次数量、内联大小及文件边界沿用 PTC v1 限制；沿程距离列表最多 1000 项。
数值输出校验拒绝 NaN、Infinity、错误长度及非数值内容。
分组成员、节点连接关系、组合条目的累计数量也受批量行数预算约束。

测试覆盖三角/四边板、实体占位、分组类型、材料/截面顺序、释放码与部分释放系数、
组合额外因子、结果坐标方向、符号和位置、缺失结果、非法输入及原有接口回归。
本轮新增能力的真实 COM/工程模型验证需要运行中的独立 STAAD 模型；
自动化 Mock 测试不能替代该项验收。
