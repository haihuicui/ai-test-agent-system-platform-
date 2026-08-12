# 盲标工作表（不含裁判分数——打完标签前不要跑 run_judges）
## 判定规则（与两个 G-Eval 裁判一一对应）

### assertability_pass —— 预期结果可断言性（对应裁判阈值 0.8）

逐条看预期结果（expected_result 或 steps 里的 result）：

- 可客观断言 = 含具体数值 / 状态码 / 确切文案 / 明确的页面元素或状态变化
- 出现 ≥2 处模糊词（「正确」「成功」「正常」「合理」「显示无误」「符合预期」
  这类无法客观判定 Pass/Fail 的措辞）→ 判 0
- 预期结果与步骤因果断裂（步骤没操作却断言了结果）≥1 处 → 判 0
- 偶发 1 处模糊、其余全部可断言 → 可判 1（0.8 阈值容忍每处 -0.15 约 1 处）

### coverage_pass —— 异常与安全覆盖（对应裁判阈值 0.7）

- 异常流用例（空值/非法格式/超长/Unicode/emoji/重复提交/并发）< 2 条 → 判 0
- 功能涉及用户输入但完全无安全用例（SQL 注入/XSS/越权/未授权）→ 判 0
  （纯查询类、无输入面的功能缺失安全用例不扣）
- 有明确取值范围的字段完全没碰边界（min/max 附近一个都没有）→ 判 0
- 全是 Happy Path → 坚决判 0

### 填法（两种，可混用）

- **一体式（推荐）**：在下面每条样本末尾的「> 判定」行直接填
  （`assertability=_ coverage=_ note=`，把 _ 改成 0/1），全部填完跑
  `./.venv/Scripts/python.exe -m tests.eval.collect_labels` 自动回收进 jsonl；
- **答题卡**：直接填 human_labels_v1.jsonl 里的 null（适合习惯逐行填的）。
- 1 = 通过（裁判应该给过线分）；0 = 不通过；_ / null = 未标注
- note 可空；判 0 时建议写一句锚点（如「TC-03 预期结果是'显示正常'」），
  分歧分析时要靠它定位
- ⚠️ md 里已填判定后，重跑 make_blind_labels 会覆盖——必须先 collect_labels 回收

---

# 样本正文

## 1. ws-test_cases_module_04

- 来源：`workspace/testcase/PR-2/test_cases_module_04.jsonl`　分组：(旧样本)　用例数：3

```json
[
 {
  "name": "内部人员在采样小程序中可选所有地点",
  "case_number": "TC-PR2-MP-001",
  "module": "权限-小程序",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "使用内部人员账号登录采样小程序；系统中存在采样点/检测实验室/内部部门三类地点数据",
  "remarks": "REQ-变更④ / FP-014 / RAG·TC-PERM-008",
  "test_data": {
   "账号类型": "内部人员",
   "操作": "采样小程序采样点选择"
  },
  "test_case_steps": [
   {
    "step": "使用内部人员账号登录采样小程序",
    "result": "登录成功，进入采样页面"
   },
   {
    "step": "点击采样点的选择框",
    "result": "采样点选择列表显示所有地点（含采样点、检测实验室、内部部门类型）；所有地点均可被选中"
   }
  ]
 },
 {
  "name": "外部人员在采样小程序中仅可选绑定的项目采样点",
  "case_number": "TC-PR2-MP-002",
  "module": "权限-小程序",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "外部人员账号绑定项目A，项目A关联采样点SP01、SP02；系统中存在其他采样点（如SP99）",
  "remarks": "REQ-变更④ / FP-015 / RAG·TC-PERM-007",
  "test_data": {
   "账号类型": "外部人员",
   "绑定项目": "项目A(采样点SP01、SP02)",
   "预期可见": [
    "SP01",
    "SP02"
   ],
   "预期不可见": [
    "其他采样点SP99"
   ]
  },
  "test_case_steps": [
   {
    "step": "使用外部人员账号登录采样小程序",
    "result": "登录成功，进入采样页面"
   },
   {
    "step": "点击采样点的选择框",
    "result": "采样点选择列表仅显示项目A绑定的采样点（SP01、SP02）；其他采样点（如SP99）不可见"
   }
  ]
 },
 {
  "name": "外部人员在采样小程序中越权选择非绑定采样点被拦截",
  "case_number": "TC-PR2-MP-003",
  "module": "权限-小程序",
  "case_type": "security",
  "priority": "critical",
  "preconditions": "外部人员账号绑定项目A；系统中存在项目B采样点SP99",
  "remarks": "用例质量红线第6条（越权） / FP-015",
  "test_data": {
   "账号": "外部人员(绑定项目A)",
   "越权目标": "项目B采样点SP99",
   "攻击场景": "水平越权"
  },
  "test_case_steps": [
   {
    "step": "使用外部人员账号登录采样小程序",
    "result": "登录成功，进入采样页面"
   },
   {
    "step": "构造请求尝试选择/提交项目B的采样点SP99",
    "result": "服务端拒绝选择SP99，返回权限不足提示；前端采样点列表亦不可见SP99"
   }
  ]
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 2. ws-test_cases_module_03

- 来源：`workspace/testcase/PR-2/test_cases_module_03.jsonl`　分组：(旧样本)　用例数：3

```json
[
 {
  "name": "内部人员在物流管理中选择地点时可选所有地点",
  "case_number": "TC-PR2-LOG-001",
  "module": "权限-物流",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "使用内部人员账号登录系统；系统中存在采样点/检测实验室/内部部门三类地点数据",
  "remarks": "REQ-变更③ / FP-012 / RAG·TC-PERM-005",
  "test_data": {
   "账号类型": "内部人员",
   "地点类型": [
    "采样点",
    "检测实验室",
    "内部部门"
   ],
   "操作": "物流单地点选择"
  },
  "test_case_steps": [
   {
    "step": "使用内部人员账号登录，进入「物流管理」模块新增物流单",
    "result": "物流单创建页面正常打开"
   },
   {
    "step": "点击寄出地点/签收地点的选择框",
    "result": "地点选择列表包含所有类型的地点（采样点、检测实验室、内部部门）；所有地点均可被选中"
   }
  ]
 },
 {
  "name": "外部人员在物流管理中仅可选检测实验室和绑定项目采样点",
  "case_number": "TC-PR2-LOG-002",
  "module": "权限-物流",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "使用外部人员账号登录；该账号绑定项目A，项目A关联采样点SP01、SP02；系统中另有其他采样点（如SP99）和内部部门类型地点",
  "remarks": "REQ-变更③ / FP-013 / RAG·TC-PERM-006",
  "test_data": {
   "账号类型": "外部人员",
   "绑定项目": "项目A(绑定采样点SP01、SP02)",
   "预期可见": [
    "全部检测实验室",
    "SP01",
    "SP02"
   ],
   "预期不可见": [
    "其他采样点SP99",
    "内部部门"
   ]
  },
  "test_case_steps": [
   {
    "step": "使用外部人员账号登录，进入「物流管理」模块新增物流单",
    "result": "物流单创建页面正常打开"
   },
   {
    "step": "点击寄出地点/签收地点的选择框",
    "result": "地点选择列表仅包含：全部检测实验室类型地点+项目A绑定的采样点（SP01、SP02）；其他采样点（如SP99）与内部部门地点不可见或不可选"
   }
  ]
 },
 {
  "name": "外部人员在物流管理中越权访问其他项目采样点被拦截",
  "case_number": "TC-PR2-LOG-003",
  "module": "权限-物流",
  "case_type": "security",
  "priority": "critical",
  "preconditions": "外部人员账号绑定项目A；系统中存在项目B及其采样点SP99",
  "remarks": "用例质量红线第6条（越权） / FP-013",
  "test_data": {
   "账号": "外部人员(绑定项目A)",
   "越权目标": "项目B采样点SP99",
   "攻击场景": "水平越权"
  },
  "test_case_steps": [
   {
    "step": "使用外部人员账号登录，进入「物流管理」模块",
    "result": "正常进入物流管理页面"
   },
   {
    "step": "构造接口请求，尝试在物流单中选择/提交项目B的采样点SP99",
    "result": "服务端拒绝选择SP99，返回权限不足错误（403/业务码拒绝）；前端地点选择列表亦不可见SP99"
   }
  ]
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 3. ws-sorted_cases

- 来源：`workspace/testcase/sorted_cases.jsonl`　分组：(旧样本)　用例数：25

```json
[
 {
  "id": "TC-S52-QC-001",
  "title": "质控任务列表仅展示BS设备相关任务",
  "module": "质控任务列表",
  "type": "功能测试",
  "priority": "P0",
  "preconditions": "系统中有BS设备、直吹设备、GC-MS设备创建的质控任务",
  "steps": "1. 进入质控任务列表 2. 查看列表中的任务",
  "test_data": "BS设备任务3条、直吹设备任务2条、GC-MS设备任务2条",
  "expected_results": "列表中仅展示BS设备相关的质控任务，直吹和GC-MS设备的任务不显示",
  "remarks": "REQ-QC-01"
 },
 {
  "id": "TC-S52-QC-002",
  "title": "质控任务列表权限单独设置",
  "module": "质控任务列表",
  "type": "功能测试",
  "priority": "P0",
  "preconditions": "用户A有质控任务列表权限，用户B无权限",
  "steps": "1. 用户A登录，查看左侧菜单 2. 用户B登录，查看左侧菜单",
  "test_data": "用户A=管理员角色，用户B=无质控权限角色",
  "expected_results": "用户A可见质控任务列表菜单项并可访问；用户B不可见该菜单项",
  "remarks": "REQ-QC-01"
 },
 {
  "id": "TC-S52-QC-003",
  "title": "质控任务列表状态标签页完整展示",
  "module": "质控任务列表",
  "type": "功能测试",
  "priority": "P0",
  "preconditions": "系统中有各状态的质控任务",
  "steps": "1. 进入质控任务列表 2. 查看顶部标签页",
  "test_data": "各状态任务至少1条",
  "expected_results": "显示全部、待检测、检测中、分析中、检测完成、已取消6个标签页",
  "remarks": "REQ-QC-02"
 },
 {
  "id": "TC-S52-QC-004",
  "title": "各状态标签页筛选正确",
  "module": "质控任务列表",
  "type": "功能测试",
  "priority": "P0",
  "preconditions": "各状态任务各5条",
  "steps": "1. 点击待检测 2. 点击检测中 3. 点击分析中 4. 点击检测完成 5. 点击已取消",
  "test_data": "待检测5条、检测中5条、分析中5条、检测完成5条、已取消5条",
  "expected_results": "每个标签页仅展示对应状态的任务，数量正确",
  "remarks": "REQ-QC-02"
 },
 {
  "id": "TC-S52-QC-005",
  "title": "创建质控任务时选择客户/采样点/检测项目/TD管号",
  "module": "质控任务列表",
  "type": "功能测试",
  "priority": "P0",
  "preconditions": "有可用客户、采样点、检测项目、TD管数据",
  "steps": "1. 点击创建任务 2. 选择气体来源=标气 3. 选择客户 4. 选择采样点 5. 选择检测项目 6. 输入TD管号 7. 点击创建",
  "test_data": "客户=广州和睦家医院，采样点=广州和睦家采样点，检测项目=RES-BS-004，TD管号=351399",
  "expected_results": "任务创建成功，列表中显示所选客户、采样点、检测项目、TD管号",
  "remarks": "REQ-QC-03"
 },
 {
  "id": "TC-S52-QC-006",
  "title": "标气/本底任务自动生成标本编码",
  "module": "质控任务列表",
  "type": "功能测试",
  "priority": "P0",
  "preconditions": "系统时间2026/06/09",
  "steps": "1. 创建标气质控任务 2. 创建本地质控任务 3. 查看生成的标本编码",
  "test_data": "气体来源=标气、本底",
  "expected_results": "标本编码格式为QC+年月日+3位顺序号，如QC20260609001",
  "remarks": "REQ-QC-04"
 },
 {
  "id": "TC-S52-QC-007",
  "title": "环境任务标本编码由用户手动输入",
  "module": "质控任务列表",
  "type": "功能测试",
  "priority": "P0",
  "preconditions": "-",
  "steps": "1. 创建环境质控任务 2. 手动输入标本编码 3. 提交",
  "test_data": "标本编码=ENV20260609001",
  "expected_results": "环境任务标本编码使用用户输入值，不做格式校验，仅做重复校验",
  "remarks": "REQ-QC-04"
 },
 {
  "id": "TC-S52-QC-008",
  "title": "环境任务标本编码重复校验",
  "module": "质控任务列表",
  "type": "功能测试",
  "priority": "P0",
  "preconditions": "已存在标本编码=ENV20260609001的环境任务",
  "steps": "1. 创建环境任务 2. 输入已存在的标本编码ENV20260609001 3. 提交",
  "test_data": "重复标本编码=ENV20260609001",
  "expected_results": "提示标本编码重复，阻止创建",
  "remarks": "REQ-QC-04"
 },
 {
  "id": "TC-S52-QC-009",
  "title": "创建任务时气体来源可选标气/本底/环境",
  "module": "质控任务列表",
  "type": "功能测试",
  "priority": "P0",
  "preconditions": "-",
  "steps": "1. 点击创建任务 2. 查看气体来源下拉选项",
  "test_data": "-",
  "expected_results": "下拉选项包含标气、本底、环境三个选项",
  "remarks": "REQ-QC-05"
 },
 {
  "id": "TC-S52-QC-010",
  "title": "标气任务自动获取气体类型",
  "module": "质控任务列表",
  "type": "功能测试",
  "priority": "P0",
  "preconditions": "标气管理中存在标气ID=SGP2026061701008010，气体类型=SGI7A-2ppb",
  "steps": "1. 创建标气质控任务 2. 输入TD管号匹配标气 3. 查看气体类型字段",
  "test_data": "TD管号匹配标气ID=SGP2026061701008010",
  "expected_results": "气体类型自动填充为SGI7A-2ppb",
  "remarks": "REQ-QC-06"
 },
 {
  "id": "TC-S52-QC-011",
  "title": "本底/环境任务气体类型为空",
  "module": "质控任务列表",
  "type": "功能测试",
  "priority": "P0",
  "preconditions": "-",
  "steps": "1. 创建本底任务 2. 创建环境任务 3. 查看气体类型字段",
  "test_data": "气体来源=本底、环境",
  "expected_results": "本底和环境任务的气体类型字段为空",
  "remarks": "REQ-QC-06"
 },
 {
  "id": "TC-S52-QC-012",
  "title": "检测完成后设备信息正确展示",
  "module": "质控任务列表",
  "type": "功能测试",
  "priority": "P0",
  "preconditions": "质控任务已完成检测",
  "steps": "1. 查看已完成检测的质控任务详情",
  "test_data": "已完成检测的任务",
  "expected_results": "显示检测设备、检测模块、检测时间、检测结果上传时间",
  "remarks": "REQ-QC-07"
 },
 {
  "id": "TC-S52-QC-013",
  "title": "平台创建的任务来源显示平台",
  "module": "质控任务列表",
  "type": "功能测试",
  "priority": "P0",
  "preconditions": "-",
  "steps": "1. 在平台手动创建质控任务 2. 查看任务详情中的任务来源",
  "test_data": "-",
  "expected_results": "任务来源显示平台",
  "remarks": "REQ-QC-08"
 },
 {
  "id": "TC-S52-QC-014",
  "title": "设备创建的质控任务同步到检测中，来源显示设备",
  "module": "质控任务列表",
  "type": "功能测试",
  "priority": "P0",
  "preconditions": "上位机设备创建了质控任务",
  "steps": "1. 设备创建质控任务 2. 在质控任务列表中查看",
  "test_data": "设备上传的质控任务",
  "expected_results": "任务自动出现在检测中标签页，任务来源显示设备",
  "remarks": "REQ-QC-08"
 },
 {
  "id": "TC-S52-QC-015",
  "title": "环境任务有接收时间和样本质量字段",
  "module": "质控任务列表",
  "type": "功能测试",
  "priority": "P0",
  "preconditions": "-",
  "steps": "1. 创建环境质控任务 2. 查看任务详情",
  "test_data": "气体来源=环境",
  "expected_results": "环境任务显示接收时间和样本质量字段",
  "remarks": "REQ-QC-09"
 },
 {
  "id": "TC-S52-QC-016",
  "title": "标气/本底任务无接收时间和样本质量字段",
  "module": "质控任务列表",
  "type": "功能测试",
  "priority": "P0",
  "preconditions": "-",
  "steps": "1. 创建标气质控任务 2. 创建本地质控任务 3. 查看任务详情",
  "test_data": "气体来源=标气、本底",
  "expected_results": "标气和本底任务不显示接收时间和样本质量字段",
  "remarks": "REQ-QC-09"
 },
 {
  "id": "TC-S52-QC-017",
  "title": "质控任务到分析中状态自动创建老化任务",
  "module": "质控任务列表",
  "type": "功能测试",
  "priority": "P0",
  "preconditions": "质控任务处于检测中状态",
  "steps": "1. 质控任务进入分析中状态 2. 查看老化任务列表",
  "test_data": "质控任务TD管号=351399",
  "expected_results": "自动创建一条关联该TD管的老化任务",
  "remarks": "REQ-QC-10"
 },
 {
  "id": "TC-S52-QC-018",
  "title": "历史质控任务迁移到新列表",
  "module": "质控任务列表",
  "type": "功能测试",
  "priority": "P0",
  "preconditions": "系统中有历史质控任务数据",
  "steps": "1. 查看质控任务列表 2. 查看检测完成标签页",
  "test_data": "历史质控任务数据",
  "expected_results": "原人工分析中的历史任务出现在检测完成标签页中",
  "remarks": "REQ-QC-11"
 },
 {
  "id": "TC-S52-QC-019",
  "title": "批量取消质控任务",
  "module": "质控任务列表",
  "type": "功能测试",
  "priority": "P0",
  "preconditions": "有多条待检测状态的质控任务",
  "steps": "1. 勾选多条任务 2. 点击取消任务 3. 输入取消原因 4. 确认",
  "test_data": "选择2条待检测任务",
  "expected_results": "所选任务状态变为已取消",
  "remarks": "REQ-QC-12"
 },
 {
  "id": "TC-S52-QC-020",
  "title": "取消标气任务时提示联系管理员",
  "module": "质控任务列表",
  "type": "功能测试",
  "priority": "P0",
  "preconditions": "标气来源的质控任务",
  "steps": "1. 取消标气质控任务 2. 查看提示信息",
  "test_data": "气体来源=标气的任务",
  "expected_results": "提示取消任务后，请联系管理员手动更改标气状态",
  "remarks": "REQ-QC-12"
 },
 {
  "id": "TC-S52-QC-021",
  "title": "环境任务批量接收样本",
  "module": "质控任务列表",
  "type": "功能测试",
  "priority": "P0",
  "preconditions": "有待检测状态的环境质控任务",
  "steps": "1. 勾选环境任务 2. 点击接收样本 3. 填写样本质量 4. 确认",
  "test_data": "环境任务2条",
  "expected_results": "环境任务状态更新，接收时间记录",
  "remarks": "REQ-QC-13"
 },
 {
  "id": "TC-S52-QC-022",
  "title": "非环境任务不可批量接收样本",
  "module": "质控任务列表",
  "type": "功能测试",
  "priority": "P0",
  "preconditions": "标气/本底任务",
  "steps": "1. 勾选标气或本底任务 2. 查看批量操作按钮",
  "test_data": "标气任务、本底任务",
  "expected_results": "批量操作中无接收样本选项",
  "remarks": "REQ-QC-13"
 },
 {
  "id": "TC-S52-QC-023",
  "title": "平台可创建环境任务",
  "module": "质控任务列表",
  "type": "功能测试",
  "priority": "P0",
  "preconditions": "-",
  "steps": "1. 点击创建任务 2. 选择气体来源=环境 3. 填写必填字段 4. 点击创建",
  "test_data": "气体来源=环境",
  "expected_results": "环境任务创建成功",
  "remarks": "REQ-QC-14"
 },
 {
  "id": "TC-S52-QC-024",
  "title": "平台不可创建标气/本底任务",
  "module": "质控任务列表",
  "type": "功能测试",
  "priority": "P0",
  "preconditions": "-",
  "steps": "1. 点击创建任务 2. 查看气体来源选项",
  "test_data": "-",
  "expected_results": "气体来源仅可选环境，标气和本底不可选",
  "remarks": "REQ-QC-14"
 },
 {
  "id": "TC-S52-QC-025",
  "title": "保存并创建下一个时清空标本编码/TD管号/采样时间",
  "module": "质控任务列表",
  "type": "功能测试",
  "priority": "P0",
  "preconditions": "-",
  "steps": "1. 创建环境任务 2. 填写所有字段 3. 点击保存并创建下一个",
  "test_data": "客户=1，采样点=1，检测项目=1，标本编码=ENV001，TD管号=351399",
  "expected_results": "标本编码、TD管号、采样时间被清空，客户、采样点、检测项目等字段保留",
  "remarks": "REQ-QC-15"
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 4. ws-dms_test_cases

- 来源：`workspace/testcase/dms_test_cases.jsonl`　分组：(旧样本)　用例数：25

```json
[
 {
  "case_number": "TC-DMS-3.1-001",
  "name": "正常创建经销商披露申请-填写所有必填字段",
  "module": "3.1 新建经销商披露申请",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "用户已登录DMS系统，具有新建披露申请的权限",
  "test_case_steps": "1. 点击\"新建披露申请\"按钮\n2. 填写所有必填字段（经销商名称、统一社会信用代码、法定代表人、联系人、联系电话、邮箱等）\n3. 点击\"提交\"按钮",
  "test_data": "经销商名称：测试经销商A；统一社会信用代码：91110108MA01XXXXXX；法定代表人：张三；联系人：李四；联系电话：13800138000；邮箱：test@test.com",
  "remarks": "正向流程验证"
 },
 {
  "case_number": "TC-DMS-3.1-002",
  "name": "创建披露申请-必填字段为空校验",
  "module": "3.1 新建经销商披露申请",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "用户已登录DMS系统",
  "test_case_steps": "1. 点击\"新建披露申请\"按钮\n2. 不填写任何必填字段\n3. 点击\"提交\"按钮",
  "test_data": "所有字段为空",
  "remarks": "必填字段校验"
 },
 {
  "case_number": "TC-DMS-3.1-003",
  "name": "创建披露申请-经销商名称超长校验",
  "module": "3.1 新建经销商披露申请",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "用户已登录DMS系统",
  "test_case_steps": "1. 点击\"新建披露申请\"按钮\n2. 在经销商名称字段输入超过200个字符\n3. 点击\"提交\"按钮",
  "test_data": "经销商名称：超过200个字符的字符串",
  "remarks": "字段长度限制校验"
 },
 {
  "case_number": "TC-DMS-3.1-004",
  "name": "创建披露申请-统一社会信用代码格式校验",
  "module": "3.1 新建经销商披露申请",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "用户已登录DMS系统",
  "test_case_steps": "1. 点击\"新建披露申请\"按钮\n2. 输入格式错误的统一社会信用代码（不足18位/包含非法字符）\n3. 点击\"提交\"按钮",
  "test_data": "统一社会信用代码：12345678901234567（17位）",
  "remarks": "格式校验"
 },
 {
  "case_number": "TC-DMS-3.1-005",
  "name": "创建披露申请-联系电话格式校验",
  "module": "3.1 新建经销商披露申请",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "用户已登录DMS系统",
  "test_case_steps": "1. 点击\"新建披露申请\"按钮\n2. 输入格式错误的联系电话\n3. 点击\"提交\"按钮",
  "test_data": "联系电话：12345（位数不足）",
  "remarks": "格式校验"
 },
 {
  "case_number": "TC-DMS-3.1-006",
  "name": "创建披露申请-邮箱格式校验",
  "module": "3.1 新建经销商披露申请",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "用户已登录DMS系统",
  "test_case_steps": "1. 点击\"新建披露申请\"按钮\n2. 输入格式错误的邮箱地址\n3. 点击\"提交\"按钮",
  "test_data": "邮箱：test@invalid",
  "remarks": "邮箱格式校验"
 },
 {
  "case_number": "TC-DMS-3.1-007",
  "name": "创建披露申请-填写所有字段（含选填字段）",
  "module": "3.1 新建经销商披露申请",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "用户已登录DMS系统",
  "test_case_steps": "1. 点击\"新建披露申请\"按钮\n2. 填写所有必填字段和选填字段（备注、经营范围、注册资本等）\n3. 点击\"提交\"按钮",
  "test_data": "填写完整的经销商信息",
  "remarks": "全字段填写验证"
 },
 {
  "case_number": "TC-DMS-3.1-008",
  "name": "创建披露申请-取消操作",
  "module": "3.1 新建经销商披露申请",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "用户已登录DMS系统",
  "test_case_steps": "1. 点击\"新建披露申请\"按钮\n2. 填写部分信息\n3. 点击\"取消\"按钮",
  "test_data": "部分填写的信息",
  "remarks": "取消操作验证"
 },
 {
  "case_number": "TC-DMS-3.1-009",
  "name": "创建披露申请-重复提交校验",
  "module": "3.1 新建经销商披露申请",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "用户已登录DMS系统，已成功提交过一次申请",
  "test_case_steps": "1. 使用相同的经销商信息再次创建披露申请\n2. 点击\"提交\"按钮",
  "test_data": "与已提交申请相同的经销商信息",
  "remarks": "重复提交校验"
 },
 {
  "case_number": "TC-DMS-3.1-010",
  "name": "创建披露申请-特殊字符输入校验",
  "module": "3.1 新建经销商披露申请",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "用户已登录DMS系统",
  "test_case_steps": "1. 点击\"新建披露申请\"按钮\n2. 在各字段输入特殊字符（<script>、SQL注入语句等）\n3. 点击\"提交\"按钮",
  "test_data": "各字段包含特殊字符和XSS/SQL注入脚本",
  "remarks": "安全校验"
 },
 {
  "case_number": "TC-DMS-3.1-011",
  "name": "创建披露申请-页面加载验证",
  "module": "3.1 新建经销商披露申请",
  "case_type": "functional",
  "priority": "low",
  "preconditions": "用户已登录DMS系统",
  "test_case_steps": "1. 点击\"新建披露申请\"按钮\n2. 观察页面加载情况",
  "test_data": "无",
  "remarks": "页面加载验证"
 },
 {
  "case_number": "TC-DMS-3.1-012",
  "name": "创建披露申请-字段默认值验证",
  "module": "3.1 新建经销商披露申请",
  "case_type": "functional",
  "priority": "low",
  "preconditions": "用户已登录DMS系统",
  "test_case_steps": "1. 点击\"新建披露申请\"按钮\n2. 检查各字段的默认值",
  "test_data": "无",
  "remarks": "默认值验证"
 },
 {
  "case_number": "TC-DMS-3.1-013",
  "name": "创建披露申请-保存草稿功能",
  "module": "3.1 新建经销商披露申请",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "用户已登录DMS系统",
  "test_case_steps": "1. 点击\"新建披露申请\"按钮\n2. 填写部分信息\n3. 点击\"保存草稿\"按钮\n4. 在草稿箱中找到该申请",
  "test_data": "部分填写的经销商信息",
  "remarks": "草稿保存功能验证"
 },
 {
  "case_number": "TC-DMS-3.1-014",
  "name": "创建披露申请-从草稿继续编辑",
  "module": "3.1 新建经销商披露申请",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "用户已登录DMS系统，存在草稿记录",
  "test_case_steps": "1. 进入草稿列表\n2. 点击草稿记录进入编辑\n3. 补充完整信息后提交",
  "test_data": "草稿中的经销商信息",
  "remarks": "草稿编辑功能验证"
 },
 {
  "case_number": "TC-DMS-3.1-015",
  "name": "创建披露申请-无权限用户操作",
  "module": "3.1 新建经销商披露申请",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "用户已登录DMS系统，但无新建披露申请的权限",
  "test_case_steps": "1. 检查页面是否显示\"新建披露申请\"按钮\n2. 尝试直接访问新建页面URL",
  "test_data": "无",
  "remarks": "权限控制验证"
 },
 {
  "case_number": "TC-DMS-3.1-016",
  "name": "创建披露申请-页面响应时间验证",
  "module": "3.1 新建经销商披露申请",
  "case_type": "performance",
  "priority": "medium",
  "preconditions": "用户已登录DMS系统",
  "test_case_steps": "1. 点击\"新建披露申请\"按钮\n2. 记录页面加载完成时间",
  "test_data": "无",
  "remarks": "性能验证，页面加载应在3秒内"
 },
 {
  "case_number": "TC-DMS-3.1-017",
  "name": "创建披露申请-提交响应时间验证",
  "module": "3.1 新建经销商披露申请",
  "case_type": "performance",
  "priority": "medium",
  "preconditions": "用户已登录DMS系统",
  "test_case_steps": "1. 填写完整的披露申请信息\n2. 点击\"提交\"按钮\n3. 记录提交到返回结果的时间",
  "test_data": "完整的经销商信息",
  "remarks": "性能验证，提交响应应在5秒内"
 },
 {
  "case_number": "TC-DMS-3.1-018",
  "name": "创建披露申请-浏览器兼容性验证（Chrome）",
  "module": "3.1 新建经销商披露申请",
  "case_type": "compatibility",
  "priority": "medium",
  "preconditions": "使用Chrome浏览器登录DMS系统",
  "test_case_steps": "1. 在Chrome浏览器中创建披露申请\n2. 验证所有功能正常",
  "test_data": "完整的经销商信息",
  "remarks": "Chrome浏览器兼容性验证"
 },
 {
  "case_number": "TC-DMS-3.1-019",
  "name": "创建披露申请-浏览器兼容性验证（Firefox）",
  "module": "3.1 新建经销商披露申请",
  "case_type": "compatibility",
  "priority": "medium",
  "preconditions": "使用Firefox浏览器登录DMS系统",
  "test_case_steps": "1. 在Firefox浏览器中创建披露申请\n2. 验证所有功能正常",
  "test_data": "完整的经销商信息",
  "remarks": "Firefox浏览器兼容性验证"
 },
 {
  "case_number": "TC-DMS-3.1-020",
  "name": "创建披露申请-浏览器兼容性验证（Edge）",
  "module": "3.1 新建经销商披露申请",
  "case_type": "compatibility",
  "priority": "medium",
  "preconditions": "使用Edge浏览器登录DMS系统",
  "test_case_steps": "1. 在Edge浏览器中创建披露申请\n2. 验证所有功能正常",
  "test_data": "完整的经销商信息",
  "remarks": "Edge浏览器兼容性验证"
 },
 {
  "case_number": "TC-DMS-3.1-021",
  "name": "创建披露申请-移动端适配验证",
  "module": "3.1 新建经销商披露申请",
  "case_type": "compatibility",
  "priority": "low",
  "preconditions": "使用移动设备登录DMS系统",
  "test_case_steps": "1. 在移动设备上打开新建披露申请页面\n2. 验证页面布局和功能",
  "test_data": "无",
  "remarks": "移动端适配验证"
 },
 {
  "case_number": "TC-DMS-3.1-022",
  "name": "创建披露申请-法人代表字段校验",
  "module": "3.1 新建经销商披露申请",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "用户已登录DMS系统",
  "test_case_steps": "1. 点击\"新建披露申请\"按钮\n2. 法人代表字段输入数字和特殊字符\n3. 点击\"提交\"按钮",
  "test_data": "法人代表：123!@#",
  "remarks": "法人代表字段格式校验"
 },
 {
  "case_number": "TC-DMS-3.1-023",
  "name": "创建披露申请-联系人字段校验",
  "module": "3.1 新建经销商披露申请",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "用户已登录DMS系统",
  "test_case_steps": "1. 点击\"新建披露申请\"按钮\n2. 联系人字段输入超长字符\n3. 点击\"提交\"按钮",
  "test_data": "联系人：超过50个字符的字符串",
  "remarks": "联系人字段长度校验"
 },
 {
  "case_number": "TC-DMS-3.1-024",
  "name": "创建披露申请-经营范围字段校验",
  "module": "3.1 新建经销商披露申请",
  "case_type": "functional",
  "priority": "low",
  "preconditions": "用户已登录DMS系统",
  "test_case_steps": "1. 点击\"新建披露申请\"按钮\n2. 经营范围字段输入超长文本\n3. 点击\"提交\"按钮",
  "test_data": "经营范围：超过500个字符的文本",
  "remarks": "经营范围字段长度校验"
 },
 {
  "case_number": "TC-DMS-3.1-025",
  "name": "创建披露申请-注册资本字段校验",
  "module": "3.1 新建经销商披露申请",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "用户已登录DMS系统",
  "test_case_steps": "1. 点击\"新建披露申请\"按钮\n2. 注册资本字段输入负数和非数字字符\n3. 点击\"提交\"按钮",
  "test_data": "注册资本：-100 / ABC",
  "remarks": "注册资本字段格式校验"
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 5. ws-tc_sysconfig_module_v2

- 来源：`workspace/testcase/tc_sysconfig_module_v2.jsonl`　分组：(旧样本)　用例数：25

```json
[
 {
  "case_number": "TC-PR-SCFG-001",
  "name": "端口连接-选择有效端口连接成功",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "标气制备软件已启动，端口号下拉列表已加载",
  "test_data": {
   "port": "COM1"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "显示端口号下拉列表，默认显示\"1\""
   },
   {
    "step": "2. 从下拉列表中选择\"COM1\"",
    "result": "下拉列表收起，端口号显示为\"COM1\""
   },
   {
    "step": "3. 点击\"连接\"按钮",
    "result": "连接成功，按钮文字变为\"断开\"，连接状态指示灯变为绿色"
   }
  ],
  "remarks": "关联需求 FP-001"
 },
 {
  "case_number": "TC-PR-SCFG-002",
  "name": "端口连接-无效端口连接失败",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "标气制备软件已启动，目标端口COM99不存在或未连接硬件",
  "test_data": {
   "port": "COM99"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "显示端口号下拉列表"
   },
   {
    "step": "2. 从下拉列表中选择\"COM99\"",
    "result": "端口号显示为\"COM99\""
   },
   {
    "step": "3. 点击\"连接\"按钮",
    "result": "连接失败，弹出错误提示\"端口连接失败，请检查端口状态\"，按钮仍为\"连接\""
   }
  ],
  "remarks": "关联需求 FP-001"
 },
 {
  "case_number": "TC-PR-SCFG-003",
  "name": "端口连接-端口被占用时提示",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "目标端口COM1已被其他程序占用",
  "test_data": {
   "port": "COM1"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "页面正常加载，端口号默认显示\"1\""
   },
   {
    "step": "2. 从下拉列表中选择\"COM1\"",
    "result": "端口号显示为\"COM1\""
   },
   {
    "step": "3. 点击\"连接\"按钮",
    "result": "连接失败，弹出提示\"端口COM1已被占用，请选择其他端口\"，按钮保持\"连接\""
   }
  ],
  "remarks": "关联需求 FP-001"
 },
 {
  "case_number": "TC-PR-SCFG-004",
  "name": "端口连接-已连接状态下断开连接",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "端口COM1已成功连接，按钮显示为\"断开\"",
  "test_data": {
   "port": "COM1"
  },
  "test_case_steps": [
   {
    "step": "1. 确认当前端口已连接，按钮显示\"断开\"",
    "result": "页面显示\"断开\"按钮，连接状态指示灯为绿色"
   },
   {
    "step": "2. 点击\"断开\"按钮",
    "result": "连接断开，按钮文字恢复为\"连接\"，连接状态指示灯变为灰色"
   }
  ],
  "remarks": "关联需求 FP-001"
 },
 {
  "case_number": "TC-PR-SCFG-005",
  "name": "端口连接-断开后重新连接",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "端口COM1之前已连接后断开",
  "test_data": {
   "port": "COM1"
  },
  "test_case_steps": [
   {
    "step": "1. 确认当前端口处于断开状态",
    "result": "按钮显示\"连接\"，连接状态指示灯为灰色"
   },
   {
    "step": "2. 再次选择\"COM1\"并点击\"连接\"",
    "result": "连接成功，按钮变为\"断开\"，连接状态指示灯变绿"
   }
  ],
  "remarks": "关联需求 FP-001"
 },
 {
  "case_number": "TC-PR-SCFG-006",
  "name": "端口连接-下拉列表展示可选端口",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "expected_ports": "COM1,COM2,COM3,COM4,COM5,COM6,COM7,COM8,COM9,COM10"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "页面正常加载"
   },
   {
    "step": "2. 点击端口号下拉列表展开",
    "result": "下拉列表展示可选端口，至少包含COM1~COM10共10个选项；默认选中\"1\""
   }
  ],
  "remarks": "关联需求 FP-001"
 },
 {
  "case_number": "TC-PR-SCFG-007",
  "name": "配气稳定时间-有效值输入",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "标气制备软件已启动，端口已连接",
  "test_data": {
   "gas_stabilization_time": "30.50"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "页面正常加载，配气稳定时间输入框为空"
   },
   {
    "step": "2. 在\"配气稳定时间\"输入框中输入\"30.50\"",
    "result": "输入框显示\"30.50\""
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存成功，页面顶部显示\"保存成功\"提示；重新打开页面该字段显示\"30.50\""
   }
  ],
  "remarks": "关联需求 FP-002"
 },
 {
  "case_number": "TC-PR-SCFG-008",
  "name": "配气稳定时间-下边界值(0.00)",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "gas_stabilization_time": "0.00"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "页面正常加载"
   },
   {
    "step": "2. 在\"配气稳定时间\"输入框中输入\"0.00\"",
    "result": "输入框显示\"0.00\""
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "如果0为允许值则保存成功，无错误提示；如果0为不允许值则字段旁提示\"配气稳定时间必须大于0\""
   }
  ],
  "remarks": "关联需求 FP-002，边界值测试"
 },
 {
  "case_number": "TC-PR-SCFG-009",
  "name": "配气稳定时间-上边界值(9999.99)",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "gas_stabilization_time": "9999.99"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "页面正常加载"
   },
   {
    "step": "2. 在\"配气稳定时间\"输入框中输入\"9999.99\"",
    "result": "输入框显示\"9999.99\""
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存成功（若9999.99在范围内），无错误提示"
   }
  ],
  "remarks": "关联需求 FP-002，边界值测试"
 },
 {
  "case_number": "TC-PR-SCFG-010",
  "name": "配气稳定时间-上边界+1溢出值(10000.00)拒绝",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "gas_stabilization_time": "10000.00"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "页面正常加载"
   },
   {
    "step": "2. 在\"配气稳定时间\"输入框中输入\"10000.00\"",
    "result": "输入框显示\"10000.00\""
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存失败，\"配气稳定时间\"字段红色高亮并提示\"数值超出允许范围(0~9999.99)\""
   }
  ],
  "remarks": "关联需求 FP-002，边界值测试"
 },
 {
  "case_number": "TC-PR-SCFG-011",
  "name": "配气稳定时间-负值(-1.00)拒绝",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "gas_stabilization_time": "-1.00"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "页面正常加载"
   },
   {
    "step": "2. 在\"配气稳定时间\"输入框中输入\"-1.00\"",
    "result": "输入框显示\"-1.00\""
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存失败，\"配气稳定时间\"字段红色高亮并提示\"请输入非负数值\""
   }
  ],
  "remarks": "关联需求 FP-002，异常输入测试"
 },
 {
  "case_number": "TC-PR-SCFG-012",
  "name": "配气稳定时间-非数字输入拒绝",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "gas_stabilization_time": "abc"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "页面正常加载"
   },
   {
    "step": "2. 在\"配气稳定时间\"输入框中输入\"abc\"",
    "result": "输入框显示\"abc\""
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存失败，\"配气稳定时间\"字段红色高亮并提示\"请输入有效数字\""
   }
  ],
  "remarks": "关联需求 FP-002，异常输入测试"
 },
 {
  "case_number": "TC-PR-SCFG-013",
  "name": "配气稳定时间-特殊字符输入拒绝",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "gas_stabilization_time": "@#$%^&*"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "页面正常加载"
   },
   {
    "step": "2. 在\"配气稳定时间\"输入框中输入\"@#$%^&*\"",
    "result": "输入框显示\"@#$%^&*\""
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存失败，\"配气稳定时间\"字段红色高亮并提示\"请输入有效数字\""
   }
  ],
  "remarks": "关联需求 FP-002，异常输入测试"
 },
 {
  "case_number": "TC-PR-SCFG-014",
  "name": "配气稳定时间-空值校验",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "gas_stabilization_time": ""
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "页面正常加载"
   },
   {
    "step": "2. 清空\"配气稳定时间\"输入框",
    "result": "输入框为空"
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存失败，\"配气稳定时间\"字段红色高亮并提示\"配气稳定时间不能为空\""
   }
  ],
  "remarks": "关联需求 FP-002，异常输入测试"
 },
 {
  "case_number": "TC-PR-SCFG-015",
  "name": "配气总量偏差阈值-有效值输入",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "total_gas_deviation": "50.00"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "页面正常加载"
   },
   {
    "step": "2. 在\"配气总量偏差阈值\"输入框中输入\"50.00\"",
    "result": "输入框显示\"50.00\""
   },
   {
    "step": "3. 点击\"保存\"按钮，关闭页面后重新打开",
    "result": "保存成功，重新打开后该字段显示\"50.00\""
   }
  ],
  "remarks": "关联需求 FP-003"
 },
 {
  "case_number": "TC-PR-SCFG-016",
  "name": "配气总量偏差阈值-下边界值(0.00)",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "total_gas_deviation": "0.00"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "页面正常加载"
   },
   {
    "step": "2. 在\"配气总量偏差阈值\"输入框中输入\"0.00\"",
    "result": "输入框显示\"0.00\""
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "如果0为允许值则保存成功；否则字段旁提示\"偏差阈值必须大于0\""
   }
  ],
  "remarks": "关联需求 FP-003，边界值测试"
 },
 {
  "case_number": "TC-PR-SCFG-017",
  "name": "配气总量偏差阈值-上边界值(9999.99)",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "total_gas_deviation": "9999.99"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "页面正常加载"
   },
   {
    "step": "2. 在\"配气总量偏差阈值\"输入框中输入\"9999.99\"",
    "result": "输入框显示\"9999.99\""
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存成功，无错误提示（若9999.99在范围内）"
   }
  ],
  "remarks": "关联需求 FP-003，边界值测试"
 },
 {
  "case_number": "TC-PR-SCFG-018",
  "name": "配气总量偏差阈值-上边界+1溢出值(10000.00)拒绝",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "total_gas_deviation": "10000.00"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "页面正常加载"
   },
   {
    "step": "2. 在\"配气总量偏差阈值\"输入框中输入\"10000.00\"",
    "result": "输入框显示\"10000.00\""
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存失败，字段红色高亮并提示\"数值超出允许范围(0~9999.99)\""
   }
  ],
  "remarks": "关联需求 FP-003，边界值测试"
 },
 {
  "case_number": "TC-PR-SCFG-019",
  "name": "配气总量偏差阈值-负值(-5.00)拒绝",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "total_gas_deviation": "-5.00"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "页面正常加载"
   },
   {
    "step": "2. 在\"配气总量偏差阈值\"输入框中输入\"-5.00\"",
    "result": "输入框显示\"-5.00\""
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存失败，字段红色高亮并提示\"请输入非负数值\""
   }
  ],
  "remarks": "关联需求 FP-003，异常输入测试"
 },
 {
  "case_number": "TC-PR-SCFG-020",
  "name": "配气总量偏差阈值-非数字输入拒绝",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "total_gas_deviation": "abc"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "页面正常加载"
   },
   {
    "step": "2. 在\"配气总量偏差阈值\"输入框中输入\"abc\"",
    "result": "输入框显示\"abc\""
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存失败，字段红色高亮并提示\"请输入有效数字\""
   }
  ],
  "remarks": "关联需求 FP-003，异常输入测试"
 },
 {
  "case_number": "TC-PR-SCFG-021",
  "name": "配气总量偏差阈值-特殊字符输入拒绝",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "total_gas_deviation": "<script>"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "页面正常加载"
   },
   {
    "step": "2. 在\"配气总量偏差阈值\"输入框中输入\"<script>\"",
    "result": "输入框显示\"<script>\""
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存失败，字段红色高亮并提示\"请输入有效数字\""
   }
  ],
  "remarks": "关联需求 FP-003，异常输入测试"
 },
 {
  "case_number": "TC-PR-SCFG-022",
  "name": "配气总量偏差阈值-空值校验",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "total_gas_deviation": ""
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "页面正常加载"
   },
   {
    "step": "2. 清空\"配气总量偏差阈值\"输入框",
    "result": "输入框为空"
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存失败，字段红色高亮并提示\"配气总量偏差阈值不能为空\""
   }
  ],
  "remarks": "关联需求 FP-003，异常输入测试"
 },
 {
  "case_number": "TC-PR-SCFG-023",
  "name": "查询周期-默认值100ms展示",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "标气制备软件首次安装或配置已重置",
  "test_data": {
   "default_value": "100"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "页面正常加载"
   },
   {
    "step": "2. 查看\"查询周期\"输入框",
    "result": "\"查询周期\"输入框中默认显示\"100\"，单位标注为ms"
   }
  ],
  "remarks": "关联需求 FP-004"
 },
 {
  "case_number": "TC-PR-SCFG-024",
  "name": "查询周期-有效值修改(500ms)",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "query_period": "500"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "页面正常加载"
   },
   {
    "step": "2. 在\"查询周期\"输入框中输入\"500\"",
    "result": "输入框显示\"500\""
   },
   {
    "step": "3. 点击\"保存\"按钮，关闭页面后重新打开",
    "result": "保存成功，重新打开后查询周期显示\"500\""
   }
  ],
  "remarks": "关联需求 FP-004"
 },
 {
  "case_number": "TC-PR-SCFG-025",
  "name": "查询周期-下边界值(1ms)",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "query_period": "1"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "页面正常加载"
   },
   {
    "step": "2. 在\"查询周期\"输入框中输入\"1\"",
    "result": "输入框显示\"1\""
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存成功（若1ms为有效最小值），无错误提示"
   }
  ],
  "remarks": "关联需求 FP-004，边界值测试"
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 6. ws-tc_sysconfig_v3

- 来源：`workspace/testcase/tc_sysconfig_v3.jsonl`　分组：(旧样本)　用例数：25

```json
[
 {
  "case_number": "TC-PR-SC-001",
  "name": "端口连接-选择有效端口连接成功",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "标气制备软件已启动，端口号下拉列表已加载",
  "test_data": {
   "port": "COM1"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "显示端口号下拉列表，默认显示\"1\""
   },
   {
    "step": "2. 从下拉列表中选择\"COM1\"",
    "result": "下拉列表收起，端口号显示为\"COM1\""
   },
   {
    "step": "3. 点击\"连接\"按钮",
    "result": "连接成功，按钮文字变为\"断开\"，连接状态指示灯变为绿色"
   }
  ],
  "remarks": "关联需求 FP-001"
 },
 {
  "case_number": "TC-PR-SC-002",
  "name": "端口连接-无效端口连接失败",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "标气制备软件已启动，目标端口COM99不存在或未连接硬件",
  "test_data": {
   "port": "COM99"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "显示端口号下拉列表"
   },
   {
    "step": "2. 从下拉列表中选择\"COM99\"",
    "result": "端口号显示为\"COM99\""
   },
   {
    "step": "3. 点击\"连接\"按钮",
    "result": "连接失败，弹出错误提示\"端口连接失败，请检查端口状态\"，按钮仍为\"连接\""
   }
  ],
  "remarks": "关联需求 FP-001"
 },
 {
  "case_number": "TC-PR-SC-003",
  "name": "端口连接-端口被占用时提示",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "目标端口COM1已被其他程序占用",
  "test_data": {
   "port": "COM1"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "页面正常加载，端口号默认显示\"1\""
   },
   {
    "step": "2. 从下拉列表中选择\"COM1\"",
    "result": "端口号显示为\"COM1\""
   },
   {
    "step": "3. 点击\"连接\"按钮",
    "result": "连接失败，弹出提示\"端口COM1已被占用，请选择其他端口\"，按钮保持\"连接\""
   }
  ],
  "remarks": "关联需求 FP-001"
 },
 {
  "case_number": "TC-PR-SC-004",
  "name": "端口连接-已连接状态下断开连接",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "端口COM1已成功连接，按钮显示为\"断开\"",
  "test_data": {
   "port": "COM1"
  },
  "test_case_steps": [
   {
    "step": "1. 确认当前端口已连接，按钮显示\"断开\"",
    "result": "页面显示\"断开\"按钮，连接状态指示灯为绿色"
   },
   {
    "step": "2. 点击\"断开\"按钮",
    "result": "连接断开，按钮文字恢复为\"连接\"，连接状态指示灯变为灰色"
   }
  ],
  "remarks": "关联需求 FP-001"
 },
 {
  "case_number": "TC-PR-SC-005",
  "name": "端口连接-断开后重新连接",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "端口COM1之前已连接后断开",
  "test_data": {
   "port": "COM1"
  },
  "test_case_steps": [
   {
    "step": "1. 确认当前端口处于断开状态",
    "result": "按钮显示\"连接\"，连接状态指示灯为灰色"
   },
   {
    "step": "2. 再次选择\"COM1\"并点击\"连接\"",
    "result": "连接成功，按钮变为\"断开\"，连接状态指示灯变绿"
   }
  ],
  "remarks": "关联需求 FP-001"
 },
 {
  "case_number": "TC-PR-SC-006",
  "name": "端口连接-下拉列表展示可选端口",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "expected_ports": "COM1,COM2,COM3,COM4,COM5,COM6,COM7,COM8,COM9,COM10"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "页面正常加载"
   },
   {
    "step": "2. 点击端口号下拉列表展开",
    "result": "下拉列表展示可选端口，至少包含COM1~COM10共10个选项；默认选中\"1\""
   }
  ],
  "remarks": "关联需求 FP-001"
 },
 {
  "case_number": "TC-PR-SC-007",
  "name": "配气稳定时间-有效值输入",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "标气制备软件已启动，端口已连接",
  "test_data": {
   "gas_stabilization_time": "30.50"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "页面正常加载，配气稳定时间输入框为空"
   },
   {
    "step": "2. 在\"配气稳定时间\"输入框中输入\"30.50\"",
    "result": "输入框显示\"30.50\""
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存成功，页面顶部显示\"保存成功\"提示；重新打开页面该字段显示\"30.50\""
   }
  ],
  "remarks": "关联需求 FP-002"
 },
 {
  "case_number": "TC-PR-SC-008",
  "name": "配气稳定时间-下边界值(0.00)",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "gas_stabilization_time": "0.00"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "页面正常加载"
   },
   {
    "step": "2. 在\"配气稳定时间\"输入框中输入\"0.00\"",
    "result": "输入框显示\"0.00\""
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "如果0为允许值则保存成功，无错误提示；如果0为不允许值则字段旁提示\"配气稳定时间必须大于0\""
   }
  ],
  "remarks": "关联需求 FP-002，边界值测试"
 },
 {
  "case_number": "TC-PR-SC-009",
  "name": "配气稳定时间-上边界值(9999.99)",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "gas_stabilization_time": "9999.99"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "页面正常加载"
   },
   {
    "step": "2. 在\"配气稳定时间\"输入框中输入\"9999.99\"",
    "result": "输入框显示\"9999.99\""
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存成功（若9999.99在范围内），无错误提示"
   }
  ],
  "remarks": "关联需求 FP-002，边界值测试"
 },
 {
  "case_number": "TC-PR-SC-010",
  "name": "配气稳定时间-上边界+1溢出值(10000.00)拒绝",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "gas_stabilization_time": "10000.00"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "页面正常加载"
   },
   {
    "step": "2. 在\"配气稳定时间\"输入框中输入\"10000.00\"",
    "result": "输入框显示\"10000.00\""
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存失败，\"配气稳定时间\"字段红色高亮并提示\"数值超出允许范围(0~9999.99)\""
   }
  ],
  "remarks": "关联需求 FP-002，边界值测试"
 },
 {
  "case_number": "TC-PR-SC-011",
  "name": "配气稳定时间-负值(-1.00)拒绝",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "gas_stabilization_time": "-1.00"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "页面正常加载"
   },
   {
    "step": "2. 在\"配气稳定时间\"输入框中输入\"-1.00\"",
    "result": "输入框显示\"-1.00\""
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存失败，\"配气稳定时间\"字段红色高亮并提示\"请输入非负数值\""
   }
  ],
  "remarks": "关联需求 FP-002，异常输入测试"
 },
 {
  "case_number": "TC-PR-SC-012",
  "name": "配气稳定时间-非数字输入拒绝",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "gas_stabilization_time": "abc"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "页面正常加载"
   },
   {
    "step": "2. 在\"配气稳定时间\"输入框中输入\"abc\"",
    "result": "输入框显示\"abc\""
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存失败，\"配气稳定时间\"字段红色高亮并提示\"请输入有效数字\""
   }
  ],
  "remarks": "关联需求 FP-002，异常输入测试"
 },
 {
  "case_number": "TC-PR-SC-013",
  "name": "配气稳定时间-特殊字符输入拒绝",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "gas_stabilization_time": "@#$%^&*"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "页面正常加载"
   },
   {
    "step": "2. 在\"配气稳定时间\"输入框中输入\"@#$%^&*\"",
    "result": "输入框显示\"@#$%^&*\""
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存失败，\"配气稳定时间\"字段红色高亮并提示\"请输入有效数字\""
   }
  ],
  "remarks": "关联需求 FP-002，异常输入测试"
 },
 {
  "case_number": "TC-PR-SC-014",
  "name": "配气稳定时间-空值校验",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "gas_stabilization_time": ""
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "页面正常加载"
   },
   {
    "step": "2. 清空\"配气稳定时间\"输入框",
    "result": "输入框为空"
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存失败，\"配气稳定时间\"字段红色高亮并提示\"配气稳定时间不能为空\""
   }
  ],
  "remarks": "关联需求 FP-002，异常输入测试"
 },
 {
  "case_number": "TC-PR-SC-015",
  "name": "配气总量偏差阈值-有效值输入",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "total_gas_deviation": "50.00"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "页面正常加载"
   },
   {
    "step": "2. 在\"配气总量偏差阈值\"输入框中输入\"50.00\"",
    "result": "输入框显示\"50.00\""
   },
   {
    "step": "3. 点击\"保存\"按钮，关闭页面后重新打开",
    "result": "保存成功，重新打开后该字段显示\"50.00\""
   }
  ],
  "remarks": "关联需求 FP-003"
 },
 {
  "case_number": "TC-PR-SC-016",
  "name": "配气总量偏差阈值-下边界值(0.00)",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "total_gas_deviation": "0.00"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "页面正常加载"
   },
   {
    "step": "2. 在\"配气总量偏差阈值\"输入框中输入\"0.00\"",
    "result": "输入框显示\"0.00\""
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "如果0为允许值则保存成功；否则字段旁提示\"偏差阈值必须大于0\""
   }
  ],
  "remarks": "关联需求 FP-003，边界值测试"
 },
 {
  "case_number": "TC-PR-SC-017",
  "name": "配气总量偏差阈值-上边界值(9999.99)",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "total_gas_deviation": "9999.99"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "页面正常加载"
   },
   {
    "step": "2. 在\"配气总量偏差阈值\"输入框中输入\"9999.99\"",
    "result": "输入框显示\"9999.99\""
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存成功，无错误提示（若9999.99在范围内）"
   }
  ],
  "remarks": "关联需求 FP-003，边界值测试"
 },
 {
  "case_number": "TC-PR-SC-018",
  "name": "配气总量偏差阈值-上边界+1溢出值(10000.00)拒绝",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "total_gas_deviation": "10000.00"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "页面正常加载"
   },
   {
    "step": "2. 在\"配气总量偏差阈值\"输入框中输入\"10000.00\"",
    "result": "输入框显示\"10000.00\""
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存失败，字段红色高亮并提示\"数值超出允许范围(0~9999.99)\""
   }
  ],
  "remarks": "关联需求 FP-003，边界值测试"
 },
 {
  "case_number": "TC-PR-SC-019",
  "name": "配气总量偏差阈值-负值(-5.00)拒绝",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "total_gas_deviation": "-5.00"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "页面正常加载"
   },
   {
    "step": "2. 在\"配气总量偏差阈值\"输入框中输入\"-5.00\"",
    "result": "输入框显示\"-5.00\""
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存失败，字段红色高亮并提示\"请输入非负数值\""
   }
  ],
  "remarks": "关联需求 FP-003，异常输入测试"
 },
 {
  "case_number": "TC-PR-SC-020",
  "name": "配气总量偏差阈值-非数字输入拒绝",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "total_gas_deviation": "abc"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "页面正常加载"
   },
   {
    "step": "2. 在\"配气总量偏差阈值\"输入框中输入\"abc\"",
    "result": "输入框显示\"abc\""
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存失败，字段红色高亮并提示\"请输入有效数字\""
   }
  ],
  "remarks": "关联需求 FP-003，异常输入测试"
 },
 {
  "case_number": "TC-PR-SC-021",
  "name": "配气总量偏差阈值-特殊字符输入拒绝",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "total_gas_deviation": "<script>"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "页面正常加载"
   },
   {
    "step": "2. 在\"配气总量偏差阈值\"输入框中输入\"<script>\"",
    "result": "输入框显示\"<script>\""
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存失败，字段红色高亮并提示\"请输入有效数字\""
   }
  ],
  "remarks": "关联需求 FP-003，异常输入测试"
 },
 {
  "case_number": "TC-PR-SC-022",
  "name": "配气总量偏差阈值-空值校验",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "total_gas_deviation": ""
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "页面正常加载"
   },
   {
    "step": "2. 清空\"配气总量偏差阈值\"输入框",
    "result": "输入框为空"
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存失败，字段红色高亮并提示\"配气总量偏差阈值不能为空\""
   }
  ],
  "remarks": "关联需求 FP-003，异常输入测试"
 },
 {
  "case_number": "TC-PR-SC-023",
  "name": "查询周期-默认值100ms展示",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "标气制备软件首次安装或配置已重置",
  "test_data": {
   "default_value": "100"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "页面正常加载"
   },
   {
    "step": "2. 查看\"查询周期\"输入框",
    "result": "\"查询周期\"输入框中默认显示\"100\"，单位标注为ms"
   }
  ],
  "remarks": "关联需求 FP-004"
 },
 {
  "case_number": "TC-PR-SC-024",
  "name": "查询周期-有效值修改(500ms)",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "query_period": "500"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "页面正常加载"
   },
   {
    "step": "2. 在\"查询周期\"输入框中输入\"500\"",
    "result": "输入框显示\"500\""
   },
   {
    "step": "3. 点击\"保存\"按钮，关闭页面后重新打开",
    "result": "保存成功，重新打开后查询周期显示\"500\""
   }
  ],
  "remarks": "关联需求 FP-004"
 },
 {
  "case_number": "TC-PR-SC-025",
  "name": "查询周期-下边界值(1ms)",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "query_period": "1"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "页面正常加载"
   },
   {
    "step": "2. 在\"查询周期\"输入框中输入\"1\"",
    "result": "输入框显示\"1\""
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存成功（若1ms为有效最小值），无错误提示"
   }
  ],
  "remarks": "关联需求 FP-004，边界值测试"
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 7. ws-tc_sysconfig_module_系统配置

- 来源：`workspace/testcase/tc_sysconfig_module_系统配置.jsonl`　分组：(旧样本)　用例数：25

```json
[
 {
  "case_number": "TC-PR-SCFG-001",
  "name": "端口连接-选择有效端口连接成功",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "标气制备软件已启动，端口号下拉列表已加载",
  "test_data": {
   "port": "COM1"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "显示端口号下拉列表，默认显示\"1\""
   },
   {
    "step": "2. 从下拉列表中选择\"COM1\""
   },
   {
    "step": "3. 点击\"连接\"按钮",
    "result": "连接成功，按钮文字变为\"断开\"，连接状态指示灯变为绿色"
   }
  ],
  "remarks": "关联需求 FP-001"
 },
 {
  "case_number": "TC-PR-SCFG-002",
  "name": "端口连接-无效端口连接失败",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "标气制备软件已启动，目标端口COM99不存在或未连接硬件",
  "test_data": {
   "port": "COM99"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "显示端口号下拉列表"
   },
   {
    "step": "2. 从下拉列表中选择\"COM99\"（无效端口）"
   },
   {
    "step": "3. 点击\"连接\"按钮",
    "result": "连接失败，弹出错误提示\"端口连接失败，请检查端口状态\"，按钮仍为\"连接\""
   }
  ],
  "remarks": "关联需求 FP-001"
 },
 {
  "case_number": "TC-PR-SCFG-003",
  "name": "端口连接-端口被占用时提示",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "目标端口COM1已被其他程序占用",
  "test_data": {
   "port": "COM1"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面"
   },
   {
    "step": "2. 从下拉列表中选择\"COM1\""
   },
   {
    "step": "3. 点击\"连接\"按钮",
    "result": "连接失败，弹出提示\"端口COM1已被占用，请选择其他端口\"，按钮保持\"连接\""
   }
  ],
  "remarks": "关联需求 FP-001"
 },
 {
  "case_number": "TC-PR-SCFG-004",
  "name": "端口连接-已连接状态下断开连接",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "端口COM1已成功连接，按钮显示为\"断开\"",
  "test_data": {
   "port": "COM1"
  },
  "test_case_steps": [
   {
    "step": "1. 确认当前端口已连接，按钮显示\"断开\""
   },
   {
    "step": "2. 点击\"断开\"按钮",
    "result": "连接断开，按钮文字恢复为\"连接\"，连接状态指示灯变为灰色/红色"
   }
  ],
  "remarks": "关联需求 FP-001"
 },
 {
  "case_number": "TC-PR-SCFG-005",
  "name": "端口连接-断开后重新连接",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "端口COM1之前已连接后断开",
  "test_data": {
   "port": "COM1"
  },
  "test_case_steps": [
   {
    "step": "1. 确认当前端口处于断开状态"
   },
   {
    "step": "2. 再次选择\"COM1\"并点击\"连接\""
   },
   {
    "step": "3. 观察连接结果",
    "result": "连接成功，按钮变为\"断开\"，连接状态指示灯变绿"
   }
  ],
  "remarks": "关联需求 FP-001"
 },
 {
  "case_number": "TC-PR-SCFG-006",
  "name": "端口连接-下拉列表展示可选端口",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "标气制备软件已启动",
  "test_data": {},
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面"
   },
   {
    "step": "2. 点击端口号下拉列表展开",
    "result": "下拉列表展示可选端口，至少包含COM1~COM10共10个选项；默认选中\"1\""
   }
  ],
  "remarks": "关联需求 FP-001"
 },
 {
  "case_number": "TC-PR-SCFG-007",
  "name": "配气稳定时间-有效值输入",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "标气制备软件已启动，端口已连接",
  "test_data": {
   "gas_stabilization_time": "30.50"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面"
   },
   {
    "step": "2. 在\"配气稳定时间\"输入框中输入\"30.50\""
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存成功，无错误提示；重新打开页面查看该字段显示为\"30.50\""
   }
  ],
  "remarks": "关联需求 FP-002"
 },
 {
  "case_number": "TC-PR-SCFG-008",
  "name": "配气稳定时间-下边界值(0.00)",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "gas_stabilization_time": "0.00"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面"
   },
   {
    "step": "2. 在\"配气稳定时间\"输入框中输入\"0.00\""
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "如果0为允许值则保存成功；如果0为不允许值则提示\"配气稳定时间必须大于0\""
   }
  ],
  "remarks": "关联需求 FP-002，边界值测试"
 },
 {
  "case_number": "TC-PR-SCFG-009",
  "name": "配气稳定时间-上边界值(9999.99)",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "gas_stabilization_time": "9999.99"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面"
   },
   {
    "step": "2. 在\"配气稳定时间\"输入框中输入\"9999.99\""
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存成功（若9999.99在范围内），无错误提示"
   }
  ],
  "remarks": "关联需求 FP-002，边界值测试"
 },
 {
  "case_number": "TC-PR-SCFG-010",
  "name": "配气稳定时间-上边界+1溢出值(10000.00)拒绝",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "gas_stabilization_time": "10000.00"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面"
   },
   {
    "step": "2. 在\"配气稳定时间\"输入框中输入\"10000.00\""
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存失败，\"配气稳定时间\"字段旁提示\"数值超出允许范围(0~9999.99)\""
   }
  ],
  "remarks": "关联需求 FP-002，边界值测试"
 },
 {
  "case_number": "TC-PR-SCFG-011",
  "name": "配气稳定时间-负值(-1.00)拒绝",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "gas_stabilization_time": "-1.00"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面"
   },
   {
    "step": "2. 在\"配气稳定时间\"输入框中输入\"-1.00\""
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存失败，\"配气稳定时间\"字段旁提示\"请输入非负数值\""
   }
  ],
  "remarks": "关联需求 FP-002，异常输入测试"
 },
 {
  "case_number": "TC-PR-SCFG-012",
  "name": "配气稳定时间-非数字输入拒绝",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "gas_stabilization_time": "abc"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面"
   },
   {
    "step": "2. 在\"配气稳定时间\"输入框中输入\"abc\""
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存失败，\"配气稳定时间\"字段旁提示\"请输入有效数字\""
   }
  ],
  "remarks": "关联需求 FP-002，异常输入测试"
 },
 {
  "case_number": "TC-PR-SCFG-013",
  "name": "配气稳定时间-特殊字符/超长字符串拒绝",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "gas_stabilization_time": "@#$%^&*"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面"
   },
   {
    "step": "2. 在\"配气稳定时间\"输入框中输入\"@#$%\"或用脚本输入超长字符串（100个字符）"
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存失败，字段旁提示\"请输入有效数字\""
   }
  ],
  "remarks": "关联需求 FP-002，异常输入测试"
 },
 {
  "case_number": "TC-PR-SCFG-014",
  "name": "配气稳定时间-空值校验",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "gas_stabilization_time": ""
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面"
   },
   {
    "step": "2. 清空\"配气稳定时间\"输入框"
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存失败，\"配气稳定时间\"字段旁提示\"配气稳定时间不能为空\""
   }
  ],
  "remarks": "关联需求 FP-002，异常输入测试"
 },
 {
  "case_number": "TC-PR-SCFG-015",
  "name": "配气总量偏差阈值-有效值输入",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "total_gas_deviation": "50.00"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面"
   },
   {
    "step": "2. 在\"配气总量偏差阈值\"输入框中输入\"50.00\""
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存成功，无错误提示；重新打开页面该字段显示\"50.00\""
   }
  ],
  "remarks": "关联需求 FP-003"
 },
 {
  "case_number": "TC-PR-SCFG-016",
  "name": "配气总量偏差阈值-下边界值(0.00)",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "total_gas_deviation": "0.00"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面"
   },
   {
    "step": "2. 在\"配气总量偏差阈值\"输入框中输入\"0.00\""
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "如果0为允许值则保存成功；否则提示\"偏差阈值必须大于0\""
   }
  ],
  "remarks": "关联需求 FP-003，边界值测试"
 },
 {
  "case_number": "TC-PR-SCFG-017",
  "name": "配气总量偏差阈值-上边界值(9999.99)",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "total_gas_deviation": "9999.99"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面"
   },
   {
    "step": "2. 在\"配气总量偏差阈值\"输入框中输入\"9999.99\""
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存成功（若9999.99在范围内）"
   }
  ],
  "remarks": "关联需求 FP-003，边界值测试"
 },
 {
  "case_number": "TC-PR-SCFG-018",
  "name": "配气总量偏差阈值-上边界+1溢出值(10000.00)拒绝",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "total_gas_deviation": "10000.00"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面"
   },
   {
    "step": "2. 在\"配气总量偏差阈值\"输入框中输入\"10000.00\""
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存失败，字段旁提示\"数值超出允许范围(0~9999.99)\""
   }
  ],
  "remarks": "关联需求 FP-003，边界值测试"
 },
 {
  "case_number": "TC-PR-SCFG-019",
  "name": "配气总量偏差阈值-负值(-5.00)拒绝",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "total_gas_deviation": "-5.00"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面"
   },
   {
    "step": "2. 在\"配气总量偏差阈值\"输入框中输入\"-5.00\""
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存失败，字段旁提示\"请输入非负数值\""
   }
  ],
  "remarks": "关联需求 FP-003，异常输入测试"
 },
 {
  "case_number": "TC-PR-SCFG-020",
  "name": "配气总量偏差阈值-非数字输入拒绝",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "total_gas_deviation": "abc"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面"
   },
   {
    "step": "2. 在\"配气总量偏差阈值\"输入框中输入\"abc\""
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存失败，字段旁提示\"请输入有效数字\""
   }
  ],
  "remarks": "关联需求 FP-003，异常输入测试"
 },
 {
  "case_number": "TC-PR-SCFG-021",
  "name": "配气总量偏差阈值-特殊字符/超长字符串拒绝",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "total_gas_deviation": "<script>alert(1)</script>"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面"
   },
   {
    "step": "2. 在\"配气总量偏差阈值\"输入框中输入含特殊字符/XSS Payload"
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存失败，字段旁提示\"请输入有效数字\""
   }
  ],
  "remarks": "关联需求 FP-003，异常输入+基础安全测试"
 },
 {
  "case_number": "TC-PR-SCFG-022",
  "name": "配气总量偏差阈值-空值校验",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "total_gas_deviation": ""
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面"
   },
   {
    "step": "2. 清空\"配气总量偏差阈值\"输入框"
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存失败，字段旁提示\"配气总量偏差阈值不能为空\""
   }
  ],
  "remarks": "关联需求 FP-003，异常输入测试"
 },
 {
  "case_number": "TC-PR-SCFG-023",
  "name": "查询周期-默认值100ms展示",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "标气制备软件首次安装或配置已重置",
  "test_data": {},
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面"
   },
   {
    "step": "2. 查看\"查询周期\"输入框",
    "result": "\"查询周期\"输入框中默认显示\"100\"ms"
   }
  ],
  "remarks": "关联需求 FP-004"
 },
 {
  "case_number": "TC-PR-SCFG-024",
  "name": "查询周期-有效值修改(500ms)",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "query_period": "500"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面"
   },
   {
    "step": "2. 在\"查询周期\"输入框中输入\"500\""
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存成功；重新打开页面显示\"500\""
   }
  ],
  "remarks": "关联需求 FP-004"
 },
 {
  "case_number": "TC-PR-SCFG-025",
  "name": "查询周期-下边界值(1ms)",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "标气制备软件已启动",
  "test_data": {
   "query_period": "1"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面"
   },
   {
    "step": "2. 在\"查询周期\"输入框中输入\"1\""
   },
   {
    "step": "3. 点击\"保存\"按钮",
    "result": "保存成功（若1ms为有效最小值）"
   }
  ],
  "remarks": "关联需求 FP-004，边界值测试"
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 8. ws-tc_all_merged

- 来源：`workspace/testcase/tc_all_merged.jsonl`　分组：(旧样本)　用例数：25

```json
[
 {
  "case_number": "TC-SC-CONN-001",
  "name": "端口号输入 - 输入合法端口号并连接成功",
  "module": "设备连接管理",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "系统配置页面已打开，标气制备设备已通电并连接至COM1端口",
  "test_data": {
   "端口号": "COM1"
  },
  "test_case_steps": [
   {
    "step": "将光标定位到端口号输入框",
    "result": "输入框获得焦点"
   },
   {
    "step": "输入端口号\"COM1\"",
    "result": "输入框显示\"COM1\""
   },
   {
    "step": "点击【连接】按钮",
    "result": "连接按钮变为\"连接中...\"状态，等待后连接成功"
   }
  ],
  "remarks": "FP-001/FP-002"
 },
 {
  "case_number": "TC-SC-CONN-002",
  "name": "端口号输入 - 输入超范围端口号",
  "module": "设备连接管理",
  "case_type": "boundary",
  "priority": "critical",
  "preconditions": "系统配置页面已打开",
  "test_data": {
   "端口号": "99999"
  },
  "test_case_steps": [
   {
    "step": "在端口号输入框中输入\"99999\"",
    "result": "输入框显示\"99999\""
   },
   {
    "step": "将焦点移出输入框",
    "result": "输入框下方显示\"端口号超出有效范围（1~65535）\""
   }
  ],
  "remarks": "FP-001 边界值"
 },
 {
  "case_number": "TC-SC-CONN-003",
  "name": "端口号输入 - SQL注入攻击",
  "module": "设备连接管理",
  "case_type": "security",
  "priority": "critical",
  "preconditions": "系统配置页面已打开",
  "test_data": {
   "端口号": "' OR 1=1 --"
  },
  "test_case_steps": [
   {
    "step": "在端口号输入框中输入\"' OR 1=1 --\"",
    "result": "输入框接受输入或拒绝特殊字符"
   },
   {
    "step": "点击【连接】按钮",
    "result": "后端对输入进行转义，不执行注入，提示\"端口号格式无效\""
   }
  ],
  "remarks": "FP-001 安全-SQL注入"
 },
 {
  "case_number": "TC-SC-CONN-004",
  "name": "端口号输入 - XSS跨站脚本攻击",
  "module": "设备连接管理",
  "case_type": "security",
  "priority": "critical",
  "preconditions": "系统配置页面已打开",
  "test_data": {
   "端口号": "<script>alert('xss')</script>"
  },
  "test_case_steps": [
   {
    "step": "在端口号输入框中输入\"<script>alert('xss')</script>\"",
    "result": "输入框对特殊字符进行HTML转义或拒绝输入"
   },
   {
    "step": "点击【连接】按钮",
    "result": "前端/后端对输入进行转义处理，不执行脚本"
   }
  ],
  "remarks": "FP-001 安全-XSS"
 },
 {
  "case_number": "TC-SC-CONN-005",
  "name": "端口号输入 - 空值校验",
  "module": "设备连接管理",
  "case_type": "abnormal",
  "priority": "critical",
  "preconditions": "系统配置页面已打开",
  "test_data": {
   "端口号": ""
  },
  "test_case_steps": [
   {
    "step": "清空端口号输入框",
    "result": "输入框为空"
   },
   {
    "step": "点击【连接】按钮",
    "result": "连接按钮不触发连接请求，提示\"请输入端口号\""
   }
  ],
  "remarks": "FP-001 异常"
 },
 {
  "case_number": "TC-SC-CONN-006",
  "name": "端口号输入 - 边界值0/1/65535/65536",
  "module": "设备连接管理",
  "case_type": "boundary",
  "priority": "critical",
  "preconditions": "系统配置页面已打开",
  "test_data": {
   "端口号1": "1",
   "端口号2": "65535",
   "端口号3": "0",
   "端口号4": "65536"
  },
  "test_case_steps": [
   {
    "step": "输入\"1\"并移出焦点",
    "result": "通过校验，无错误提示"
   },
   {
    "step": "清空后输入\"65535\"并移出焦点",
    "result": "通过校验，无错误提示"
   },
   {
    "step": "输入\"0\"并移出焦点",
    "result": "提示\"端口号最小值为1\""
   },
   {
    "step": "输入\"65536\"并移出焦点",
    "result": "提示\"端口号最大值为65535\""
   }
  ],
  "remarks": "FP-001 边界值"
 },
 {
  "case_number": "TC-SC-CONN-007",
  "name": "连接可用设备 - 成功建立连接",
  "module": "设备连接管理",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "标气制备设备已通电并连接至COM1端口",
  "test_data": {
   "端口号": "COM1"
  },
  "test_case_steps": [
   {
    "step": "输入\"COM1\"并点击【连接】",
    "result": "按钮变为\"连接中...\"状态"
   },
   {
    "step": "连接成功",
    "result": "按钮变为\"已连接\"（置灰），页面提示\"设备连接成功\""
   }
  ],
  "remarks": "FP-002/FP-003 正向"
 },
 {
  "case_number": "TC-SC-CONN-008",
  "name": "连接不可用端口 - 设备未接入",
  "module": "设备连接管理",
  "case_type": "abnormal",
  "priority": "critical",
  "preconditions": "端口COM5上未连接任何设备",
  "test_data": {
   "端口号": "COM5"
  },
  "test_case_steps": [
   {
    "step": "输入\"COM5\"并点击【连接】",
    "result": "按钮变为\"连接中...\""
   },
   {
    "step": "连接失败",
    "result": "提示\"连接失败：未检测到设备，请检查设备电源和连接线\""
   }
  ],
  "remarks": "FP-002/FP-003 异常"
 },
 {
  "case_number": "TC-SC-CONN-009",
  "name": "连接已被占用的端口",
  "module": "设备连接管理",
  "case_type": "abnormal",
  "priority": "critical",
  "preconditions": "端口COM1已被其他串口工具占用",
  "test_data": {
   "端口号": "COM1"
  },
  "test_case_steps": [
   {
    "step": "输入已被占用的\"COM1\"并点击【连接】",
    "result": "连接失败，提示\"端口COM1已被占用，请关闭其他占用程序后重试\""
   }
  ],
  "remarks": "FP-002 异常"
 },
 {
  "case_number": "TC-SC-CONN-010",
  "name": "设备连接中断后自动检测与重连",
  "module": "设备连接管理",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "设备已连接成功（COM1）",
  "test_data": {
   "端口号": "COM1"
  },
  "test_case_steps": [
   {
    "step": "在已连接状态下断开设备电源",
    "result": "连接状态变为\"已断开\"，提示\"设备连接已中断\""
   },
   {
    "step": "恢复设备电源并点击【连接】",
    "result": "重新连接成功"
   }
  ],
  "remarks": "FP-002/FP-003 恢复"
 },
 {
  "case_number": "TC-SC-CONN-011",
  "name": "防重复提交 - 连接过程中再次点击",
  "module": "设备连接管理",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "设备连接请求正在处理中",
  "test_data": {
   "端口号": "COM1"
  },
  "test_case_steps": [
   {
    "step": "点击【连接】后按钮变为\"连接中...\"",
    "result": "按钮状态为\"连接中...\""
   },
   {
    "step": "再次点击【连接】按钮",
    "result": "第二次点击无效，不发起重复连接请求"
   }
  ],
  "remarks": "FP-002 防重复"
 },
 {
  "case_number": "TC-SC-CONN-012",
  "name": "连接失败时错误信息反馈质量",
  "module": "设备连接管理",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "端口COM99不存在",
  "test_data": {
   "端口号": "COM99"
  },
  "test_case_steps": [
   {
    "step": "输入\"COM99\"并点击【连接】",
    "result": "连接失败后显示明确错误提示（含失败原因和操作建议）"
   }
  ],
  "remarks": "FP-003 反馈"
 },
 {
  "case_number": "TC-SC-GAS-001",
  "name": "配气稳定时间 - 输入合法值保存成功",
  "module": "配气参数配置",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "系统配置页面已打开，各字段为空",
  "test_data": {
   "配气稳定时间": "30"
  },
  "test_case_steps": [
   {
    "step": "在配气稳定时间输入框中输入\"30\"",
    "result": "输入框显示\"30\""
   },
   {
    "step": "填写其他必填字段并点击【保存】",
    "result": "配置保存成功，提示\"配置已保存\""
   }
  ],
  "remarks": "FP-004 正向"
 },
 {
  "case_number": "TC-SC-GAS-002",
  "name": "配气稳定时间 - 边界值测试（0/1/2/299/300/301）",
  "module": "配气参数配置",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "系统配置页面已打开",
  "test_data": {
   "稳定时间值": [
    "0",
    "1",
    "2",
    "299",
    "300",
    "301"
   ]
  },
  "test_case_steps": [
   {
    "step": "输入\"1\"并移出焦点",
    "result": "通过校验，无错误提示"
   },
   {
    "step": "输入\"2\"并移出焦点",
    "result": "通过校验，无错误提示"
   },
   {
    "step": "输入\"299\"并移出焦点",
    "result": "通过校验，无错误提示"
   },
   {
    "step": "输入\"300\"并移出焦点",
    "result": "通过校验，无错误提示"
   },
   {
    "step": "输入\"0\"并移出焦点",
    "result": "提示\"配气稳定时间必须大于0秒\""
   },
   {
    "step": "输入\"301\"并移出焦点",
    "result": "提示\"配气稳定时间不能超过300秒\""
   }
  ],
  "remarks": "FP-004 边界值（假设范围1~300s）"
 },
 {
  "case_number": "TC-SC-GAS-003",
  "name": "配气稳定时间 - 输入负数",
  "module": "配气参数配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "系统配置页面已打开",
  "test_data": {
   "配气稳定时间": "-5"
  },
  "test_case_steps": [
   {
    "step": "输入\"-5\"并移出焦点",
    "result": "提示\"配气稳定时间不能为负数\""
   }
  ],
  "remarks": "FP-004 异常"
 },
 {
  "case_number": "TC-SC-GAS-004",
  "name": "配气稳定时间 - 输入小数",
  "module": "配气参数配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "系统配置页面已打开",
  "test_data": {
   "配气稳定时间": "30.5"
  },
  "test_case_steps": [
   {
    "step": "输入\"30.5\"并移出焦点",
    "result": "如果支持小数则通过；如果只支持整数，提示\"请输入整数\""
   }
  ],
  "remarks": "FP-004 边界"
 },
 {
  "case_number": "TC-SC-GAS-005",
  "name": "配气稳定时间 - 非数字字符",
  "module": "配气参数配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "系统配置页面已打开",
  "test_data": {
   "配气稳定时间": "abc"
  },
  "test_case_steps": [
   {
    "step": "输入\"abc\"并移出焦点",
    "result": "提示\"请输入有效数字\""
   }
  ],
  "remarks": "FP-004 异常"
 },
 {
  "case_number": "TC-SC-GAS-006",
  "name": "配气总量偏差阈值 - 输入合法值保存成功",
  "module": "配气参数配置",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "系统配置页面已打开",
  "test_data": {
   "配气总量偏差阈值": "50"
  },
  "test_case_steps": [
   {
    "step": "输入\"50\"",
    "result": "输入框显示\"50\""
   },
   {
    "step": "点击【保存】",
    "result": "配置保存成功"
   }
  ],
  "remarks": "FP-005 正向"
 },
 {
  "case_number": "TC-SC-GAS-007",
  "name": "配气总量偏差阈值 - 边界值（0/0.1/0.2/999.9/1000/1000.1）",
  "module": "配气参数配置",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "系统配置页面已打开",
  "test_data": {
   "偏差阈值值": [
    "0.1",
    "0.2",
    "999.9",
    "1000",
    "0",
    "1000.1"
   ]
  },
  "test_case_steps": [
   {
    "step": "输入\"0.1\"并移出焦点",
    "result": "通过校验"
   },
   {
    "step": "输入\"0.2\"并移出焦点",
    "result": "通过校验"
   },
   {
    "step": "输入\"999.9\"并移出焦点",
    "result": "通过校验"
   },
   {
    "step": "输入\"1000\"并移出焦点",
    "result": "通过校验"
   },
   {
    "step": "输入\"0\"并移出焦点",
    "result": "提示\"偏差阈值必须大于0\""
   },
   {
    "step": "输入\"1000.1\"并移出焦点",
    "result": "提示\"偏差阈值不能超过1000\""
   }
  ],
  "remarks": "FP-005 边界值（假设范围0.1~1000ml）"
 },
 {
  "case_number": "TC-SC-GAS-008",
  "name": "配气总量偏差阈值 - 负数/空值",
  "module": "配气参数配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "系统配置页面已打开",
  "test_data": {
   "偏差阈值1": "-1",
   "偏差阈值2": ""
  },
  "test_case_steps": [
   {
    "step": "输入\"-1\"并移出焦点",
    "result": "提示\"偏差阈值不能为负数\""
   },
   {
    "step": "清空输入框并移出焦点",
    "result": "提示\"请输入配气总量偏差阈值\""
   }
  ],
  "remarks": "FP-005 异常"
 },
 {
  "case_number": "TC-SC-GAS-009",
  "name": "配气总量偏差阈值 - 输入特殊字符/SQL注入",
  "module": "配气参数配置",
  "case_type": "security",
  "priority": "critical",
  "preconditions": "系统配置页面已打开",
  "test_data": {
   "偏差阈值": "' OR 1=1 --"
  },
  "test_case_steps": [
   {
    "step": "输入\"' OR 1=1 --\"",
    "result": "后端对输入进行转义处理"
   },
   {
    "step": "点击【保存】",
    "result": "提示\"请输入有效数字\"，不执行注入"
   }
  ],
  "remarks": "FP-005 安全"
 },
 {
  "case_number": "TC-SC-GAS-010",
  "name": "查询周期 - 默认值100ms验证",
  "module": "配气参数配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "系统配置页面首次打开",
  "test_data": {
   "查询周期": "100"
  },
  "test_case_steps": [
   {
    "step": "进入系统配置页面",
    "result": "查询周期输入框默认显示\"100\""
   }
  ],
  "remarks": "FP-006 默认值验证"
 },
 {
  "case_number": "TC-SC-GAS-011",
  "name": "查询周期 - 修改合法值并保存",
  "module": "配气参数配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "系统配置页面已打开",
  "test_data": {
   "查询周期": "500"
  },
  "test_case_steps": [
   {
    "step": "输入\"500\"",
    "result": "输入框显示\"500\""
   },
   {
    "step": "点击【保存】",
    "result": "保存成功"
   },
   {
    "step": "重新进入系统配置页面",
    "result": "查询周期显示\"500\""
   }
  ],
  "remarks": "FP-006 正向"
 },
 {
  "case_number": "TC-SC-GAS-012",
  "name": "查询周期 - 边界值（9/10/11/9999/10000/10001）",
  "module": "配气参数配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "系统配置页面已打开",
  "test_data": {
   "查询周期值": [
    "10",
    "11",
    "9999",
    "10000",
    "9",
    "10001"
   ]
  },
  "test_case_steps": [
   {
    "step": "输入\"10\"并移出焦点",
    "result": "通过校验"
   },
   {
    "step": "输入\"11\"并移出焦点",
    "result": "通过校验"
   },
   {
    "step": "输入\"9999\"并移出焦点",
    "result": "通过校验"
   },
   {
    "step": "输入\"10000\"并移出焦点",
    "result": "通过校验"
   },
   {
    "step": "输入\"9\"并移出焦点",
    "result": "提示\"查询周期最小值为10ms\""
   },
   {
    "step": "输入\"10001\"并移出焦点",
    "result": "提示\"查询周期最大值为10000ms\""
   }
  ],
  "remarks": "FP-006 边界值（假设范围10~10000ms）"
 },
 {
  "case_number": "TC-SC-GAS-013",
  "name": "流量偏差阈值 - 输入合法值保存成功",
  "module": "配气参数配置",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "系统配置页面已打开",
  "test_data": {
   "流量偏差阈值": "10"
  },
  "test_case_steps": [
   {
    "step": "输入\"10\"",
    "result": "输入框显示\"10\""
   },
   {
    "step": "点击【保存】",
    "result": "保存成功"
   }
  ],
  "remarks": "FP-007 正向"
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 9. ws-PR-2-final_module_01

- 来源：`workspace/testcase/PR-2/final_module_01.jsonl`　分组：(旧样本)　用例数：25

```json
[
 {
  "name": "创建POS服务订单-绑定完整设备信息成功",
  "case_number": "TC-PR2-POS-001",
  "module": "POS服务订单",
  "case_type": "functional",
  "preconditions": "设备档案已存在（UPN=UPN2026001，序列号=SN2026001，发货时间=2026-03-15）；经销商账号 dealer01 已登录DMS",
  "remarks": "关联需求 REQ-POS-001 / FP-001",
  "priority": "critical",
  "test_data": {
   "合同号": "Contract001",
   "设备UPN": "UPN2026001",
   "设备序列号": "SN2026001",
   "服务产品型号": "AAAA"
  },
  "test_case_steps": [
   {
    "step": "经销商dealer01登录DMS，进入POS服务订单创建页",
    "result": "成功进入创建页，可填写订单信息"
   },
   {
    "step": "填写合同号Contract001，选择服务产品型号AAAA",
    "result": "合同号与产品型号可正常录入"
   },
   {
    "step": "绑定设备UPN=UPN2026001、序列号=SN2026001",
    "result": "设备信息绑定成功，显示对应设备档案"
   },
   {
    "step": "点击【提交订单】",
    "result": "订单创建成功，返回订单号且格式为字母+数字组合，订单状态显示为已提交，全程未出现经销商二次确认环节"
   }
  ]
 },
 {
  "name": "创建POS服务订单-设备UPN为空拒绝",
  "case_number": "TC-PR2-POS-002",
  "module": "POS服务订单",
  "case_type": "functional",
  "preconditions": "经销商账号 dealer01 已登录DMS",
  "remarks": "关联需求 REQ-POS-001 / FP-001",
  "priority": "critical",
  "test_data": {
   "合同号": "Contract002",
   "设备UPN": "",
   "设备序列号": "SN2026001",
   "服务产品型号": "AAAA"
  },
  "test_case_steps": [
   {
    "step": "进入POS服务订单创建页，填写合同号Contract002与产品型号AAAA",
    "result": "表单可正常填写"
   },
   {
    "step": "设备UPN字段留空，仅绑定序列号SN2026001",
    "result": "序列号绑定成功"
   },
   {
    "step": "点击【提交订单】",
    "result": "系统拒绝提交，提示\"设备UPN为必填项\"，订单未创建"
   }
  ]
 },
 {
  "name": "创建POS服务订单-设备序列号为空拒绝",
  "case_number": "TC-PR2-POS-003",
  "module": "POS服务订单",
  "case_type": "functional",
  "preconditions": "经销商账号 dealer01 已登录DMS",
  "remarks": "关联需求 REQ-POS-001 / FP-001",
  "priority": "critical",
  "test_data": {
   "合同号": "Contract003",
   "设备UPN": "UPN2026001",
   "设备序列号": "",
   "服务产品型号": "AAAA"
  },
  "test_case_steps": [
   {
    "step": "进入POS服务订单创建页，填写合同号Contract003与产品型号AAAA",
    "result": "表单可正常填写"
   },
   {
    "step": "设备序列号字段留空，仅绑定UPN=UPN2026001",
    "result": "UPN绑定成功"
   },
   {
    "step": "点击【提交订单】",
    "result": "系统拒绝提交，提示\"设备序列号为必填项\"，订单未创建"
   }
  ]
 },
 {
  "name": "创建POS服务订单-设备档案不存在拒绝",
  "case_number": "TC-PR2-POS-004",
  "module": "POS服务订单",
  "case_type": "functional",
  "preconditions": "经销商账号 dealer01 已登录DMS；UPN999999/SN999999 对应设备档案不存在",
  "remarks": "关联需求 REQ-POS-001 / FP-001",
  "priority": "high",
  "test_data": {
   "合同号": "Contract004",
   "设备UPN": "UPN999999",
   "设备序列号": "SN999999",
   "服务产品型号": "AAAA"
  },
  "test_case_steps": [
   {
    "step": "进入POS服务订单创建页，填写合同号Contract004与产品型号AAAA",
    "result": "表单可正常填写"
   },
   {
    "step": "绑定设备UPN=UPN999999、序列号=SN999999",
    "result": "系统提示\"未找到对应设备档案，无法绑定\"，该设备未加入订单明细"
   },
   {
    "step": "查看【提交订单】按钮状态",
    "result": "提交按钮保持禁用状态无法点击，订单未创建，页面展示可读错误提示"
   }
  ]
 },
 {
  "name": "创建POS服务订单-自由文本字段SQL注入与XSS防护",
  "case_number": "TC-PR2-POS-005",
  "module": "POS服务订单",
  "case_type": "security",
  "preconditions": "经销商账号 dealer01 已登录DMS；设备档案存在（UPN=UPN2026001、SN=SN2026001）",
  "remarks": "关联需求 REQ-POS-001 / FP-001 / 安全红线",
  "priority": "high",
  "test_data": {
   "合同号": "' OR '1'='1",
   "设备UPN": "UPN2026001",
   "设备序列号": "SN2026001",
   "服务产品型号": "AAAA",
   "备注": "<script>alert(1)</script>"
  },
  "test_case_steps": [
   {
    "step": "进入POS服务订单创建页",
    "result": "表单正常加载"
   },
   {
    "step": "合同号输入SQL注入Payload：' OR '1'='1，备注字段输入XSS Payload：<script>alert(1)</script>，然后绑定有效设备档案UPN2026001/SN2026001",
    "result": "设备绑定成功（序列号保持有效值SN2026001不受注入Payload影响），合同号与备注按普通字符串保存，无数据库异常"
   },
   {
    "step": "点击【提交订单】",
    "result": "订单创建成功，未执行注入语句，无SQL报错；订单列表页展示该订单时无XSS弹窗，合同号与备注按转义后原文展示"
   }
  ]
 },
 {
  "name": "服务周期计算-合同已对接服务周期直接使用对接数据",
  "case_number": "TC-PR2-POS-006",
  "module": "POS服务订单",
  "case_type": "functional",
  "preconditions": "合同系统已对接服务周期与开票时间（合同服务起始=2026-05-01、截止=2029-04-30）；设备档案存在（UPN=UPN2026001、SN=SN2026001）",
  "remarks": "关联需求 REQ-POS-002 / FP-002",
  "priority": "critical",
  "test_data": {
   "合同号": "Contract006",
   "合同服务起始": "2026-05-01",
   "合同服务截止": "2029-04-30",
   "设备UPN": "UPN2026001",
   "设备序列号": "SN2026001"
  },
  "test_case_steps": [
   {
    "step": "使用已对接服务周期与开票时间的合同创建POS订单并绑定设备",
    "result": "订单信息填写完成"
   },
   {
    "step": "提交订单并完成SAP对接",
    "result": "订单推送至SAP"
   },
   {
    "step": "查看推送SAP的服务周期字段",
    "result": "服务起始时间=2026-05-01、服务截止时间=2029-04-30，与合同对接数据完全一致，未按发货时间重新计算"
   }
  ]
 },
 {
  "name": "服务周期计算-未对接服务周期起始时间=发货时间+x月",
  "case_number": "TC-PR2-POS-007",
  "module": "POS服务订单",
  "case_type": "functional",
  "preconditions": "合同未对接服务周期与开票时间；设备档案发货时间=2026-01-20（UPN=UPN2026001、SN=SN2026001）；x=1（精度与需求一致）",
  "remarks": "关联需求 REQ-POS-002 / FP-002 / 阻塞性假设x已确认",
  "priority": "critical",
  "test_data": {
   "合同号": "Contract007",
   "设备发货时间": "2026-01-20",
   "x": 1,
   "设备UPN": "UPN2026001",
   "设备序列号": "SN2026001"
  },
  "test_case_steps": [
   {
    "step": "使用未对接服务周期的合同创建POS订单并绑定设备",
    "result": "订单信息填写完成"
   },
   {
    "step": "提交订单并完成SAP对接",
    "result": "订单推送至SAP"
   },
   {
    "step": "查看推送SAP的服务起始时间",
    "result": "服务起始时间=2026-02-20（发货时间2026-01-20+1月），格式YYYY-mm-DD"
   }
  ]
 },
 {
  "name": "服务周期计算-未对接服务周期截止时间=发货时间+x月+12n",
  "case_number": "TC-PR2-POS-008",
  "module": "POS服务订单",
  "case_type": "functional",
  "preconditions": "合同未对接服务周期；设备发货时间=2026-01-20；x=1、n=1（n为服务年限，定义与需求一致）",
  "remarks": "关联需求 REQ-POS-002 / FP-002 / 阻塞性假设n已确认",
  "priority": "critical",
  "test_data": {
   "合同号": "Contract008",
   "设备发货时间": "2026-01-20",
   "x": 1,
   "n": 1,
   "设备UPN": "UPN2026001",
   "设备序列号": "SN2026001"
  },
  "test_case_steps": [
   {
    "step": "使用未对接服务周期的合同创建POS订单并绑定设备",
    "result": "订单信息填写完成"
   },
   {
    "step": "提交订单并完成SAP对接",
    "result": "订单推送至SAP"
   },
   {
    "step": "查看推送SAP的服务截止时间",
    "result": "服务截止时间=2027-02-20（发货时间2026-01-20+1月+12月*1），格式YYYY-mm-DD"
   }
  ]
 },
 {
  "name": "服务周期计算-跨年边界值验证",
  "case_number": "TC-PR2-POS-009",
  "module": "POS服务订单",
  "case_type": "functional",
  "preconditions": "合同未对接服务周期；设备发货时间=2026-11-15；x=2、n=1",
  "remarks": "关联需求 REQ-POS-002 / FP-002 / 边界值",
  "priority": "critical",
  "test_data": {
   "合同号": "Contract009",
   "设备发货时间": "2026-11-15",
   "x": 2,
   "n": 1,
   "设备UPN": "UPN2026001",
   "设备序列号": "SN2026001"
  },
  "test_case_steps": [
   {
    "step": "使用未对接服务周期的合同创建POS订单并绑定设备",
    "result": "订单信息填写完成"
   },
   {
    "step": "提交订单并完成SAP对接",
    "result": "订单推送至SAP"
   },
   {
    "step": "查看服务起始时间与服务截止时间",
    "result": "服务起始时间=2027-01-15（2026-11-15跨年+2月），服务截止时间=2028-01-15（再+12月*1），日期进位正确无跨年偏差"
   }
  ]
 },
 {
  "name": "开票时间计算=对接SAP时间+1天",
  "case_number": "TC-PR2-POS-010",
  "module": "POS服务订单",
  "case_type": "functional",
  "preconditions": "订单已提交并进入SAP对接，对接SAP时间=2026-04-30",
  "remarks": "关联需求 REQ-POS-002 / FP-002",
  "priority": "high",
  "test_data": {
   "对接SAP时间": "2026-04-30",
   "服务开票时间格式": "YYYY-mm-DD"
  },
  "test_case_steps": [
   {
    "step": "完成订单SAP对接并记录对接时间",
    "result": "对接时间=2026-04-30"
   },
   {
    "step": "在DMS订单详情查看服务开票时间字段",
    "result": "服务开票时间=2026-05-01，格式为YYYY-mm-DD（对接时间+1天）"
   }
  ]
 },
 {
  "name": "周期维护一致性-仅维护服务周期未维护开票周期拒绝",
  "case_number": "TC-PR2-POS-011",
  "module": "POS服务订单",
  "case_type": "functional",
  "preconditions": "合同系统仅维护了服务周期（2026-05-01~2029-04-30）、未维护开票周期",
  "remarks": "关联需求 REQ-POS-002 / FP-002",
  "priority": "critical",
  "test_data": {
   "合同号": "Contract010",
   "服务周期": "2026-05-01~2029-04-30",
   "开票周期": "未维护"
  },
  "test_case_steps": [
   {
    "step": "使用仅维护服务周期的合同创建POS订单并绑定设备",
    "result": "订单信息填写完成"
   },
   {
    "step": "点击【提交订单】",
    "result": "系统拒绝创建订单，提示\"服务周期与开票周期必须同时维护或不维护\""
   }
  ]
 },
 {
  "name": "状态流转-已提交变更为已进入SAP",
  "case_number": "TC-PR2-POS-012",
  "module": "POS服务订单",
  "case_type": "functional",
  "preconditions": "订单ZCS2026050001已通过测试数据准备脚本创建成功，当前状态=已提交（独立准备，不依赖其他用例执行结果）",
  "remarks": "关联需求 REQ-POS-003 / FP-003 / 状态转换",
  "priority": "critical",
  "test_data": {
   "订单号": "ZCS2026050001",
   "初始状态": "已提交",
   "目标状态": "已进入SAP"
  },
  "test_case_steps": [
   {
    "step": "触发系统推送该订单至SAP",
    "result": "SAP对接接口返回成功"
   },
   {
    "step": "在DMS订单管理查询该订单状态",
    "result": "订单状态由\"已提交\"变更为\"已进入SAP\"，操作记录新增\"下载订单/已对接SAP\"记录"
   }
  ]
 },
 {
  "name": "状态流转-CC确认后已进入SAP变更为已确认",
  "case_number": "TC-PR2-POS-013",
  "module": "POS服务订单",
  "case_type": "functional",
  "preconditions": "订单ZCS2026050003已通过准备脚本创建并推送SAP，状态=已进入SAP；CC账号cc01已登录DMS（独立准备，不依赖其他用例执行结果）",
  "remarks": "关联需求 REQ-POS-003 / FP-003 / 状态转换",
  "priority": "critical",
  "test_data": {
   "订单号": "ZCS2026050003",
   "初始状态": "已进入SAP",
   "CC账号": "cc01"
  },
  "test_case_steps": [
   {
    "step": "CC账号cc01登录DMS，打开订单ZCS2026050003",
    "result": "订单详情正常展示"
   },
   {
    "step": "点击【确认】按钮完成订单确认",
    "result": "订单状态由\"已进入SAP\"变更为\"已确认\"，操作记录新增CC确认记录（操作人=cc01、操作内容=确认）"
   }
  ]
 },
 {
  "name": "状态流转-部分开票变更为完全开票",
  "case_number": "TC-PR2-POS-014",
  "module": "POS服务订单",
  "case_type": "functional",
  "preconditions": "订单ZCS2026050004已通过准备脚本创建并确认，状态=已确认；付款周期含3期（各1000.00）（独立准备，不依赖其他用例执行结果）",
  "remarks": "关联需求 REQ-POS-003 / FP-003 / 状态转换",
  "priority": "high",
  "test_data": {
   "订单号": "ZCS2026050004",
   "初始状态": "已确认",
   "开票期数": 3,
   "每期开票金额": 1000.0
  },
  "test_case_steps": [
   {
    "step": "SAP回传第1期开票信息",
    "result": "DMS订单状态变更为\"部分开票\""
   },
   {
    "step": "SAP回传第2期、第3期开票信息",
    "result": "3期全部开票后，DMS订单状态变更为\"完全开票\""
   }
  ]
 },
 {
  "name": "SAP对接失败-DMS侧错误处理与状态保持",
  "case_number": "TC-PR2-POS-015",
  "module": "POS服务订单",
  "case_type": "functional",
  "preconditions": "SAP对接接口Mock配置为返回失败（网络超时/业务拒绝）；订单ZCS2026050002已通过准备脚本创建，状态=已提交（独立准备，不依赖其他用例执行结果）",
  "remarks": "关联需求 REQ-POS-003 / FP-003 / SAP内部处理不测",
  "priority": "high",
  "test_data": {
   "订单号": "ZCS2026050002",
   "初始状态": "已提交",
   "SAP响应": "失败"
  },
  "test_case_steps": [
   {
    "step": "触发订单ZCS2026050002推送SAP",
    "result": "SAP对接接口返回失败"
   },
   {
    "step": "查看DMS侧订单状态与提示",
    "result": "订单状态保持\"已提交\"不变，系统展示可读的对接失败提示，支持重新推送；不验证SAP内部处理逻辑"
   }
  ]
 },
 {
  "name": "开票信息同步-部分开票状态与金额正确",
  "case_number": "TC-PR2-POS-016",
  "module": "POS服务订单",
  "case_type": "functional",
  "preconditions": "订单ZCS2026050005已通过准备脚本创建并确认；SAP回传第1期开票信息（开票周期2026-05-01~2027-04-30、金额1000.00、开票日期2026-05-30）（独立准备，不依赖其他用例执行结果）",
  "remarks": "关联需求 REQ-POS-004 / FP-004",
  "priority": "critical",
  "test_data": {
   "订单号": "ZCS2026050005",
   "开票周期": "2026-05-01~2027-04-30",
   "开票金额": 1000.0,
   "开票日期": "2026-05-30"
  },
  "test_case_steps": [
   {
    "step": "SAP回传第1期开票信息至DMS",
    "result": "同步成功"
   },
   {
    "step": "在DMS订单付款周期标签页查看第1期记录",
    "result": "第1期开票状态=已开票、开票金额=1000.00、开票日期=2026-05-30，其余2期保持未开票状态"
   }
  ]
 },
 {
  "name": "开票信息同步-完全开票状态与金额正确",
  "case_number": "TC-PR2-POS-017",
  "module": "POS服务订单",
  "case_type": "functional",
  "preconditions": "订单ZCS2026050006已通过准备脚本创建并确认；SAP回传全部3期开票信息，合计3000.00（独立准备，不依赖其他用例执行结果）",
  "remarks": "关联需求 REQ-POS-004 / FP-004",
  "priority": "high",
  "test_data": {
   "订单号": "ZCS2026050006",
   "开票期数": 3,
   "开票总额": 3000.0
  },
  "test_case_steps": [
   {
    "step": "SAP回传全部3期开票信息至DMS",
    "result": "同步成功"
   },
   {
    "step": "在DMS订单付款周期标签页查看全部期次",
    "result": "3期开票状态均为已开票，各期开票金额合计=3000.00，订单状态=完全开票"
   }
  ]
 },
 {
  "name": "开票信息同步-同步接口异常处理",
  "case_number": "TC-PR2-POS-018",
  "module": "POS服务订单",
  "case_type": "functional",
  "preconditions": "SAP开票回传接口Mock配置为超时；订单ZCS2026050007已通过准备脚本创建并确认，且3期均未开票（独立准备，不依赖其他用例执行结果）",
  "remarks": "关联需求 REQ-POS-004 / FP-004 / 异常场景",
  "priority": "high",
  "test_data": {
   "订单号": "ZCS2026050007",
   "同步接口响应": "超时",
   "开票初始状态": "未开票",
   "开票初始金额": 0.0
  },
  "test_case_steps": [
   {
    "step": "触发SAP开票信息同步",
    "result": "同步接口超时返回失败"
   },
   {
    "step": "查看DMS侧开票状态",
    "result": "各期开票状态保持\"未开票\"、金额保持0.00不变，无脏数据，系统提示同步失败可重试"
   },
   {
    "step": "恢复接口后重新同步",
    "result": "开票状态与金额正确更新，与SAP回传一致"
   }
  ]
 },
 {
  "name": "GSMS服务周期回写-5条件全部匹配更新成功",
  "case_number": "TC-PR2-POS-019",
  "module": "POS服务订单",
  "case_type": "functional",
  "preconditions": "GSMS回写接口Mock可用；订单ZCS2026050008已通过准备脚本创建（独立准备，不依赖其他用例执行结果）",
  "remarks": "关联需求 REQ-POS-005 / FP-005",
  "priority": "high",
  "test_data": {
   "服务订单编号": "ZCS2026050008",
   "设备产品编号": "AAAA",
   "设备批号": "B202601",
   "设备序列号": "SN2026001",
   "POS服务UPN编号": "UPN2026001",
   "GSMS回写服务起始": "2026-06-01",
   "GSMS回写服务截止": "2029-05-31"
  },
  "test_case_steps": [
   {
    "step": "GSMS回传实际维保效期（5条件全部匹配）",
    "result": "回写请求送达DMS"
   },
   {
    "step": "查询DMS中该订单服务周期",
    "result": "DMS服务起始时间=2026-06-01、服务截止时间=2029-05-31，已更新为GSMS回写值，回写结果返回成功"
   }
  ]
 },
 {
  "name": "GSMS服务周期回写-5条件部分匹配不更新（批号不匹配）",
  "case_number": "TC-PR2-POS-020",
  "module": "POS服务订单",
  "case_type": "functional",
  "preconditions": "GSMS回写接口Mock可用；订单ZCS2026050009已通过准备脚本创建，设备批号B999999不存在于该订单（独立准备，不依赖其他用例执行结果）",
  "remarks": "关联需求 REQ-POS-005 / FP-005 / 数据一致性",
  "priority": "medium",
  "test_data": {
   "服务订单编号": "ZCS2026050009",
   "设备产品编号": "AAAA",
   "设备批号": "B999999",
   "设备序列号": "SN2026001",
   "POS服务UPN编号": "UPN2026001"
  },
  "test_case_steps": [
   {
    "step": "GSMS回传维保效期（设备批号B999999不匹配）",
    "result": "回写请求送达DMS"
   },
   {
    "step": "查询DMS中该订单服务周期",
    "result": "服务周期保持原值不变，回写结果返回\"匹配失败/未更新\"提示，无部分更新产生脏数据"
   }
  ]
 },
 {
  "name": "服务周期计算-x=0边界值验证",
  "case_number": "TC-PR2-POS-021",
  "module": "POS服务订单",
  "case_type": "functional",
  "preconditions": "合同未对接服务周期；设备发货时间=2026-01-20；x=0、n=1",
  "remarks": "关联需求 REQ-POS-002 / FP-002 / 边界值补充",
  "priority": "high",
  "test_data": {
   "合同号": "Contract021",
   "设备发货时间": "2026-01-20",
   "x": 0,
   "n": 1,
   "设备UPN": "UPN2026001",
   "设备序列号": "SN2026001"
  },
  "test_case_steps": [
   {
    "step": "使用未对接服务周期的合同创建POS订单并绑定设备",
    "result": "订单信息填写完成"
   },
   {
    "step": "提交订单并完成SAP对接",
    "result": "订单推送至SAP"
   },
   {
    "step": "查看服务起始时间与服务截止时间",
    "result": "服务起始时间=2026-01-20（发货时间+0月=发货当天），服务截止时间=2027-01-20（+12月*1），x=0边界计算正确"
   }
  ]
 },
 {
  "name": "服务周期计算-月末日期进位边界验证",
  "case_number": "TC-PR2-POS-022",
  "module": "POS服务订单",
  "case_type": "functional",
  "preconditions": "合同未对接服务周期；设备发货时间=2026-01-31；x=1、n=1",
  "remarks": "关联需求 REQ-POS-002 / FP-002 / 边界值补充",
  "priority": "high",
  "test_data": {
   "合同号": "Contract022",
   "设备发货时间": "2026-01-31",
   "x": 1,
   "n": 1,
   "设备UPN": "UPN2026001",
   "设备序列号": "SN2026001"
  },
  "test_case_steps": [
   {
    "step": "使用未对接服务周期的合同创建POS订单并绑定设备",
    "result": "订单信息填写完成"
   },
   {
    "step": "提交订单并完成SAP对接",
    "result": "订单推送至SAP"
   },
   {
    "step": "查看服务起始时间",
    "result": "服务起始时间=2026-02-28（2026-01-31+1月，2月无31日自动进位至月末28日），月末进位正确"
   }
  ]
 },
 {
  "name": "开票时间计算-跨年+1天边界验证",
  "case_number": "TC-PR2-POS-023",
  "module": "POS服务订单",
  "case_type": "functional",
  "preconditions": "订单已提交并进入SAP对接，对接SAP时间=2026-12-31",
  "remarks": "关联需求 REQ-POS-002 / FP-002 / 边界值补充",
  "priority": "high",
  "test_data": {
   "对接SAP时间": "2026-12-31",
   "服务开票时间": "2027-01-01"
  },
  "test_case_steps": [
   {
    "step": "完成订单SAP对接并记录对接时间=2026-12-31",
    "result": "对接时间=2026-12-31"
   },
   {
    "step": "在DMS订单详情查看服务开票时间字段",
    "result": "服务开票时间=2027-01-01（12-31跨年+1天进位到次年1月1日），格式YYYY-mm-DD"
   }
  ]
 },
 {
  "name": "开票信息同步-DMS向SAP推送开票信息",
  "case_number": "TC-PR2-POS-024",
  "module": "POS服务订单",
  "case_type": "functional",
  "preconditions": "订单ZCS2026050010已确认；SAP开票接口Mock可记录调用请求；DMS侧开票信息可维护",
  "remarks": "关联需求 REQ-POS-004 / FP-004 / 双向同步补充",
  "priority": "critical",
  "test_data": {
   "订单号": "ZCS2026050010",
   "开票周期": "2026-05-01~2027-04-30",
   "开票金额": 1000.0,
   "同步方向": "DMS→SAP"
  },
  "test_case_steps": [
   {
    "step": "在DMS订单付款周期维护第1期开票信息（开票周期2026-05-01~2027-04-30、金额1000.00）",
    "result": "DMS侧开票信息保存成功"
   },
   {
    "step": "触发DMS向SAP推送开票信息",
    "result": "SAP接口Mock收到推送请求，请求体包含订单号ZCS2026050010、开票周期、金额1000.00，与DMS维护值一致"
   },
   {
    "step": "查看推送结果",
    "result": "推送返回成功，DMS记录同步状态=已同步，无数据丢失"
   }
  ]
 },
 {
  "name": "开票信息同步-开票金额为0边界处理",
  "case_number": "TC-PR2-POS-025",
  "module": "POS服务订单",
  "case_type": "functional",
  "preconditions": "订单ZCS2026050011已确认；SAP回传开票金额=0.00",
  "remarks": "关联需求 REQ-POS-004 / FP-004 / 边界值补充",
  "priority": "high",
  "test_data": {
   "订单号": "ZCS2026050011",
   "开票金额": 0.0
  },
  "test_case_steps": [
   {
    "step": "SAP回传第1期开票信息（开票金额0.00）至DMS",
    "result": "同步请求送达DMS"
   },
   {
    "step": "查看DMS侧该期开票记录",
    "result": "系统拒绝同步0金额开票，返回明确错误提示\"开票金额不能为0\"，该期开票状态保持未开票不变，无脏数据"
   }
  ]
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 10. ws-test_cases_login

- 来源：`workspace/testcase/test_cases_login.jsonl`　分组：(旧样本)　用例数：25

```json
[
 {
  "name": "登录成功-正确的用户名和密码",
  "case_number": "TC-PROJECT-LOGIN-001",
  "module": "用户登录",
  "case_type": "functional",
  "preconditions": "用户账号已注册且状态正常",
  "remarks": "REQ-LOGIN-001",
  "test_data": {
   "username": "test_user_01",
   "password": "ValidP@ss123",
   "expected_login_result": "成功"
  },
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "访问登录页面",
    "result": "显示用户名和密码输入框及登录按钮"
   },
   {
    "step": "输入已注册的用户名：test_user_01",
    "result": "输入框正确显示输入内容"
   },
   {
    "step": "输入正确密码：ValidP@ss123",
    "result": "密码以掩码形式显示"
   },
   {
    "step": "点击「登录」按钮",
    "result": "页面显示登录成功，跳转至系统首页/仪表盘"
   },
   {
    "step": "验证首页是否显示已登录用户信息",
    "result": "页面右上角显示用户头像/用户名，确认已登录状态"
   }
  ]
 },
 {
  "name": "登录成功-手机号+验证码登录",
  "case_number": "TC-PROJECT-LOGIN-002",
  "module": "用户登录",
  "case_type": "functional",
  "preconditions": "手机号已注册且绑定账号",
  "remarks": "REQ-LOGIN-002",
  "test_data": {
   "phone": "13800138000",
   "verification_code": "888888",
   "expected_login_result": "成功"
  },
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "访问登录页面，切换到「短信验证码登录」选项卡",
    "result": "显示手机号输入框和「获取验证码」按钮"
   },
   {
    "step": "输入已注册的手机号：13800138000",
    "result": "输入框正确显示"
   },
   {
    "step": "点击「获取验证码」按钮",
    "result": "收到短信验证码，按钮倒计时60秒"
   },
   {
    "step": "输入收到的有效验证码（示例：888888）",
    "result": "验证码输入框显示6位数字"
   },
   {
    "step": "点击「登录」按钮",
    "result": "页面显示登录成功，跳转至系统首页"
   }
  ]
 },
 {
  "name": "登录成功-勾选记住我保持登录状态",
  "case_number": "TC-PROJECT-LOGIN-003",
  "module": "用户登录",
  "case_type": "functional",
  "preconditions": "用户账号已注册，浏览器Cookie支持",
  "remarks": "REQ-LOGIN-003",
  "test_data": {
   "username": "test_user_01",
   "password": "ValidP@ss123",
   "remember_me": true
  },
  "priority": "high",
  "test_case_steps": [
   {
    "step": "访问登录页面",
    "result": "显示「记住我」复选框"
   },
   {
    "step": "勾选「记住我」复选框",
    "result": "复选框显示为选中状态"
   },
   {
    "step": "输入正确用户名和密码，点击登录",
    "result": "登录成功，跳转至首页"
   },
   {
    "step": "关闭浏览器并重新打开，再次访问需登录页面或首页",
    "result": "页面自动保持登录状态，无需重新输入凭据"
   },
   {
    "step": "验证Cookie中的登录Token有效期",
    "result": "Token有效期符合预期（如7天或30天）"
   }
  ]
 },
 {
  "name": "登录失败-密码错误",
  "case_number": "TC-PROJECT-LOGIN-004",
  "module": "用户登录",
  "case_type": "functional",
  "preconditions": "用户账号已注册，密码为 ValidP@ss123",
  "remarks": "REQ-LOGIN-001",
  "test_data": {
   "username": "test_user_01",
   "password": "WrongP@ss456",
   "expected_error": "密码错误提示"
  },
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "访问登录页面",
    "result": "登录页面正常显示"
   },
   {
    "step": "输入正确用户名：test_user_01",
    "result": "输入正确"
   },
   {
    "step": "输入错误密码：WrongP@ss456",
    "result": "输入完成"
   },
   {
    "step": "点击「登录」按钮",
    "result": "登录失败，页面显示错误提示「密码错误」或「用户名或密码不正确」"
   },
   {
    "step": "确认未跳转到首页，仍停留在登录页",
    "result": "仍停留在登录页面"
   }
  ]
 },
 {
  "name": "登录失败-用户名不存在",
  "case_number": "TC-PROJECT-LOGIN-005",
  "module": "用户登录",
  "case_type": "functional",
  "preconditions": "系统中不存在 never_registered_user 账号",
  "remarks": "REQ-LOGIN-001",
  "test_data": {
   "username": "never_registered_user",
   "password": "SomeP@ss123",
   "expected_error": "用户名不存在提示"
  },
  "priority": "high",
  "test_case_steps": [
   {
    "step": "访问登录页面",
    "result": "登录页面正常显示"
   },
   {
    "step": "输入未注册的用户名：never_registered_user",
    "result": "输入正确"
   },
   {
    "step": "输入任意密码：SomeP@ss123",
    "result": "输入完成"
   },
   {
    "step": "点击「登录」按钮",
    "result": "登录失败，提示「用户名或密码不正确」（不明确提示哪个字段错误，防枚举攻击）"
   }
  ]
 },
 {
  "name": "登录失败-用户名为空",
  "case_number": "TC-PROJECT-LOGIN-006",
  "module": "用户登录",
  "case_type": "functional",
  "preconditions": "无",
  "remarks": "REQ-LOGIN-001",
  "test_data": {
   "username": "",
   "password": "ValidP@ss123",
   "expected_error": "请输入用户名提示"
  },
  "priority": "high",
  "test_case_steps": [
   {
    "step": "访问登录页面",
    "result": "登录页面正常显示"
   },
   {
    "step": "将用户名输入框留空",
    "result": "输入框为空"
   },
   {
    "step": "输入正确密码",
    "result": "输入完成"
   },
   {
    "step": "点击「登录」按钮",
    "result": "页面提示「请输入用户名」或「用户名不能为空」，登录未执行"
   }
  ]
 },
 {
  "name": "登录失败-密码为空",
  "case_number": "TC-PROJECT-LOGIN-007",
  "module": "用户登录",
  "case_type": "functional",
  "preconditions": "无",
  "remarks": "REQ-LOGIN-001",
  "test_data": {
   "username": "test_user_01",
   "password": "",
   "expected_error": "请输入密码提示"
  },
  "priority": "high",
  "test_case_steps": [
   {
    "step": "访问登录页面",
    "result": "登录页面正常显示"
   },
   {
    "step": "输入正确用户名：test_user_01",
    "result": "输入正确"
   },
   {
    "step": "密码输入框留空",
    "result": "密码框为空"
   },
   {
    "step": "点击「登录」按钮",
    "result": "页面提示「请输入密码」或「密码不能为空」，登录未执行"
   }
  ]
 },
 {
  "name": "登录失败-用户名和密码均为空",
  "case_number": "TC-PROJECT-LOGIN-008",
  "module": "用户登录",
  "case_type": "functional",
  "preconditions": "无",
  "remarks": "REQ-LOGIN-001",
  "test_data": {
   "username": "",
   "password": "",
   "expected_error": "请输入用户名和密码提示"
  },
  "priority": "medium",
  "test_case_steps": [
   {
    "step": "访问登录页面",
    "result": "登录页面正常显示"
   },
   {
    "step": "用户名和密码输入框均留空",
    "result": "两个输入框均为空"
   },
   {
    "step": "点击「登录」按钮",
    "result": "页面提示「请输入用户名」或「请输入用户名和密码」"
   }
  ]
 },
 {
  "name": "登录失败-连续5次密码错误触发账号锁定",
  "case_number": "TC-PROJECT-LOGIN-009",
  "module": "用户登录",
  "case_type": "functional",
  "preconditions": "用户 test_lock_user 已注册，登录错误次数可重置",
  "remarks": "REQ-LOGIN-004",
  "test_data": {
   "username": "test_lock_user",
   "password_attempts": [
    "Wrong1@34",
    "Wrong2@34",
    "Wrong3@34",
    "Wrong4@34",
    "Wrong5@34"
   ],
   "correct_password": "ValidP@ss123",
   "expected_result": "第5次失败后账号被锁定"
  },
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "使用 test_lock_user 和错误密码 Wrong1@34 登录第1次",
    "result": "登录失败：「密码错误」，剩余尝试次数减少"
   },
   {
    "step": "使用错误密码 Wrong2@34 登录第2次",
    "result": "登录失败，剩余尝试次数减少"
   },
   {
    "step": "使用错误密码 Wrong3@34 登录第3次",
    "result": "登录失败，剩余尝试次数减少"
   },
   {
    "step": "使用错误密码 Wrong4@34 登录第4次",
    "result": "登录失败，剩余尝试次数减少"
   },
   {
    "step": "使用错误密码 Wrong5@34 登录第5次",
    "result": "登录失败，提示「账号已被锁定，请30分钟后再试」或联系客服"
   },
   {
    "step": "立即使用正确密码 ValidP@ss123 尝试登录",
    "result": "登录失败，提示「账号已被锁定」，即使密码正确也无法登录"
   }
  ]
 },
 {
  "name": "登录失败-账号锁定状态下使用错误密码",
  "case_number": "TC-PROJECT-LOGIN-010",
  "module": "用户登录",
  "case_type": "functional",
  "preconditions": "账号 test_lock_user 已被锁定（连续5次密码错误）",
  "remarks": "REQ-LOGIN-004",
  "test_data": {
   "username": "test_lock_user",
   "password": "AnotherWrongP@ss",
   "expected_error": "账号已被锁定提示"
  },
  "priority": "high",
  "test_case_steps": [
   {
    "step": "确认账号 test_lock_user 处于锁定状态",
    "result": "系统记录该账号已锁定"
   },
   {
    "step": "输入 test_lock_user 和任意错误密码",
    "result": "输入完成"
   },
   {
    "step": "点击「登录」按钮",
    "result": "登录失败，提示「账号已被锁定，请在30分钟后重试」或「联系客服解锁」"
   }
  ]
 },
 {
  "name": "登录成功-锁定时间到期后自动解锁",
  "case_number": "TC-PROJECT-LOGIN-011",
  "module": "用户登录",
  "case_type": "functional",
  "preconditions": "账号 test_lock_user 已被锁定，锁定时间已过30分钟",
  "remarks": "REQ-LOGIN-004",
  "test_data": {
   "username": "test_lock_user",
   "password": "ValidP@ss123",
   "expected_login_result": "成功"
  },
  "priority": "high",
  "test_case_steps": [
   {
    "step": "确认账号 test_lock_user 的锁定时间已超过30分钟",
    "result": "系统记录的锁定状态已过期"
   },
   {
    "step": "输入 test_lock_user 和正确密码 ValidP@ss123",
    "result": "输入正确"
   },
   {
    "step": "点击「登录」按钮",
    "result": "登录成功，跳转至首页，账号锁定状态已自动解除"
   },
   {
    "step": "验证锁定计数器已重置为0",
    "result": "下次错误登录从第1次开始计数"
   }
  ]
 },
 {
  "name": "安全测试-SQL注入尝试绕过登录",
  "case_number": "TC-PROJECT-LOGIN-012",
  "module": "用户登录",
  "case_type": "security",
  "preconditions": "登录页面未做输入过滤",
  "remarks": "REQ-LOGIN-SEC-001",
  "test_data": {
   "username": "admin' OR '1'='1",
   "password": "admin' OR '1'='1",
   "expected_result": "防止SQL注入，登录失败"
  },
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "访问登录页面",
    "result": "登录页面正常显示"
   },
   {
    "step": "在用户名输入框中输入SQL注入语句：admin' OR '1'='1",
    "result": "输入被正确转义或过滤"
   },
   {
    "step": "在密码输入框中输入SQL注入语句：admin' OR '1'='1",
    "result": "输入被正确转义或过滤"
   },
   {
    "step": "点击「登录」按钮",
    "result": "登录失败，不应绕过认证；系统未返回SQL错误信息"
   }
  ]
 },
 {
  "name": "安全测试-XSS攻击尝试",
  "case_number": "TC-PROJECT-LOGIN-013",
  "module": "用户登录",
  "case_type": "security",
  "preconditions": "登录页面未做XSS过滤",
  "remarks": "REQ-LOGIN-SEC-001",
  "test_data": {
   "username": "<script>alert('XSS')</script>",
   "password": "test123",
   "expected_result": "XSS脚本被转义，不执行"
  },
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "访问登录页面",
    "result": "登录页面正常显示"
   },
   {
    "step": "在用户名输入框中输入XSS脚本：<script>alert('XSS')</script>",
    "result": "输入框显示文本内容，脚本未被执行"
   },
   {
    "step": "在密码框中输入任意密码",
    "result": "输入完成"
   },
   {
    "step": "点击「登录」按钮",
    "result": "登录失败，返回的页面上不应弹出alert弹窗，XSS脚本被HTML转义处理"
   },
   {
    "step": "检查页面源码确认脚本被转义",
    "result": "<script>标签被转义为 &lt;script&gt;"
   }
  ]
 },
 {
  "name": "安全测试-SQL注入-Union查询尝试",
  "case_number": "TC-PROJECT-LOGIN-014",
  "module": "用户登录",
  "case_type": "security",
  "preconditions": "登录页面存在用户名字段",
  "remarks": "REQ-LOGIN-SEC-001",
  "test_data": {
   "username": "admin' UNION SELECT * FROM users--",
   "password": "any",
   "expected_result": "防止SQL注入，登录失败"
  },
  "priority": "high",
  "test_case_steps": [
   {
    "step": "访问登录页面",
    "result": "登录页面正常显示"
   },
   {
    "step": "输入SQL Union注入语句：admin' UNION SELECT * FROM users--",
    "result": "输入正常显示"
   },
   {
    "step": "输入任意密码",
    "result": "输入完成"
   },
   {
    "step": "点击「登录」按钮",
    "result": "登录失败，不应返回数据库数据"
   }
  ]
 },
 {
  "name": "密码长度边界-最小长度（如6位）",
  "case_number": "TC-PROJECT-LOGIN-015",
  "module": "用户登录",
  "case_type": "functional",
  "preconditions": "系统密码策略要求最少6位",
  "remarks": "REQ-LOGIN-005",
  "test_data": {
   "username": "test_user_01",
   "password": "Ab1@x",
   "expected_error": "密码长度不足提示"
  },
  "priority": "high",
  "test_case_steps": [
   {
    "step": "访问登录页面",
    "result": "登录页面正常显示"
   },
   {
    "step": "输入已注册用户名：test_user_01",
    "result": "输入正确"
   },
   {
    "step": "输入5位密码（最小长度6位以下）：Ab1@x",
    "result": "输入完成"
   },
   {
    "step": "点击「登录」按钮",
    "result": "若为注册/修改密码页，提示「密码长度不能少于6位」；若为登录页，验证该账号密码有效性（登录失败）"
   }
  ]
 },
 {
  "name": "密码长度边界-最小长度临界值（如6位）",
  "case_number": "TC-PROJECT-LOGIN-016",
  "module": "用户登录",
  "case_type": "functional",
  "preconditions": "系统允许6位密码且该账号密码为6位",
  "remarks": "REQ-LOGIN-005",
  "test_data": {
   "username": "test_user_short",
   "password": "A1b@2x",
   "expected_login_result": "登录成功（若密码匹配）"
  },
  "priority": "medium",
  "test_case_steps": [
   {
    "step": "访问登录页面",
    "result": "登录页面正常显示"
   },
   {
    "step": "输入用户名为 test_user_short（密码长度为6位）",
    "result": "输入正确"
   },
   {
    "step": "输入密码 A1b@2x",
    "result": "输入完成"
   },
   {
    "step": "点击「登录」按钮",
    "result": "若密码正确则登录成功，证明6位密码被系统接受"
   }
  ]
 },
 {
  "name": "密码长度边界-最大长度（如20位）",
  "case_number": "TC-PROJECT-LOGIN-017",
  "module": "用户登录",
  "case_type": "functional",
  "preconditions": "系统密码策略允许20位，注册时已设置20位密码",
  "remarks": "REQ-LOGIN-005",
  "test_data": {
   "username": "test_user_long",
   "password": "A1b@2xCDEFGhijklmnO",
   "expected_login_result": "登录成功（若密码匹配）"
  },
  "priority": "medium",
  "test_case_steps": [
   {
    "step": "访问登录页面",
    "result": "登录页面正常显示"
   },
   {
    "step": "输入用户名为 test_user_long",
    "result": "输入正确"
   },
   {
    "step": "输入20位密码 A1b@2xCDEFGhijklmnO",
    "result": "输入框正常显示，未截断"
   },
   {
    "step": "点击「登录」按钮",
    "result": "若密码正确则登录成功，证明20位密码被系统正常处理"
   }
  ]
 },
 {
  "name": "密码长度边界-超过最大长度（如21位）",
  "case_number": "TC-PROJECT-LOGIN-018",
  "module": "用户登录",
  "case_type": "functional",
  "preconditions": "系统密码策略最大长度20位",
  "remarks": "REQ-LOGIN-005",
  "test_data": {
   "username": "test_user_long",
   "password": "A1b@2xCDEFGhijklmnOPQ",
   "expected_result": "系统截断或拒绝"
  },
  "priority": "medium",
  "test_case_steps": [
   {
    "step": "访问登录页面",
    "result": "登录页面正常显示"
   },
   {
    "step": "输入用户名 test_user_long",
    "result": "输入正确"
   },
   {
    "step": "输入21位密码 A1b@2xCDEFGhijklmnOPQ",
    "result": "输入框可能阻止输入超过20位，或允许输入但后端会处理"
   },
   {
    "step": "点击「登录」按钮",
    "result": "系统按密码策略处理（截断/拒绝），不应出现系统异常"
   }
  ]
 },
 {
  "name": "安全测试-密码暴力破解防护-短时间大量尝试",
  "case_number": "TC-PROJECT-LOGIN-019",
  "module": "用户登录",
  "case_type": "security",
  "preconditions": "系统具有防暴力破解机制",
  "remarks": "REQ-LOGIN-SEC-002",
  "test_data": {
   "username": "test_user_01",
   "password_attempts": "每秒1次持续20次",
   "expected_result": "IP或账号被临时限制"
  },
  "priority": "high",
  "test_case_steps": [
   {
    "step": "准备暴力破解脚本（或手动快速操作），以每秒1次的速度使用不同错误密码连续登录",
    "result": "前几次返回密码错误"
   },
   {
    "step": "持续登录10次左右",
    "result": "系统开始显示验证码或延迟响应"
   },
   {
    "step": "持续登录到15次以上",
    "result": "IP地址或账号被临时封禁，提示「操作过于频繁，请稍后再试」"
   },
   {
    "step": "使用正确密码尝试登录",
    "result": "登录仍然被阻止，需等待封禁时间到期"
   }
  ]
 },
 {
  "name": "Session管理-Token过期后访问需认证页面",
  "case_number": "TC-PROJECT-LOGIN-020",
  "module": "用户登录",
  "case_type": "security",
  "preconditions": "用户已登录，等待Session/Token过期",
  "remarks": "REQ-LOGIN-SEC-003",
  "test_data": {
   "username": "test_user_01",
   "password": "ValidP@ss123",
   "session_timeout": "30分钟",
   "expected_result": "重定向到登录页"
  },
  "priority": "high",
  "test_case_steps": [
   {
    "step": "使用有效凭据登录系统",
    "result": "登录成功，获得Session/Token"
   },
   {
    "step": "等待Session/Token过期（如30分钟）",
    "result": "Session/Token在服务端过期"
   },
   {
    "step": "在过期状态下尝试访问需要登录认证的页面（如个人中心）",
    "result": "请求被拒绝，重定向到登录页面"
   },
   {
    "step": "使用已过期的Token调用API接口",
    "result": "返回401 Unauthorized或Token过期错误"
   }
  ]
 },
 {
  "name": "登出功能-Token失效",
  "case_number": "TC-PROJECT-LOGIN-021",
  "module": "用户登录",
  "case_type": "functional",
  "preconditions": "用户已登录",
  "remarks": "REQ-LOGIN-006",
  "test_data": {
   "username": "test_user_01",
   "password": "ValidP@ss123",
   "expected_result": "登出后Token失效"
  },
  "priority": "high",
  "test_case_steps": [
   {
    "step": "登录系统成功",
    "result": "登录成功，获得有效Token"
   },
   {
    "step": "点击右上角「退出登录」/「登出」",
    "result": "页面提示确认或直接登出，跳转回登录页"
   },
   {
    "step": "使用已登出的Token调用需要认证的API",
    "result": "API返回401 Unauthorized，Token已失效"
   },
   {
    "step": "在浏览器直接点击「后退」按钮",
    "result": "页面不展示已登录的内容，或显示登录页面"
   }
  ]
 },
 {
  "name": "登录安全-传输加密（HTTPS强制检查）",
  "case_number": "TC-PROJECT-LOGIN-022",
  "module": "用户登录",
  "case_type": "security",
  "preconditions": "系统应强制HTTPS",
  "remarks": "REQ-LOGIN-SEC-004",
  "test_data": {
   "request_type": "HTTP重定向",
   "expected_result": "强制使用HTTPS"
  },
  "priority": "high",
  "test_case_steps": [
   {
    "step": "使用HTTP协议（而非HTTPS）访问登录页面",
    "result": "自动重定向到HTTPS版本的URL"
   },
   {
    "step": "检查登录请求的协议",
    "result": "所有登录请求均使用HTTPS加密传输"
   },
   {
    "step": "检查登录请求Payload",
    "result": "用户名和密码在传输过程中加密，不可明文读取"
   }
  ]
 },
 {
  "name": "登录失败-验证码错误",
  "case_number": "TC-PROJECT-LOGIN-023",
  "module": "用户登录",
  "case_type": "functional",
  "preconditions": "存在验证码机制，手机号13800138000已注册",
  "remarks": "REQ-LOGIN-002",
  "test_data": {
   "phone": "13800138000",
   "verification_code": "000000",
   "expected_error": "验证码错误提示"
  },
  "priority": "high",
  "test_case_steps": [
   {
    "step": "切换到短信验证码登录",
    "result": "显示手机号和验证码输入框"
   },
   {
    "step": "输入已注册手机号：13800138000",
    "result": "输入完成"
   },
   {
    "step": "点击「获取验证码」",
    "result": "收到6位短信验证码"
   },
   {
    "step": "输入错误的验证码：000000（假设正确码为888888）",
    "result": "输入完成"
   },
   {
    "step": "点击「登录」按钮",
    "result": "登录失败，提示「验证码错误」或「验证码不正确」"
   }
  ]
 },
 {
  "name": "登录失败-验证码过期重试",
  "case_number": "TC-PROJECT-LOGIN-024",
  "module": "用户登录",
  "case_type": "functional",
  "preconditions": "手机号13800138000已注册，验证码有效期5分钟",
  "remarks": "REQ-LOGIN-002",
  "test_data": {
   "phone": "13800138000",
   "wait_time": "5分钟+1秒",
   "expected_error": "验证码已过期"
  },
  "priority": "high",
  "test_case_steps": [
   {
    "step": "切换到短信验证码登录",
    "result": "显示手机号和验证码输入框"
   },
   {
    "step": "输入手机号并点击获取验证码",
    "result": "收到验证码888888"
   },
   {
    "step": "等待超过5分钟有效期（5分1秒）",
    "result": "验证码在服务端已过期"
   },
   {
    "step": "输入原验证码888888并点击登录",
    "result": "登录失败，提示「验证码已过期，请重新获取」"
   }
  ]
 },
 {
  "name": "登录失败-密码含前导空格/尾部空格",
  "case_number": "TC-PROJECT-LOGIN-025",
  "module": "用户登录",
  "case_type": "functional",
  "preconditions": "用户密码为 ValidP@ss123，系统处理空格策略",
  "remarks": "REQ-LOGIN-005",
  "test_data": {
   "username": "test_user_01",
   "password": " ValidP@ss123",
   "expected_result": "取决于系统策略"
  },
  "priority": "medium",
  "test_case_steps": [
   {
    "step": "访问登录页面",
    "result": "登录页面正常显示"
   },
   {
    "step": "输入正确用户名",
    "result": "输入正确"
   },
   {
    "step": "在正确密码前加一个空格： ValidP@ss123",
    "result": "输入完成"
   },
   {
    "step": "点击「登录」按钮",
    "result": "若系统自动trim空格，则登录成功；否则登录失败"
   },
   {
    "step": "若失败，在密码后加一个空格再测试",
    "result": "验证系统对空格的处理策略是否前后一致"
   }
  ]
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 11. ws-PR-1-test_cases_module_01_login

- 来源：`workspace/testcase/PR-1/test_cases_module_01_login.jsonl`　分组：PR-1　用例数：27

```json
[
 {
  "name": "有效手机号可发送验证码",
  "case_number": "TC-PR1-LOGIN-001",
  "module": "手机号验证码登录",
  "case_type": "functional",
  "preconditions": "登录页已加载，短信服务可用",
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "在手机号输入框输入 13812345678",
    "result": "输入框允许输入11位数字，无格式错误提示"
   },
   {
    "step": "点击\"获取验证码\"按钮",
    "result": "返回\"验证码已发送\"提示，按钮进入60秒倒计时并显示\"60s后重新获取\""
   }
  ],
  "test_data": {
   "手机号": "13812345678"
  },
  "remarks": "FP-001 需求FR-01规则1"
 },
 {
  "name": "10位手机号格式校验拒绝",
  "case_number": "TC-PR1-LOGIN-002",
  "module": "手机号验证码登录",
  "case_type": "functional",
  "preconditions": "登录页已加载",
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "在手机号输入框输入 10 位数字 1381234567",
    "result": "输入框下方提示\"请输入正确的手机号\""
   },
   {
    "step": "观察\"获取验证码\"按钮状态",
    "result": "登录/获取验证码按钮保持置灰不可点击，未发出任何发送请求"
   }
  ],
  "test_data": {
   "手机号": "1381234567",
   "位数": 10
  },
  "remarks": "FP-001 边界值min-1 需求FR-01规则1"
 },
 {
  "name": "12位手机号格式校验拒绝",
  "case_number": "TC-PR1-LOGIN-003",
  "module": "手机号验证码登录",
  "case_type": "functional",
  "preconditions": "登录页已加载",
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "在手机号输入框输入 12 位数字 138123456789",
    "result": "输入框下方提示\"请输入正确的手机号\""
   },
   {
    "step": "观察\"获取验证码\"按钮状态",
    "result": "按钮保持置灰不可点击，未发出任何发送请求"
   }
  ],
  "test_data": {
   "手机号": "138123456789",
   "位数": 12
  },
  "remarks": "FP-001 边界值max+1 需求FR-01规则1"
 },
 {
  "name": "非3-9号段手机号校验拒绝",
  "case_number": "TC-PR1-LOGIN-004",
  "module": "手机号验证码登录",
  "case_type": "functional",
  "preconditions": "登录页已加载",
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "在手机号输入框输入第2位为2的手机号 12812345678",
    "result": "输入框下方提示\"请输入正确的手机号\""
   },
   {
    "step": "观察\"获取验证码\"按钮状态",
    "result": "按钮保持置灰不可点击，未发出任何发送请求"
   }
  ],
  "test_data": {
   "手机号": "12812345678",
   "第2位": "2(不在3-9范围)"
  },
  "remarks": "FP-001 需求FR-01规则1"
 },
 {
  "name": "含字母或特殊字符手机号校验拒绝",
  "case_number": "TC-PR1-LOGIN-005",
  "module": "手机号验证码登录",
  "case_type": "functional",
  "preconditions": "登录页已加载",
  "priority": "high",
  "test_case_steps": [
   {
    "step": "依次输入含字母的 1381234567a 和含特殊字符的 13812345#67",
    "result": "每次输入后提示\"请输入正确的手机号\"，按钮保持置灰"
   }
  ],
  "test_data": {
   "手机号1": "1381234567a",
   "手机号2": "13812345#67"
  },
  "remarks": "FP-001 需求FR-01规则1"
 },
 {
  "name": "手机号输入SQL注入与XSS攻击防护",
  "case_number": "TC-PR1-LOGIN-006",
  "module": "手机号验证码登录",
  "case_type": "security",
  "preconditions": "登录页已加载，抓包工具可用",
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "在手机号输入框分别输入 '; DROP TABLE users; -- 和 <script>alert(1)</script> 并尝试提交",
    "result": "均被格式校验拦截并提示\"请输入正确的手机号\"，不向后端发起发送请求"
   },
   {
    "step": "通过抓包工具直接向发送接口提交上述注入串",
    "result": "接口返回参数校验错误，响应体不包含SQL错误信息，数据库无异常变更"
   },
   {
    "step": "检查页面源码",
    "result": "页面无脚本执行，XSS载荷被过滤或转义"
   }
  ],
  "test_data": {
   "SQL注入载荷": "'; DROP TABLE users; --",
   "XSS载荷": "<script>alert(1)</script>"
  },
  "remarks": "FP-001 安全 需求FR-01规则1"
 },
 {
  "name": "首次发送验证码成功并进入60秒倒计时",
  "case_number": "TC-PR1-LOGIN-007",
  "module": "手机号验证码登录",
  "case_type": "functional",
  "preconditions": "手机号13912345678当日发送次数为0，60秒内未发送过",
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "输入手机号13912345678并点击\"获取验证码\"",
    "result": "提示\"验证码已发送\"，短信网关收到发送请求"
   },
   {
    "step": "观察按钮状态",
    "result": "按钮变为\"60s后重新获取\"并逐秒倒计时，倒计时期间不可再次点击"
   }
  ],
  "test_data": {
   "手机号": "13912345678",
   "当日已发送次数": 0
  },
  "remarks": "FP-002 需求FR-01规则3"
 },
 {
  "name": "60秒内重复发送验证码被拦截",
  "case_number": "TC-PR1-LOGIN-008",
  "module": "手机号验证码登录",
  "case_type": "functional",
  "preconditions": "手机号13912345678已在30秒前发送过验证码，倒计时进行中",
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "倒计时未结束时再次点击\"获取验证码\"",
    "result": "按钮不可点击（置灰），提示\"发送过于频繁，请稍后再试\""
   },
   {
    "step": "检查短信网关接收记录",
    "result": "无新的验证码发送记录"
   }
  ],
  "test_data": {
   "手机号": "13912345678",
   "两次发送间隔": "30秒"
  },
  "remarks": "FP-002 需求FR-01规则3"
 },
 {
  "name": "倒计时结束后可再次发送验证码",
  "case_number": "TC-PR1-LOGIN-009",
  "module": "手机号验证码登录",
  "case_type": "functional",
  "preconditions": "手机号13912345678已发送过验证码且倒计时已结束",
  "priority": "high",
  "test_case_steps": [
   {
    "step": "等待倒计时归零后点击\"获取验证码\"",
    "result": "按钮恢复可点击，点击后提示\"验证码已发送\"，倒计时重新开始"
   },
   {
    "step": "检查短信网关接收记录",
    "result": "收到新的验证码发送记录"
   }
  ],
  "test_data": {
   "手机号": "13912345678",
   "等待时长": "61秒"
  },
  "remarks": "FP-002 需求FR-01规则3"
 },
 {
  "name": "同一手机号当日第10次发送成功、第11次超限",
  "case_number": "TC-PR1-LOGIN-010",
  "module": "手机号验证码登录",
  "case_type": "functional",
  "preconditions": "手机号17012340001当日已发送9次验证码",
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "第10次点击\"获取验证码\"",
    "result": "发送成功，提示\"验证码已发送\""
   },
   {
    "step": "立即第11次点击\"获取验证码\"",
    "result": "提示\"发送过于频繁，请稍后再试\"，短信网关无新发送记录"
   }
  ],
  "test_data": {
   "手机号": "17012340001",
   "当日已发送次数": "9次(第10次为边界内最后一次)"
  },
  "remarks": "FP-002 边界值max=max 需求FR-01规则3"
 },
 {
  "name": "同一IP当日第51次发送超限拦截",
  "case_number": "TC-PR1-LOGIN-011",
  "module": "手机号验证码登录",
  "case_type": "functional",
  "preconditions": "测试IP 203.0.113.1 当日已发送50次验证码，短信服务可用",
  "priority": "high",
  "test_case_steps": [
   {
    "step": "使用IP 203.0.113.1 发起第51次验证码发送请求（换用另一手机号）",
    "result": "接口返回限流提示\"发送过于频繁，请稍后再试\"，短信网关无新发送记录"
   },
   {
    "step": "检查该IP第50次发送是否成功",
    "result": "第50次发送正常成功（边界内不受影响）"
   }
  ],
  "test_data": {
   "IP": "203.0.113.1",
   "当日该IP已发送次数": 50
  },
  "remarks": "FP-002 边界值 需求FR-01规则3 默认假设4(以服务端公网IP计数)"
 },
 {
  "name": "单IP高频请求防短信轰炸",
  "case_number": "TC-PR1-LOGIN-012",
  "module": "手机号验证码登录",
  "case_type": "security",
  "preconditions": "抓包/压测工具可用，风控开关开启",
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "从单一IP 203.0.113.2 在1分钟内发起30次验证码发送请求（每次更换手机号）",
    "result": "请求被限流（返回429或触发图形验证码），实际下发短信数远低于请求数"
   },
   {
    "step": "检查风控日志",
    "result": "系统记录该IP被风控标记，后续请求需通过图形验证码"
   }
  ],
  "test_data": {
   "IP": "203.0.113.2",
   "1分钟内发送请求数": 30,
   "触发规则": "同IP 1分钟≥10次触发图形验证码"
  },
  "remarks": "FP-002 安全 需求FR-01规则3 目标1.2防短信轰炸"
 },
 {
  "name": "正确验证码登录成功",
  "case_number": "TC-PR1-LOGIN-013",
  "module": "手机号验证码登录",
  "case_type": "functional",
  "preconditions": "手机号13812345678已注册，刚获取验证码483920且在5分钟有效期内",
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "输入手机号13812345678和验证码483920，点击\"登录\"",
    "result": "登录成功，接口返回200且data.token非空"
   },
   {
    "step": "观察页面跳转",
    "result": "跳转至登录前页面或首页"
   }
  ],
  "test_data": {
   "手机号": "13812345678",
   "验证码": "483920",
   "验证码位数": 6
  },
  "remarks": "FP-003 FP-005 需求FR-01规则2"
 },
 {
  "name": "验证码位数不足或超长校验拒绝",
  "case_number": "TC-PR1-LOGIN-014",
  "module": "手机号验证码登录",
  "case_type": "functional",
  "preconditions": "登录页已加载，存在有效验证码",
  "priority": "high",
  "test_case_steps": [
   {
    "step": "依次输入5位验证码12345、7位验证码1234567、含字母的12345a",
    "result": "均提示\"请输入6位数字验证码\"，不发起登录校验请求"
   }
  ],
  "test_data": {
   "验证码1": "12345(5位)",
   "验证码2": "1234567(7位)",
   "验证码3": "12345a(含字母)"
  },
  "remarks": "FP-003 边界值 需求FR-01规则2"
 },
 {
  "name": "验证码超过5分钟有效期后登录失败",
  "case_number": "TC-PR1-LOGIN-015",
  "module": "手机号验证码登录",
  "case_type": "functional",
  "preconditions": "手机号13812345678已获取验证码483920，已等待301秒（超过5分钟）",
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "输入手机号和该过期验证码483920，点击\"登录\"",
    "result": "提示\"验证码已过期，请重新获取\"，登录失败，不返回token"
   }
  ],
  "test_data": {
   "手机号": "13812345678",
   "验证码": "483920",
   "生成后等待时长": "301秒(>5分钟)"
  },
  "remarks": "FP-003 边界值 需求FR-01规则2"
 },
 {
  "name": "验证码单次使用后再次使用被拒",
  "case_number": "TC-PR1-LOGIN-016",
  "module": "手机号验证码登录",
  "case_type": "functional",
  "preconditions": "验证码483920已被成功使用过一次完成登录",
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "登出后再次输入手机号13812345678和同一验证码483920并登录",
    "result": "提示\"验证码已失效或已被使用\"，登录失败，不返回token"
   }
  ],
  "test_data": {
   "手机号": "13812345678",
   "验证码": "483920",
   "使用次数": 2
  },
  "remarks": "FP-003 需求FR-01规则2"
 },
 {
  "name": "连续输错4次第5次输对验证码可登录",
  "case_number": "TC-PR1-LOGIN-017",
  "module": "手机号验证码登录",
  "case_type": "functional",
  "preconditions": "手机号13812345678已获取正确验证码483920",
  "priority": "high",
  "test_case_steps": [
   {
    "step": "连续输入错误验证码111111共4次并提交",
    "result": "每次提示\"验证码错误，剩余N次机会\"，剩余次数依次为4/3/2/1"
   },
   {
    "step": "第5次输入正确验证码483920并提交",
    "result": "登录成功，返回token并跳转目标页"
   }
  ],
  "test_data": {
   "错误验证码": "111111",
   "正确验证码": "483920",
   "错误次数": 4
  },
  "remarks": "FP-003 边界值max-1 需求FR-01规则4"
 },
 {
  "name": "连续输错5次验证码作废需重新获取",
  "case_number": "TC-PR1-LOGIN-018",
  "module": "手机号验证码登录",
  "case_type": "functional",
  "preconditions": "手机号13812345678已获取正确验证码483920",
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "连续输入错误验证码222222共5次并提交",
    "result": "第5次输错后提示\"验证码已作废，请重新获取\"，按钮引导重新发送"
   },
   {
    "step": "第6次输入正确验证码483920并提交",
    "result": "仍提示验证码已作废，登录失败，不返回token"
   }
  ],
  "test_data": {
   "错误验证码": "222222",
   "正确验证码": "483920",
   "错误次数": 5
  },
  "remarks": "FP-003 边界值max 需求FR-01规则4"
 },
 {
  "name": "验证码暴力枚举防护",
  "case_number": "TC-PR1-LOGIN-019",
  "module": "手机号验证码登录",
  "case_type": "security",
  "preconditions": "抓包/压测工具可用，手机号13812345678已获取验证码",
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "通过脚本在1分钟内对登录接口发起20次不同验证码的尝试",
    "result": "第6次起触发风控：接口返回限流错误或要求图形验证码，无法继续枚举"
   },
   {
    "step": "检查登录日志",
    "result": "20次尝试均被记录为失败登录，无一次成功"
   }
  ],
  "test_data": {
   "手机号": "13812345678",
   "1分钟内错误尝试次数": 20,
   "风控规则": "验证码连续输错5次作废+频率限制"
  },
  "remarks": "FP-003 安全 需求FR-01规则4 目标1.2防撞库"
 },
 {
  "name": "未注册手机号自动注册并登录成功",
  "case_number": "TC-PR1-LOGIN-020",
  "module": "手机号验证码登录",
  "case_type": "functional",
  "preconditions": "手机号17012340002从未注册，已获取有效验证码111222",
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "输入未注册手机号17012340002和验证码111222，点击登录",
    "result": "登录成功，返回token，跳转登录前页面或首页"
   },
   {
    "step": "查询用户表",
    "result": "用户表中新增一条该手机号账号记录，注册时间与登录时间一致"
   }
  ],
  "test_data": {
   "手机号": "17012340002",
   "验证码": "111222",
   "注册状态": "未注册(虚拟号段)"
  },
  "remarks": "FP-004 需求FR-01规则5"
 },
 {
  "name": "新用户登录成功后进入新手引导",
  "case_number": "TC-PR1-LOGIN-021",
  "module": "手机号验证码登录",
  "case_type": "functional",
  "preconditions": "手机号17012340003为新注册用户，已获取有效验证码333444",
  "priority": "high",
  "test_case_steps": [
   {
    "step": "新用户使用验证码登录成功",
    "result": "登录成功后跳转至新手引导页而非首页"
   },
   {
    "step": "完成新手引导后返回",
    "result": "返回后可正常进入首页，引导不再重复弹出"
   }
  ],
  "test_data": {
   "手机号": "17012340003",
   "验证码": "333444",
   "用户类型": "新用户"
  },
  "remarks": "FP-004 需求FR-01规则5"
 },
 {
  "name": "已注册用户重复登录不重复建号",
  "case_number": "TC-PR1-LOGIN-022",
  "module": "手机号验证码登录",
  "case_type": "functional",
  "preconditions": "手机号13812345678已注册，可正常获取验证码",
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "老用户登录成功后主动登出，再次登录同一手机号",
    "result": "两次均登录成功，返回token"
   },
   {
    "step": "查询用户表该手机号记录",
    "result": "仅存在一条账号记录，账号ID不变，未产生重复账号"
   }
  ],
  "test_data": {
   "手机号": "13812345678",
   "账号数量": "1"
  },
  "remarks": "FP-004 需求FR-01规则5"
 },
 {
  "name": "并发登录同一未注册手机号仅创建单一账号",
  "case_number": "TC-PR1-LOGIN-023",
  "module": "手机号验证码登录",
  "case_type": "functional",
  "preconditions": "手机号17012340004未注册，验证码可复用(测试环境放开单次限制或使用两条验证码), 并发工具可用",
  "priority": "high",
  "test_case_steps": [
   {
    "step": "同时发起2个相同手机号的登录请求",
    "result": "两个请求均返回登录成功，不返回冲突错误"
   },
   {
    "step": "查询用户表该手机号记录",
    "result": "仅新增一条账号记录，无重复账号、无半注册状态"
   }
  ],
  "test_data": {
   "手机号": "17012340004",
   "并发请求数": 2
  },
  "remarks": "FP-004 并发一致性 需求FR-01规则5 风险2.3自动注册一致性"
 },
 {
  "name": "登录成功返回token并跳转登录前页面",
  "case_number": "TC-PR1-LOGIN-024",
  "module": "手机号验证码登录",
  "case_type": "functional",
  "preconditions": "已登录用户从/orders页面被引导至登录页，验证码有效",
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "从/orders页面触发登录流程，输入有效手机号验证码登录",
    "result": "登录接口响应体含token字段且格式为JWT(三段式)"
   },
   {
    "step": "观察页面跳转",
    "result": "跳转回登录前页面/orders，而非首页"
   }
  ],
  "test_data": {
   "手机号": "13812345678",
   "来源页面": "/orders",
   "token格式": "JWT三段式"
  },
  "remarks": "FP-005 需求FR-01规则6"
 },
 {
  "name": "无来源页面时登录成功跳转首页",
  "case_number": "TC-PR1-LOGIN-025",
  "module": "手机号验证码登录",
  "case_type": "functional",
  "preconditions": "直接访问登录页（无登录前页面），验证码有效",
  "priority": "high",
  "test_case_steps": [
   {
    "step": "直接输入手机号验证码登录",
    "result": "登录成功后跳转至首页"
   }
  ],
  "test_data": {
   "手机号": "13812345678",
   "来源页面": "无(直接访问登录页)"
  },
  "remarks": "FP-005 需求FR-01规则6"
 },
 {
  "name": "登录失败返回明确错误提示且不跳转",
  "case_number": "TC-PR1-LOGIN-026",
  "module": "手机号验证码登录",
  "case_type": "functional",
  "preconditions": "手机号13812345678已获取验证码483920",
  "priority": "high",
  "test_case_steps": [
   {
    "step": "输入错误验证码999999并点击登录",
    "result": "页面展示具体错误\"验证码错误，剩余机会X次\"，URL保持不变"
   },
   {
    "step": "检查接口响应",
    "result": "登录接口返回业务失败码，响应体不包含token字段"
   }
  ],
  "test_data": {
   "手机号": "13812345678",
   "验证码": "999999(错误)"
  },
  "remarks": "FP-005 需求FR-01输出"
 },
 {
  "name": "登录接口性能基线P95小于等于500ms",
  "case_number": "TC-PR1-LOGIN-027",
  "module": "手机号验证码登录",
  "case_type": "performance",
  "preconditions": "性能测试环境已部署，短信Mock服务可用，压测工具JMeter已配置",
  "priority": "high",
  "test_case_steps": [
   {
    "step": "配置100虚拟用户并发，每用户迭代50次，共5000次登录请求",
    "result": "登录接口P95响应时间≤500ms"
   },
   {
    "step": "统计错误率与成功率",
    "result": "登录成功率≥99%(不含验证码输错)，接口错误率<0.5%"
   }
  ],
  "test_data": {
   "并发用户数": 100,
   "迭代次数": 50,
   "总请求数": 5000,
   "P95目标": "≤500ms",
   "成功率目标": "≥99%"
  },
  "remarks": "FP-005 性能基线 需求§1.3指标"
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 12. ws-PR-1-test_cases_dressup_module_03_preview

- 来源：`workspace/testcase/PR-1/test_cases_dressup_module_03_preview.jsonl`　分组：PR-1　用例数：17

```json
[
 {
  "name": "麦位框预览效果展示用户头像与麦位框动效",
  "case_number": "TC-PR1-PREVIEW-001",
  "module": "预览区",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "麦位框装扮弹窗已展示（麦位框-萌爪闪闪）",
  "remarks": "关联需求 REQ-DEC-003（需求点3 预览区）",
  "test_data": {
   "装扮": "麦位框-萌爪闪闪",
   "预览组成": "用户头像+麦位框动效"
  },
  "test_case_steps": [
   {
    "step": "查看弹窗预览区",
    "result": "预览区展示用户头像+麦位框动效，动效效果与现有个性装扮页的麦位框效果一致"
   }
  ]
 },
 {
  "name": "座驾坐骑进房特效预览展示固定背景与动效",
  "case_number": "TC-PR1-PREVIEW-002",
  "module": "预览区",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "座驾装扮弹窗已展示，装扮为坐骑进房特效类型（座驾-星河战舰）",
  "remarks": "关联需求 REQ-DEC-003（需求点3 坐骑进房特效）",
  "test_data": {
   "装扮": "座驾-星河战舰",
   "特效类型": "坐骑进房特效",
   "预览组成": "固定背景+动效"
  },
  "test_case_steps": [
   {
    "step": "查看弹窗预览区",
    "result": "预览区展示固定背景+坐骑进房动效，与现有个性装扮页效果一致"
   }
  ]
 },
 {
  "name": "座驾板子进房特效预览与坐骑特效区分展示",
  "case_number": "TC-PR1-PREVIEW-003",
  "module": "预览区",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "座驾装扮弹窗已展示，装扮为板子进房特效类型（座驾-专属板子）",
  "remarks": "关联需求 REQ-DEC-003（需求点3 区分坐骑/板子进房特效）",
  "test_data": {
   "装扮": "座驾-专属板子",
   "特效类型": "板子进房特效",
   "预览组成": "固定背景+动效",
   "可辨识元素": "板子造型元素/板子专属文案标识"
  },
  "test_case_steps": [
   {
    "step": "查看弹窗预览区",
    "result": "预览区展示固定背景+板子进房动效；动效中出现板子造型元素（区别于坐骑的骑乘造型元素），依据板子专属元素/文案标识可客观判定为板子进房特效"
   }
  ]
 },
 {
  "name": "个人铭牌预览展示固定背景与铭牌动效",
  "case_number": "TC-PR1-PREVIEW-004",
  "module": "预览区",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "个人铭牌装扮弹窗已展示（个人铭牌-闪耀之星）",
  "remarks": "关联需求 REQ-DEC-003（需求点3 个人铭牌）",
  "test_data": {
   "装扮": "个人铭牌-闪耀之星",
   "预览组成": "固定背景+铭牌动效"
  },
  "test_case_steps": [
   {
    "step": "查看弹窗预览区",
    "result": "预览区展示固定背景+铭牌动效，与现有个性装扮页效果一致"
   }
  ]
 },
 {
  "name": "装扮名称格式为『类型名称-装扮名称』",
  "case_number": "TC-PR1-PREVIEW-005",
  "module": "预览区",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "麦位框装扮弹窗已展示（麦位框-萌爪闪闪）",
  "remarks": "关联需求 REQ-DEC-003（需求点3 名称格式）",
  "test_data": {
   "装扮类型": "麦位框",
   "装扮名称": "萌爪闪闪",
   "预期名称": "麦位框-萌爪闪闪"
  },
  "test_case_steps": [
   {
    "step": "查看弹窗内装扮名称展示",
    "result": "名称显示为『麦位框-萌爪闪闪』，格式为『类型名称-装扮名称』"
   }
  ]
 },
 {
  "name": "有效期格式为『剩余时间：n天』",
  "case_number": "TC-PR1-PREVIEW-006",
  "module": "预览区",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "装扮弹窗已展示，该装扮剩余有效期30天（麦位框-萌爪闪闪）",
  "remarks": "关联需求 REQ-DEC-003（需求点3 有效期格式）",
  "test_data": {
   "剩余有效期": 30,
   "预期文案": "剩余时间：30天"
  },
  "test_case_steps": [
   {
    "step": "查看弹窗内有效期信息",
    "result": "有效期显示为『剩余时间：30天』，格式与需求一致"
   }
  ]
 },
 {
  "name": "有效期边界值1天与365天展示",
  "case_number": "TC-PR1-PREVIEW-007",
  "module": "预览区",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "分别构造2件剩余有效期不同的装扮：1天与365天（365天有效期通过测试环境接口/数据库造数，不可自然等待）",
  "remarks": "关联需求 REQ-DEC-003；边界值场景；造数依赖：剩余有效期365天需通过测试环境改库/造数接口构造",
  "test_data": {
   "装扮1剩余有效期": 1,
   "装扮1预期文案": "剩余时间：1天",
   "装扮2剩余有效期": 365,
   "装扮2预期文案": "剩余时间：365天"
  },
  "test_case_steps": [
   {
    "step": "查看剩余有效期1天的装扮弹窗",
    "result": "有效期显示为『剩余时间：1天』，n=1不省略单位"
   },
   {
    "step": "查看剩余有效期365天的装扮弹窗",
    "result": "有效期显示为『剩余时间：365天』，大数值完整展示无溢出"
   }
  ]
 },
 {
  "name": "cp麦位框的CP信息展示在有效期右侧",
  "case_number": "TC-PR1-PREVIEW-008",
  "module": "预览区",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "cp麦位框装扮弹窗已展示（cp麦位框-情定今生），已绑定CP昵称『小甜甜』，剩余有效期30天",
  "remarks": "关联需求 REQ-DEC-003（需求点3 关系信息展示）；拼接格式依据需求原文示例『剩余时间：n天丨CP：用户昵称昵称』",
  "test_data": {
   "装扮": "cp麦位框-情定今生",
   "CP昵称": "小甜甜",
   "剩余有效期": 30,
   "预期文案": "剩余时间：30天丨CP：小甜甜"
  },
  "test_case_steps": [
   {
    "step": "查看弹窗内有效期及右侧区域",
    "result": "有效期右侧展示CP信息，整体文案为『剩余时间：30天丨CP：小甜甜』，CP信息位于有效期右边"
   }
  ]
 },
 {
  "name": "坐骑关系用户信息展示在有效期右侧",
  "case_number": "TC-PR1-PREVIEW-009",
  "module": "预览区",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "坐骑装扮弹窗已展示（座驾-星河战舰），已绑定关系用户昵称『挚友小明』，剩余有效期7天",
  "remarks": "关联需求 REQ-DEC-003（需求点3 关系信息展示）；拼接格式依据需求原文示例（有效期右侧展示关系用户信息）",
  "test_data": {
   "装扮": "座驾-星河战舰",
   "关系用户昵称": "挚友小明",
   "剩余有效期": 7,
   "预期文案": "剩余时间：7天丨挚友小明"
  },
  "test_case_steps": [
   {
    "step": "查看弹窗内有效期及右侧区域",
    "result": "有效期右侧展示关系用户信息，整体文案为『剩余时间：7天丨挚友小明』"
   }
  ]
 },
 {
  "name": "无关系信息装扮仅展示有效期不显示关系部分",
  "case_number": "TC-PR1-PREVIEW-010",
  "module": "预览区",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "普通麦位框装扮弹窗已展示（麦位框-萌爪闪闪），该装扮无CP关系、无关系用户，剩余有效期30天",
  "remarks": "关联需求 REQ-DEC-003（需求点3 关系信息非必展示）",
  "test_data": {
   "装扮": "麦位框-萌爪闪闪",
   "是否有关系信息": "无",
   "剩余有效期": 30,
   "预期文案": "剩余时间：30天"
  },
  "test_case_steps": [
   {
    "step": "查看弹窗内有效期及右侧区域",
    "result": "仅显示『剩余时间：30天』，右侧无『丨CP：xxx』或关系用户信息"
   }
  ]
 },
 {
  "name": "滑动切换时名称有效期关系信息同步切换",
  "case_number": "TC-PR1-PREVIEW-011",
  "module": "预览区",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "合并弹窗已展示2件装扮：cp麦位框-情定今生（CP=小甜甜，30天）为第1张、座驾-星河战舰（无关系，7天）为第2张，当前预览第1张",
  "remarks": "关联需求 REQ-DEC-003（需求点3 合并展示时信息随预览切换）",
  "test_data": {
   "卡片1": "cp麦位框-情定今生丨CP：小甜甜丨剩余时间：30天",
   "卡片2": "座驾-星河战舰丨剩余时间：7天"
  },
  "test_case_steps": [
   {
    "step": "当前预览第1张cp麦位框卡片，记录名称、有效期、关系信息",
    "result": "显示『cp麦位框-情定今生』、『剩余时间：30天』、『丨CP：小甜甜』"
   },
   {
    "step": "向左滑动切换到第2张座驾卡片",
    "result": "名称变为『座驾-星河战舰』，有效期变为『剩余时间：7天』，关系信息区域无内容；三项信息均与当前预览装扮一致"
   }
  ]
 },
 {
  "name": "装扮名称超长展示不破坏弹窗布局",
  "case_number": "TC-PR1-PREVIEW-012",
  "module": "预览区",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "获得1件名称超长的装扮（麦位框-超长名称测试这是一个非常长的装扮名称用于验证展示效果不会破坏弹窗布局）并弹出弹窗",
  "remarks": "关联需求 REQ-DEC-003；边界值场景；截断规则以客户端既定样式规范为准（超长时显示省略号）",
  "test_data": {
   "装扮名称": "麦位框-超长名称测试这是一个非常长的装扮名称用于验证展示效果不会破坏弹窗布局",
   "名称长度": "30+字符",
   "预期处理": "按既定规则截断显示并追加省略号"
  },
  "test_case_steps": [
   {
    "step": "查看弹窗内装扮名称展示与弹窗整体布局",
    "result": "名称按客户端既定截断规则显示（超长部分以省略号『…』替代），弹窗布局无横向溢出、无错乱，其余信息正常展示"
   }
  ]
 },
 {
  "name": "CP昵称含XSS脚本时不执行脚本以纯文本展示",
  "case_number": "TC-PR1-PREVIEW-013",
  "module": "预览区",
  "case_type": "security",
  "priority": "high",
  "preconditions": "cp麦位框装扮弹窗已展示（cp麦位框-情定今生），CP昵称通过测试接口/数据库构造为包含恶意脚本的内容",
  "remarks": "关联需求 REQ-DEC-003；安全用例（XSS）；造数方式：测试接口直接修改CP昵称字段",
  "test_data": {
   "CP昵称": "<script>alert(document.cookie)</script>",
   "装扮": "cp麦位框-情定今生"
  },
  "test_case_steps": [
   {
    "step": "打开弹窗查看关系信息区域",
    "result": "页面无 alert 弹窗、无页面崩溃、无脚本执行痕迹（服务端返回的脚本内容未作为可执行代码渲染）"
   },
   {
    "step": "检查CP昵称的展示方式",
    "result": "恶意内容以纯文本或转义形式展示，不渲染为HTML/脚本；弹窗其余区域渲染无异常、无布局破坏"
   }
  ]
 },
 {
  "name": "剩余有效期0天装扮的展示",
  "case_number": "TC-PR1-PREVIEW-014",
  "module": "预览区",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "装扮弹窗已展示，该装扮剩余有效期0天（当天到期，通过测试环境接口/数据库构造）",
  "remarks": "关联需求 REQ-DEC-003；边界值场景；需求未定义 n=0/过期展示规则，按『显示剩余时间：0天』假设编写，待产品确认",
  "test_data": {
   "剩余有效期": 0,
   "假设预期文案": "剩余时间：0天",
   "造数方式": "测试环境接口/数据库构造剩余0天"
  },
  "test_case_steps": [
   {
    "step": "查看弹窗内有效期信息",
    "result": "有效期显示为『剩余时间：0天』（n=0完整展示，无负数、无格式错乱）；若产品定义过期装扮不弹窗/置灰，则以产品规则为准（标注待确认）"
   }
  ]
 },
 {
  "name": "已过期装扮获得后的处理",
  "case_number": "TC-PR1-PREVIEW-015",
  "module": "预览区",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "服务端向用户发放1件已过期装扮（有效期为过去时间，通过测试环境接口/数据库构造）",
  "remarks": "关联需求 REQ-DEC-003；异常场景——已过期装扮是否仍发放/是否弹窗/是否置灰需求未明确，按『不弹窗且不入包（或置灰入包）』假设编写，待产品确认",
  "test_data": {
   "装扮": "麦位框-已过期样例",
   "有效期": "已过期（过去时间）"
  },
  "test_case_steps": [
   {
    "step": "服务端发放1件已过期装扮，观察弹窗",
    "result": "按产品规则处理（标注待确认）：不弹出装扮弹窗（若弹窗则展示置灰/不可佩戴状态），无异常报错"
   },
   {
    "step": "查看背包中该装扮",
    "result": "背包中该已过期装扮的处理（不入包丢弃 或 入包置灰）与产品规则一致，无发放异常"
   }
  ]
 },
 {
  "name": "CP昵称含SQL注入内容时不执行且以纯文本展示",
  "case_number": "TC-PR1-PREVIEW-016",
  "module": "预览区",
  "case_type": "security",
  "priority": "high",
  "preconditions": "cp麦位框装扮弹窗已展示（cp麦位框-情定今生），CP昵称通过测试接口/数据库构造为SQL注入字符串",
  "remarks": "关联需求 REQ-DEC-003；安全用例（SQL注入）；造数方式：测试接口直接修改CP昵称字段",
  "test_data": {
   "CP昵称": "1' OR '1'='1",
   "装扮": "cp麦位框-情定今生"
  },
  "test_case_steps": [
   {
    "step": "打开弹窗查看关系信息区域",
    "result": "页面无数据库报错信息泄露、无越权展示他人数据（未出现其他用户的CP信息）"
   },
   {
    "step": "检查CP昵称的展示方式",
    "result": "SQL注入字符串以纯文本展示，不触发任何SQL执行行为；弹窗其余区域渲染正常"
   }
  ]
 },
 {
  "name": "CP昵称含特殊字符与emoji及超长内容的展示",
  "case_number": "TC-PR1-PREVIEW-017",
  "module": "预览区",
  "case_type": "security",
  "priority": "medium",
  "preconditions": "cp麦位框装扮弹窗已展示（cp麦位框-情定今生），CP昵称通过测试接口/数据库构造为含特殊字符、emoji及超长内容",
  "remarks": "关联需求 REQ-DEC-003；安全用例（特殊字符/Unicode/超长）；造数方式：测试接口直接修改CP昵称字段",
  "test_data": {
   "CP昵称": "🌟测试&<>\"\\'昵称AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
   "装扮": "cp麦位框-情定今生",
   "昵称长度": "120+字符含特殊符号"
  },
  "test_case_steps": [
   {
    "step": "打开弹窗查看关系信息区域",
    "result": "特殊字符、emoji、超长昵称按既定规则完整展示或截断（追加省略号），无渲染异常、无字符乱码、无布局错乱"
   },
   {
    "step": "检查弹窗整体",
    "result": "弹窗不崩溃、不白屏，其余装扮信息展示正常"
   }
  ]
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 13. ws-PR-2-test_cases_sysconfig

- 来源：`workspace/testcase/PR-2/test_cases_sysconfig.jsonl`　分组：PR-2　用例数：30

```json
[
 {
  "case_number": "TC-PR2-SC-001",
  "name": "端口号默认显示为COM1",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "系统配置页面已加载，未连接任何端口",
  "test_data": {
   "port": "COM1"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "端口号下拉框默认显示\"1\""
   }
  ],
  "remarks": "覆盖FP-001-端口选择与连接"
 },
 {
  "case_number": "TC-PR2-SC-002",
  "name": "选择合法端口号并连接成功",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "系统配置页面已加载，端口COM3未被占用",
  "test_data": {
   "port": "COM3"
  },
  "test_case_steps": [
   {
    "step": "1. 点击端口号下拉框，选择COM3",
    "result": "下拉框选中COM3"
   },
   {
    "step": "2. 点击\"连接\"按钮",
    "result": "连接按钮状态变为\"已连接\"，界面显示连接成功提示"
   }
  ],
  "remarks": "覆盖FP-001-端口选择与连接"
 },
 {
  "case_number": "TC-PR2-SC-003",
  "name": "端口被占用时连接失败",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "系统配置页面已加载，端口COM1已被其他应用程序占用",
  "test_data": {
   "port": "COM1"
  },
  "test_case_steps": [
   {
    "step": "1. 选择端口COM1",
    "result": "端口下拉框显示COM1"
   },
   {
    "step": "2. 点击\"连接\"按钮",
    "result": "连接失败，界面显示端口被占用的错误提示，连接按钮保持\"未连接\"状态"
   }
  ],
  "remarks": "覆盖FP-001-端口选择与连接；异常场景"
 },
 {
  "case_number": "TC-PR2-SC-004",
  "name": "连接成功后断开连接",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "已成功连接端口COM5，状态显示\"已连接\"",
  "test_data": {
   "port": "COM5"
  },
  "test_case_steps": [
   {
    "step": "1. 点击\"断开连接\"按钮（或再次点击\"连接\"按钮）",
    "result": "连接断开，按钮状态恢复为\"未连接\"，界面显示已断开的提示信息"
   }
  ],
  "remarks": "覆盖FP-001-端口选择与连接"
 },
 {
  "case_number": "TC-PR2-SC-005",
  "name": "端口下拉列表内容完整",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "系统配置页面已加载",
  "test_data": {
   "port": "-"
  },
  "test_case_steps": [
   {
    "step": "1. 展开端口号下拉框",
    "result": "下拉列表显示可用端口列表（如COM1~COM10），至少包含1个选项"
   }
  ],
  "remarks": "覆盖FP-001-端口选择与连接"
 },
 {
  "case_number": "TC-PR2-SC-006",
  "name": "配气稳定时间-输入合法值",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "系统配置页面已加载",
  "test_data": {
   "配气稳定时间": "500.00"
  },
  "test_case_steps": [
   {
    "step": "1. 在配气稳定时间输入框中输入\"500.00\"",
    "result": "输入框正确显示输入值"
   },
   {
    "step": "2. 点击\"保存\"按钮",
    "result": "保存成功，无校验错误提示"
   }
  ],
  "remarks": "覆盖FP-002-配气稳定时间配置；边界值中间值"
 },
 {
  "case_number": "TC-PR2-SC-007",
  "name": "配气稳定时间-边界值0秒",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "系统配置页面已加载",
  "test_data": {
   "配气稳定时间": "0"
  },
  "test_case_steps": [
   {
    "step": "1. 在配气稳定时间输入框中输入\"0\"",
    "result": "输入框正确显示0"
   },
   {
    "step": "2. 点击\"保存\"按钮",
    "result": "保存成功（假设0为有效值）或提示\"请输入大于0的值\"（取决于业务规则）"
   }
  ],
  "remarks": "覆盖FP-002-配气稳定时间配置；边界值最小值"
 },
 {
  "case_number": "TC-PR2-SC-008",
  "name": "配气稳定时间-边界值9999.99秒",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "系统配置页面已加载",
  "test_data": {
   "配气稳定时间": "9999.99"
  },
  "test_case_steps": [
   {
    "step": "1. 在配气稳定时间输入框中输入\"9999.99\"",
    "result": "输入框正确显示9999.99"
   },
   {
    "step": "2. 点击\"保存\"按钮",
    "result": "保存成功"
   }
  ],
  "remarks": "覆盖FP-002-配气稳定时间配置；边界值最大值"
 },
 {
  "case_number": "TC-PR2-SC-009",
  "name": "配气稳定时间-输入负数",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "系统配置页面已加载",
  "test_data": {
   "配气稳定时间": "-1"
  },
  "test_case_steps": [
   {
    "step": "1. 在配气稳定时间输入框中输入\"-1\"",
    "result": "输入框显示-1"
   },
   {
    "step": "2. 点击\"保存\"按钮",
    "result": "保存失败，提示\"配气稳定时间必须大于等于0\""
   }
  ],
  "remarks": "覆盖FP-002-配气稳定时间配置；边界值min-1"
 },
 {
  "case_number": "TC-PR2-SC-010",
  "name": "配气稳定时间-输入超范围值",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "系统配置页面已加载",
  "test_data": {
   "配气稳定时间": "100000"
  },
  "test_case_steps": [
   {
    "step": "1. 在配气稳定时间输入框中输入\"100000\"",
    "result": "输入框显示100000"
   },
   {
    "step": "2. 点击\"保存\"按钮",
    "result": "保存失败，提示输入值超出范围"
   }
  ],
  "remarks": "覆盖FP-002-配气稳定时间配置；边界值max+1"
 },
 {
  "case_number": "TC-PR2-SC-011",
  "name": "配气稳定时间-输入3位小数值",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "系统配置页面已加载",
  "test_data": {
   "配气稳定时间": "0.001"
  },
  "test_case_steps": [
   {
    "step": "1. 在配气稳定时间输入框中输入\"0.001\"",
    "result": "输入框显示0.001"
   },
   {
    "step": "2. 点击\"保存\"按钮",
    "result": "保存失败或自动截断为0.00，提示\"最多支持2位小数\""
   }
  ],
  "remarks": "覆盖FP-002-配气稳定时间配置；精度校验"
 },
 {
  "case_number": "TC-PR2-SC-012",
  "name": "配气稳定时间-输入非数字字符",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "系统配置页面已加载",
  "test_data": {
   "配气稳定时间": "abc"
  },
  "test_case_steps": [
   {
    "step": "1. 在配气稳定时间输入框中输入\"abc\"",
    "result": "输入框拒绝输入或保存时提示\"请输入数字\""
   }
  ],
  "remarks": "覆盖FP-002-配气稳定时间配置；异常输入"
 },
 {
  "case_number": "TC-PR2-SC-013",
  "name": "配气稳定时间-输入空值",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "系统配置页面已加载",
  "test_data": {
   "配气稳定时间": ""
  },
  "test_case_steps": [
   {
    "step": "1. 清空配气稳定时间输入框",
    "result": "输入框为空"
   },
   {
    "step": "2. 点击\"保存\"按钮",
    "result": "保存失败，提示\"配气稳定时间为必填项\""
   }
  ],
  "remarks": "覆盖FP-002-配气稳定时间配置；空值校验"
 },
 {
  "case_number": "TC-PR2-SC-014",
  "name": "配气总量偏差阈值-输入合法值",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "系统配置页面已加载",
  "test_data": {
   "配气总量偏差阈值": "50.00"
  },
  "test_case_steps": [
   {
    "step": "1. 在配气总量偏差阈值输入框中输入\"50.00\"",
    "result": "输入框正确显示50.00"
   },
   {
    "step": "2. 点击\"保存\"按钮",
    "result": "保存成功"
   }
  ],
  "remarks": "覆盖FP-003-配气总量偏差阈值配置"
 },
 {
  "case_number": "TC-PR2-SC-015",
  "name": "配气总量偏差阈值-边界值0ml",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "系统配置页面已加载",
  "test_data": {
   "配气总量偏差阈值": "0"
  },
  "test_case_steps": [
   {
    "step": "1. 输入\"0\"",
    "result": "输入框显示0"
   },
   {
    "step": "2. 点击保存",
    "result": "保存成功或提示\"请输入大于0的值\""
   }
  ],
  "remarks": "覆盖FP-003-配气总量偏差阈值配置；边界值最小值"
 },
 {
  "case_number": "TC-PR2-SC-016",
  "name": "配气总量偏差阈值-边界值9999.99ml",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "系统配置页面已加载",
  "test_data": {
   "配气总量偏差阈值": "9999.99"
  },
  "test_case_steps": [
   {
    "step": "1. 输入\"9999.99\"",
    "result": "输入框显示9999.99"
   },
   {
    "step": "2. 点击保存",
    "result": "保存成功"
   }
  ],
  "remarks": "覆盖FP-003-配气总量偏差阈值配置；边界值最大值"
 },
 {
  "case_number": "TC-PR2-SC-017",
  "name": "配气总量偏差阈值-输入负数",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "系统配置页面已加载",
  "test_data": {
   "配气总量偏差阈值": "-1"
  },
  "test_case_steps": [
   {
    "step": "1. 输入\"-1\"",
    "result": "输入框显示-1"
   },
   {
    "step": "2. 点击保存",
    "result": "保存失败，提示\"阈值必须大于等于0\""
   }
  ],
  "remarks": "覆盖FP-003-配气总量偏差阈值配置；边界值min-1"
 },
 {
  "case_number": "TC-PR2-SC-018",
  "name": "配气总量偏差阈值-输入超范围值",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "系统配置页面已加载",
  "test_data": {
   "配气总量偏差阈值": "100000"
  },
  "test_case_steps": [
   {
    "step": "1. 输入\"100000\"",
    "result": "输入框显示100000"
   },
   {
    "step": "2. 点击保存",
    "result": "保存失败，提示超出范围"
   }
  ],
  "remarks": "覆盖FP-003-配气总量偏差阈值配置；边界值max+1"
 },
 {
  "case_number": "TC-PR2-SC-019",
  "name": "配气总量偏差阈值-输入特殊字符",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "系统配置页面已加载",
  "test_data": {
   "配气总量偏差阈值": "@#$%"
  },
  "test_case_steps": [
   {
    "step": "1. 输入\"@#$%\"",
    "result": "输入框拒绝输入或保存时提示格式错误"
   }
  ],
  "remarks": "覆盖FP-003-配气总量偏差阈值配置；特殊字符"
 },
 {
  "case_number": "TC-PR2-SC-020",
  "name": "配气总量偏差阈值-输入空值",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "系统配置页面已加载",
  "test_data": {
   "配气总量偏差阈值": ""
  },
  "test_case_steps": [
   {
    "step": "1. 清空输入框",
    "result": "输入框为空"
   },
   {
    "step": "2. 点击保存",
    "result": "保存失败，提示为必填项"
   }
  ],
  "remarks": "覆盖FP-003-配气总量偏差阈值配置；空值校验"
 },
 {
  "case_number": "TC-PR2-SC-021",
  "name": "查询周期-默认显示100ms",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "系统配置页面首次加载，未修改过查询周期",
  "test_data": {
   "查询周期": "100"
  },
  "test_case_steps": [
   {
    "step": "1. 打开系统配置页面",
    "result": "查询周期输入框默认显示\"100\"，输入框右侧显示单位\"ms\""
   }
  ],
  "remarks": "覆盖FP-004-查询周期配置"
 },
 {
  "case_number": "TC-PR2-SC-022",
  "name": "查询周期-输入合法值",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "系统配置页面已加载",
  "test_data": {
   "查询周期": "500"
  },
  "test_case_steps": [
   {
    "step": "1. 输入\"500\"",
    "result": "输入框显示500"
   },
   {
    "step": "2. 点击保存",
    "result": "保存成功"
   }
  ],
  "remarks": "覆盖FP-004-查询周期配置"
 },
 {
  "case_number": "TC-PR2-SC-023",
  "name": "查询周期-边界值50ms",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "系统配置页面已加载",
  "test_data": {
   "查询周期": "50"
  },
  "test_case_steps": [
   {
    "step": "1. 输入\"50\"",
    "result": "输入框显示50"
   },
   {
    "step": "2. 点击保存",
    "result": "保存成功"
   }
  ],
  "remarks": "覆盖FP-004-查询周期配置；边界值最小值"
 },
 {
  "case_number": "TC-PR2-SC-024",
  "name": "查询周期-边界值10000ms",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "系统配置页面已加载",
  "test_data": {
   "查询周期": "10000"
  },
  "test_case_steps": [
   {
    "step": "1. 输入\"10000\"",
    "result": "输入框显示10000"
   },
   {
    "step": "2. 点击保存",
    "result": "保存成功"
   }
  ],
  "remarks": "覆盖FP-004-查询周期配置；边界值最大值"
 },
 {
  "case_number": "TC-PR2-SC-025",
  "name": "查询周期-输入小于下限值49ms",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "系统配置页面已加载",
  "test_data": {
   "查询周期": "49"
  },
  "test_case_steps": [
   {
    "step": "1. 输入\"49\"",
    "result": "输入框显示49"
   },
   {
    "step": "2. 点击保存",
    "result": "保存失败，提示\"查询周期最小值为50ms\""
   }
  ],
  "remarks": "覆盖FP-004-查询周期配置；边界值min-1"
 },
 {
  "case_number": "TC-PR2-SC-026",
  "name": "查询周期-输入大于上限值10001ms",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "系统配置页面已加载",
  "test_data": {
   "查询周期": "10001"
  },
  "test_case_steps": [
   {
    "step": "1. 输入\"10001\"",
    "result": "输入框显示10001"
   },
   {
    "step": "2. 点击保存",
    "result": "保存失败，提示\"查询周期最大值为10000ms\""
   }
  ],
  "remarks": "覆盖FP-004-查询周期配置；边界值max+1"
 },
 {
  "case_number": "TC-PR2-SC-027",
  "name": "查询周期-输入小数",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "系统配置页面已加载",
  "test_data": {
   "查询周期": "100.5"
  },
  "test_case_steps": [
   {
    "step": "1. 输入\"100.5\"",
    "result": "输入框显示100.5"
   },
   {
    "step": "2. 点击保存",
    "result": "保存失败（假设查询周期仅支持整数），提示\"查询周期必须为整数\""
   }
  ],
  "remarks": "覆盖FP-004-查询周期配置；类型校验"
 },
 {
  "case_number": "TC-PR2-SC-028",
  "name": "查询周期-输入0值",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "系统配置页面已加载",
  "test_data": {
   "查询周期": "0"
  },
  "test_case_steps": [
   {
    "step": "1. 输入\"0\"",
    "result": "输入框显示0"
   },
   {
    "step": "2. 点击保存",
    "result": "保存失败，提示\"查询周期最小值为50ms\""
   }
  ],
  "remarks": "覆盖FP-004-查询周期配置；零值校验"
 },
 {
  "case_number": "TC-PR2-SC-029",
  "name": "查询周期-输入空值",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "系统配置页面已加载",
  "test_data": {
   "查询周期": ""
  },
  "test_case_steps": [
   {
    "step": "1. 清空查询周期输入框",
    "result": "输入框为空"
   },
   {
    "step": "2. 点击保存",
    "result": "保存失败，提示为必填项，或恢复为默认值100ms"
   }
  ],
  "remarks": "覆盖FP-004-查询周期配置；空值校验"
 },
 {
  "case_number": "TC-PR2-SC-030",
  "name": "流量偏差阈值-输入合法值",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "系统配置页面已加载",
  "test_data": {
   "流量偏差阈值": "100.00"
  },
  "test_case_steps": [
   {
    "step": "1. 输入\"100.00\"",
    "result": "输入框显示100.00"
   },
   {
    "step": "2. 点击保存",
    "result": "保存成功"
   }
  ],
  "remarks": "覆盖FP-005-流量偏差阈值配置"
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 14. ws-PR-1-test_cases_dressup_module_05_multi

- 来源：`workspace/testcase/PR-1/test_cases_dressup_module_05_multi.jsonl`　分组：PR-1　用例数：14

```json
[
 {
  "name": "合并弹窗显示佩戴当前与全部佩戴两个按钮",
  "case_number": "TC-PR1-MULTI-001",
  "module": "合并装扮操作",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "合并弹窗已展示2件装扮：麦位框-萌爪闪闪、座驾-星河战舰",
  "remarks": "关联需求 REQ-DEC-004（需求点4 合并按钮数量与文案）",
  "test_data": {
   "弹窗内装扮数": 2,
   "按钮1": "佩戴当前",
   "按钮2": "全部佩戴",
   "不应显示按钮": "立即佩戴"
  },
  "test_case_steps": [
   {
    "step": "查看弹窗底部按钮区域",
    "result": "显示2个按钮『佩戴当前』和『全部佩戴』，不显示『立即佩戴』"
   }
  ]
 },
 {
  "name": "点击佩戴当前佩戴当前预览装扮并自动切换下一张",
  "case_number": "TC-PR1-MULTI-002",
  "module": "合并装扮操作",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "合并弹窗已展示2件装扮：麦位框-萌爪闪闪（第1张，当前预览）、座驾-星河战舰（第2张）；网络正常",
  "remarks": "关联需求 REQ-DEC-004（需求点4 佩戴当前逻辑）",
  "test_data": {
   "当前预览": "麦位框-萌爪闪闪",
   "下一张": "座驾-星河战舰",
   "预期toast": "装扮已佩戴"
  },
  "test_case_steps": [
   {
    "step": "点击『佩戴当前』按钮",
    "result": "当前预览的麦位框-萌爪闪闪佩戴成功，toast提示『装扮已佩戴』"
   },
   {
    "step": "观察卡片列表与预览",
    "result": "麦位框-萌爪闪闪卡片从弹窗卡片列表中移除；弹窗自动切换到下一张卡片（座驾-星河战舰）预览"
   }
  ]
 },
 {
  "name": "佩戴当前操作只影响当前预览的装扮",
  "case_number": "TC-PR1-MULTI-003",
  "module": "合并装扮操作",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "合并弹窗已展示3件装扮：麦位框-萌爪闪闪（第1张，当前预览）、座驾-星河战舰、个人铭牌-闪耀之星",
  "remarks": "关联需求 REQ-DEC-004（需求点4 佩戴当前仅操作当前展示装扮）",
  "test_data": {
   "卡片1": "麦位框-萌爪闪闪",
   "卡片2": "座驾-星河战舰",
   "卡片3": "个人铭牌-闪耀之星",
   "操作": "佩戴当前×1次"
  },
  "test_case_steps": [
   {
    "step": "点击『佩戴当前』按钮1次",
    "result": "仅麦位框-萌爪闪闪被佩戴"
   },
   {
    "step": "检查其余两张卡片的状态",
    "result": "座驾-星河战舰、个人铭牌-闪耀之星仍保留在弹窗卡片列表中，二者均处于未佩戴状态"
   }
  ]
 },
 {
  "name": "全部预览卡片佩戴完毕后弹窗自动关闭",
  "case_number": "TC-PR1-MULTI-004",
  "module": "合并装扮操作",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "合并弹窗已展示2件装扮：麦位框-萌爪闪闪（当前预览）、座驾-星河战舰；网络正常",
  "remarks": "关联需求 REQ-DEC-004（需求点4 佩戴当前至全部佩戴完毕自动关闭）",
  "test_data": {
   "卡片1": "麦位框-萌爪闪闪",
   "卡片2": "座驾-星河战舰",
   "操作": "连续佩戴当前×2次"
  },
  "test_case_steps": [
   {
    "step": "第1次点击『佩戴当前』",
    "result": "麦位框佩戴成功，toast『装扮已佩戴』，自动切换到座驾卡片"
   },
   {
    "step": "第2次点击『佩戴当前』",
    "result": "座驾佩戴成功，toast『装扮已佩戴』"
   },
   {
    "step": "观察弹窗状态",
    "result": "所有卡片佩戴完毕后弹窗自动关闭"
   }
  ]
 },
 {
  "name": "点击全部佩戴一次性佩戴全部装扮并关闭弹窗",
  "case_number": "TC-PR1-MULTI-005",
  "module": "合并装扮操作",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "合并弹窗已展示3件不同类型装扮：麦位框-萌爪闪闪、座驾-星河战舰、个人铭牌-闪耀之星；网络正常",
  "remarks": "关联需求 REQ-DEC-004（需求点4 全部佩戴逻辑）",
  "test_data": {
   "卡片1": "麦位框-萌爪闪闪",
   "卡片2": "座驾-星河战舰",
   "卡片3": "个人铭牌-闪耀之星",
   "预期toast": "装扮已全部佩戴"
  },
  "test_case_steps": [
   {
    "step": "点击『全部佩戴』按钮",
    "result": "3件装扮全部佩戴成功"
   },
   {
    "step": "观察弹窗与toast",
    "result": "弹窗关闭；toast提示『装扮已全部佩戴』"
   }
  ]
 },
 {
  "name": "全部佩戴时同类型多个装扮仅佩戴首个",
  "case_number": "TC-PR1-MULTI-006",
  "module": "合并装扮操作",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "合并弹窗已展示3件装扮：麦位框-萌爪闪闪（第1张）、麦位框-星河之恋（第2张，同类型）、座驾-星河战舰（第3张）",
  "remarks": "关联需求 REQ-DEC-004（需求点4 全部佩戴同类型只戴首个）；toast『装扮已全部佩戴』为需求原文明确文案（REQ-DEC-004：完成后，关闭弹窗并toast提示『装扮已全部佩戴』），即使同类型只佩戴首个，toast文案不变",
  "test_data": {
   "卡片1": "麦位框-萌爪闪闪",
   "卡片2": "麦位框-星河之恋",
   "卡片3": "座驾-星河战舰",
   "应佩戴": [
    "麦位框-萌爪闪闪",
    "座驾-星河战舰"
   ],
   "不应佩戴": "麦位框-星河之恋",
   "预期toast": "装扮已全部佩戴"
  },
  "test_case_steps": [
   {
    "step": "点击『全部佩戴』按钮",
    "result": "佩戴麦位框-萌爪闪闪（麦位框类型首个）和座驾-星河战舰"
   },
   {
    "step": "检查麦位框-星河之恋的佩戴状态",
    "result": "麦位框-星河之恋未被佩戴，保留在背包中"
   },
   {
    "step": "观察弹窗与toast",
    "result": "弹窗关闭，toast提示『装扮已全部佩戴』（需求原文明确文案）"
   }
  ]
 },
 {
  "name": "全部佩戴后麦位框实际生效验证",
  "case_number": "TC-PR1-MULTI-007",
  "module": "合并装扮操作",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "用户已通过『全部佩戴』成功佩戴麦位框-萌爪闪闪",
  "remarks": "关联需求 REQ-DEC-004（需求点4 佩戴后生效）",
  "test_data": {
   "已佩戴装扮": "麦位框-萌爪闪闪",
   "验证位置": "房间麦位头像"
  },
  "test_case_steps": [
   {
    "step": "返回房间页面查看自己的麦位头像",
    "result": "麦位头像展示麦位框-萌爪闪闪效果（含动效）"
   }
  ]
 },
 {
  "name": "全部佩戴后座驾进房动画实际生效验证",
  "case_number": "TC-PR1-MULTI-008",
  "module": "合并装扮操作",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "用户已通过『全部佩戴』成功佩戴座驾-星河战舰",
  "remarks": "关联需求 REQ-DEC-004（需求点4 佩戴后生效）",
  "test_data": {
   "已佩戴装扮": "座驾-星河战舰",
   "验证方式": "退出房间后重新进入"
  },
  "test_case_steps": [
   {
    "step": "退出当前房间后重新进入房间",
    "result": "进房时展示座驾-星河战舰动画效果（坐骑进房特效）"
   }
  ]
 },
 {
  "name": "全部佩戴接口部分失败时的状态联动验证",
  "case_number": "TC-PR1-MULTI-009",
  "module": "合并装扮操作",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "合并弹窗已展示2件装扮：麦位框-萌爪闪闪（佩戴成功）、座驾-星河战舰（模拟服务端佩戴接口失败）；网络对第2件返回失败",
  "remarks": "关联需求 REQ-DEC-004；异常场景——按『部分成功：成功件佩戴、失败件保留可重试』假设编写，待产品确认（若策略为全部回滚需同步调整断言）",
  "test_data": {
   "卡片1": "麦位框-萌爪闪闪",
   "卡片2": "座驾-星河战舰",
   "服务端响应": "第1件成功、第2件返回失败错误码"
  },
  "test_case_steps": [
   {
    "step": "点击『全部佩戴』按钮",
    "result": "麦位框-萌爪闪闪（第1件）佩戴成功；座驾-星河战舰（第2件）佩戴失败，无崩溃、无卡死"
   },
   {
    "step": "观察卡片列表变化",
    "result": "佩戴成功的麦位框卡片从列表移除；佩戴失败的座驾卡片保留在弹窗中"
   },
   {
    "step": "观察标题变化",
    "result": "标题按剩余卡片数更新为『获得1件装扮』"
   },
   {
    "step": "再次点击『全部佩戴』重试",
    "result": "重试成功后座驾佩戴成功、卡片移除、弹窗关闭，toast提示『装扮已全部佩戴』；重试失败则卡片继续保留可再次重试"
   }
  ]
 },
 {
  "name": "佩戴当前操作时预览非首张卡片的定位行为",
  "case_number": "TC-PR1-MULTI-010",
  "module": "合并装扮操作",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "合并弹窗已展示3件装扮：麦位框-萌爪闪闪（第1张）、座驾-星河战舰（第2张）、个人铭牌-闪耀之星（第3张）；先向左滑动1次使当前预览为第2张（座驾-星河战舰）；网络正常",
  "remarks": "关联需求 REQ-DEC-004；需求未定义非首张佩戴后的定位规则，按『移除后展示相邻卡片（优先下一张，无下一张则回退上一张）』轮播假设编写，待产品确认",
  "test_data": {
   "当前预览": "座驾-星河战舰（第2张）",
   "移除后预期定位": "第3张个人铭牌-闪耀之星（相邻下一张）",
   "操作": "点击佩戴当前"
  },
  "test_case_steps": [
   {
    "step": "点击『佩戴当前』按钮",
    "result": "当前预览的座驾-星河战舰佩戴成功，toast『装扮已佩戴』，座驾卡片从列表移除"
   },
   {
    "step": "观察移除后的预览定位",
    "result": "预览停留在相邻卡片（第3张个人铭牌-闪耀之星，按轮播假设优先展示下一张）；标题更新为『获得2件装扮』，剩余2张卡片均保留"
   }
  ]
 },
 {
  "name": "合并弹窗佩戴至剩1件时的按钮形态",
  "case_number": "TC-PR1-MULTI-011",
  "module": "合并装扮操作",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "合并弹窗已展示3件装扮：麦位框-萌爪闪闪（第1张）、座驾-星河战舰（第2张）、个人铭牌-闪耀之星（第3张）；连续点击『佩戴当前』2次后弹窗内剩1张卡片",
  "remarks": "关联需求 REQ-DEC-004；需求点4 字面规则『弹窗内展示的装扮数=1时，仅1个按钮“立即佩戴”』，按此假设断言按钮切换，待产品确认（若合并弹窗保持双按钮则需调整）",
  "test_data": {
   "初始卡片数": 3,
   "操作": "佩戴当前×2次",
   "剩1件时预期按钮": "立即佩戴（单按钮）",
   "剩1件时预期标题": "获得装扮"
  },
  "test_case_steps": [
   {
    "step": "连续点击『佩戴当前』2次，佩戴前2件装扮",
    "result": "前2件佩戴成功，标题依次更新为『获得2件装扮』→『获得装扮』，弹窗内仅剩1张卡片"
   },
   {
    "step": "查看剩1张卡片时的按钮区域",
    "result": "按钮形态由『佩戴当前+全部佩戴』切换为仅1个『立即佩戴』按钮（按需求点4 字面规则：弹窗内装扮数=1时仅显示『立即佩戴』）"
   }
  ]
 },
 {
  "name": "全部佩戴时3件全同类型仅佩戴首个",
  "case_number": "TC-PR1-MULTI-012",
  "module": "合并装扮操作",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "合并弹窗已展示3件装扮，全部为麦位框类型：麦位框-萌爪闪闪（第1张）、麦位框-星河之恋（第2张）、麦位框-初见之约（第3张）",
  "remarks": "关联需求 REQ-DEC-004（需求点4 同类型只佩戴首个）；需求未明确剩余同类型装扮的再次佩戴入口，待产品确认",
  "test_data": {
   "卡片1": "麦位框-萌爪闪闪",
   "卡片2": "麦位框-星河之恋",
   "卡片3": "麦位框-初见之约",
   "应佩戴": "麦位框-萌爪闪闪",
   "不应佩戴": [
    "麦位框-星河之恋",
    "麦位框-初见之约"
   ]
  },
  "test_case_steps": [
   {
    "step": "点击『全部佩戴』按钮",
    "result": "仅佩戴麦位框类型首个装扮（麦位框-萌爪闪闪）"
   },
   {
    "step": "查看背包中其余2件",
    "result": "麦位框-星河之恋、麦位框-初见之约未被佩戴，保留在背包中"
   },
   {
    "step": "观察弹窗与toast",
    "result": "弹窗关闭，toast提示『装扮已全部佩戴』"
   }
  ]
 },
 {
  "name": "全部佩戴接口整体失败时的处理",
  "case_number": "TC-PR1-MULTI-013",
  "module": "合并装扮操作",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "合并弹窗已展示2件装扮：麦位框-萌爪闪闪、座驾-星河战舰；服务端全部佩戴接口被模拟为整体失败（返回错误码）",
  "remarks": "关联需求 REQ-DEC-004；异常场景",
  "test_data": {
   "卡片1": "麦位框-萌爪闪闪",
   "卡片2": "座驾-星河战舰",
   "服务端响应": "全部佩戴接口整体返回失败错误码"
  },
  "test_case_steps": [
   {
    "step": "点击『全部佩戴』按钮",
    "result": "弹窗不关闭、无崩溃，展示服务端错误码对应的失败提示信息"
   },
   {
    "step": "检查卡片、标题与按钮状态",
    "result": "2张卡片均保留在弹窗中，标题不变（仍为『获得2件装扮』），『全部佩戴』按钮可再次点击重试，无重复toast"
   }
  ]
 },
 {
  "name": "合并弹窗关闭按钮的行为验证",
  "case_number": "TC-PR1-MULTI-014",
  "module": "合并装扮操作",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "合并弹窗已展示3件装扮：麦位框-萌爪闪闪、座驾-星河战舰、个人铭牌-闪耀之星",
  "remarks": "关联需求 REQ-DEC-004（需求点4 关闭按钮）；入包断言：关闭=不佩戴但3件均需入包",
  "test_data": {
   "卡片数": 3,
   "操作": "点击关闭按钮",
   "入包校验": "3件装扮均已在背包中且未佩戴"
  },
  "test_case_steps": [
   {
    "step": "点击弹窗『关闭』按钮",
    "result": "弹窗直接关闭，无toast提示，无装扮被佩戴"
   },
   {
    "step": "查看背包中3件装扮",
    "result": "麦位框-萌爪闪闪、座驾-星河战舰、个人铭牌-闪耀之星均已入包（可在背包中查到），均处于未佩戴状态，发放未丢失"
   }
  ]
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 15. ws-PR-2-final_module_05

- 来源：`workspace/testcase/PR-2/final_module_05.jsonl`　分组：PR-2　用例数：20

```json
[
 {
  "name": "服务退票订单-退票明细完整创建成功",
  "case_number": "TC-PR2-CR-001",
  "module": "服务退单退票",
  "case_type": "functional",
  "preconditions": "原合同Contract001存在且含已开票付款计划；原合同明细行号与付款行号有效；经销商账号 dealer01 已登录DMS",
  "remarks": "关联需求 REQ-CR-001 / FP-012",
  "priority": "critical",
  "test_data": {
   "原合同编号": "Contract001",
   "原合同明细行号": 1,
   "原合同明细付款行号": 1,
   "匹配SAP行号": "SAP-LINE-001",
   "退票金额": 1000.0
  },
  "test_case_steps": [
   {
    "step": "经销商dealer01登录DMS，进入服务退票订单创建页",
    "result": "成功进入创建页"
   },
   {
    "step": "填写退票明细：原合同编号Contract001、原合同明细行号1、原合同明细付款行号1",
    "result": "退票明细录入成功"
   },
   {
    "step": "提交退票申请",
    "result": "系统匹配原付款明细SAP行号后创建CR退票订单，退票订单创建成功"
   }
  ]
 },
 {
  "name": "服务退票订单-退票明细缺少原合同编号拒绝",
  "case_number": "TC-PR2-CR-002",
  "module": "服务退单退票",
  "case_type": "functional",
  "preconditions": "经销商账号 dealer01 已登录DMS",
  "remarks": "关联需求 REQ-CR-001 / FP-012 / 异常场景",
  "priority": "critical",
  "test_data": {
   "原合同编号": "",
   "原合同明细行号": 1,
   "原合同明细付款行号": 1
  },
  "test_case_steps": [
   {
    "step": "进入服务退票订单创建页",
    "result": "成功进入创建页"
   },
   {
    "step": "原合同编号留空，填写明细行号与付款行号",
    "result": "明细行号与付款行号可填写"
   },
   {
    "step": "提交退票申请",
    "result": "系统拒绝创建退票订单，提示\"原合同编号为必填项\""
   }
  ]
 },
 {
  "name": "服务退票订单-匹配不到原付款明细SAP行号处理",
  "case_number": "TC-PR2-CR-003",
  "module": "服务退单退票",
  "case_type": "functional",
  "preconditions": "原合同Contract002存在但付款行号3无对应SAP行号",
  "remarks": "关联需求 REQ-CR-001 / FP-012 / 异常场景",
  "priority": "critical",
  "test_data": {
   "原合同编号": "Contract002",
   "原合同明细行号": 1,
   "原合同明细付款行号": 3,
   "匹配SAP行号": "不存在"
  },
  "test_case_steps": [
   {
    "step": "发起退票申请，退票明细填写原合同Contract002、明细行号1、付款行号3",
    "result": "退票明细录入成功"
   },
   {
    "step": "提交退票申请",
    "result": "系统无法匹配原付款明细SAP行号，返回明确错误提示，退票订单未创建，无脏数据"
   }
  ]
 },
 {
  "name": "服务退票订单-服务退票部分自动对接SAP",
  "case_number": "TC-PR2-CR-004",
  "module": "服务退单退票",
  "case_type": "functional",
  "preconditions": "CR退票订单CR2026050001已通过准备脚本创建；SAP对接接口Mock可用（独立准备，不依赖其他用例）",
  "remarks": "关联需求 REQ-CR-001 / FP-012",
  "priority": "critical",
  "test_data": {
   "退票订单号": "CR2026050001",
   "服务退票部分金额": 1000.0
  },
  "test_case_steps": [
   {
    "step": "CR退票订单创建成功后触发对接",
    "result": "服务退票部分自动对接SAP接口调用成功"
   },
   {
    "step": "查看退票订单状态",
    "result": "退票订单状态由\"已提交\"变更为\"已进入SAP\"，服务退票部分对接数据正确"
   }
  ]
 },
 {
  "name": "服务退票订单-状态流转已提交至已完成",
  "case_number": "TC-PR2-CR-005",
  "module": "服务退单退票",
  "case_type": "functional",
  "preconditions": "CR退票订单CR2026050008已通过准备脚本创建（含服务退票明细，独立于CR-004使用的订单号），当前状态=已提交；SAP退票处理Mock返回成功（独立准备，不依赖其他用例）",
  "remarks": "关联需求 REQ-CR-001 / FP-012 / 状态转换",
  "priority": "high",
  "test_data": {
   "退票订单号": "CR2026050008",
   "初始状态": "已提交",
   "中间状态": "已进入SAP",
   "目标状态": "已完成"
  },
  "test_case_steps": [
   {
    "step": "查看CR退票订单CR2026050008当前状态",
    "result": "订单状态=已提交"
   },
   {
    "step": "触发服务退票部分自动对接SAP",
    "result": "订单状态变更为\"已进入SAP\""
   },
   {
    "step": "SAP退票处理完成（Mock）",
    "result": "订单状态变更为\"已完成\""
   }
  ]
 },
 {
  "name": "撤销付款计划-CC手工在SAP操作后返回DMS确认完成",
  "case_number": "TC-PR2-CR-006",
  "module": "服务退单退票",
  "case_type": "functional",
  "preconditions": "CR退票订单CR2026050002包含未开票付款计划（撤销类型）；CC账号cc01已登录DMS；SAP Mock可用",
  "remarks": "关联需求 REQ-CR-002 / FP-013",
  "priority": "critical",
  "test_data": {
   "退票订单号": "CR2026050002",
   "付款计划类型": "撤销",
   "CC账号": "cc01"
  },
  "test_case_steps": [
   {
    "step": "提交包含撤销付款计划的CR退票订单",
    "result": "订单创建成功，未开票的撤销付款计划不自动对接SAP"
   },
   {
    "step": "CC账号cc01在SAP手工执行撤销操作（Mock）",
    "result": "SAP撤销操作完成"
   },
   {
    "step": "CC返回DMS打开CR退票订单CR2026050002，点击【确认完成】",
    "result": "退票完成确认成功，订单状态变为已完成"
   }
  ]
 },
 {
  "name": "撤销付款计划-仅包含撤销操作状态流转已进入SAP至已完成",
  "case_number": "TC-PR2-CR-007",
  "module": "服务退单退票",
  "case_type": "functional",
  "preconditions": "可创建仅包含撤销（Cancel）类型付款计划、无退票明细的CR退票订单；CC账号cc01已登录DMS（独立准备，不依赖其他用例）",
  "remarks": "关联需求 REQ-CR-002 / FP-013 / 状态转换",
  "priority": "critical",
  "test_data": {
   "退票订单号": "CR2026050003",
   "付款计划类型": "仅撤销",
   "初始状态": "已进入SAP",
   "目标状态": "已完成"
  },
  "test_case_steps": [
   {
    "step": "创建并提交仅包含撤销操作的CR退票订单CR2026050003",
    "result": "订单状态直接为\"已进入SAP\"（业务规则：仅含撤销的订单不经过自动对接流程）"
   },
   {
    "step": "CC完成SAP手工撤销操作后返回DMS点击【确认完成】",
    "result": "订单状态由\"已进入SAP\"变更为\"已完成\""
   }
  ]
 },
 {
  "name": "人工及配件退单-根据合同编号关联历史DR订单",
  "case_number": "TC-PR2-CR-008",
  "module": "服务退单退票",
  "case_type": "functional",
  "preconditions": "历史DR订单DR2026040001存在且关联合同Contract020；经销商账号 dealer01 已登录DMS",
  "remarks": "关联需求 REQ-CR-003 / FP-014",
  "priority": "high",
  "test_data": {
   "合同编号": "Contract020",
   "历史DR订单号": "DR2026040001",
   "退单类型": "配件及人工退单"
  },
  "test_case_steps": [
   {
    "step": "经销商dealer01进入人工及配件退单创建页，填写合同编号Contract020",
    "result": "退单创建页正常打开"
   },
   {
    "step": "提交退单申请",
    "result": "系统根据合同编号Contract020自动关联历史DR订单DR2026040001，人工及配件退单创建成功"
   }
  ]
 },
 {
  "name": "人工及配件退单-CC确认完成后原DR订单状态调整为已完成",
  "case_number": "TC-PR2-CR-009",
  "module": "服务退单退票",
  "case_type": "functional",
  "preconditions": "原DR订单DR2026040001状态=已进入SAP（DR订单中间态，与DR状态机一致）；人工及配件退单CRDR2026050001已创建并关联该订单；CC账号cc01已登录DMS（独立准备，不依赖其他用例）",
  "remarks": "关联需求 REQ-CR-003 / FP-014 / 数据联动",
  "priority": "critical",
  "test_data": {
   "退单号": "CRDR2026050001",
   "原DR订单号": "DR2026040001",
   "原DR订单初始状态": "已进入SAP",
   "原DR订单目标状态": "已完成"
  },
  "test_case_steps": [
   {
    "step": "CC账号cc01在SAP完成操作后返回DMS打开退单CRDR2026050001",
    "result": "退单详情正常展示"
   },
   {
    "step": "点击【确认完成】按钮完成单据撤销",
    "result": "退单确认完成成功，单据撤销生效"
   },
   {
    "step": "查询原DR订单DR2026040001状态",
    "result": "原DR订单状态由\"已进入SAP\"调整为\"已完成\""
   }
  ]
 },
 {
  "name": "人工及配件退单-只能整单操作不可部分退",
  "case_number": "TC-PR2-CR-010",
  "module": "服务退单退票",
  "case_type": "functional",
  "preconditions": "人工及配件退单CRDR2026050002已创建，包含2条配件明细",
  "remarks": "关联需求 REQ-CR-003 / FP-014 / 边界场景",
  "priority": "high",
  "test_data": {
   "退单号": "CRDR2026050002",
   "明细条数": 2,
   "操作范围": "整单"
  },
  "test_case_steps": [
   {
    "step": "打开人工及配件退单CRDR2026050002",
    "result": "退单详情展示2条配件明细"
   },
   {
    "step": "尝试只选择其中1条明细进行退单操作",
    "result": "系统禁止部分退单，提示\"退单只能整单操作\"，无法选择部分明细提交"
   },
   {
    "step": "整单提交确认",
    "result": "整单退单操作成功"
   }
  ]
 },
 {
  "name": "人工及配件退单-状态流转申请撤销至已完成",
  "case_number": "TC-PR2-CR-011",
  "module": "服务退单退票",
  "case_type": "functional",
  "preconditions": "人工及配件退单CRDR2026050003已创建；CC账号cc01已登录DMS",
  "remarks": "关联需求 REQ-CR-003 / FP-014 / 状态转换",
  "priority": "critical",
  "test_data": {
   "退单号": "CRDR2026050003",
   "初始状态": "申请撤销",
   "目标状态": "已完成"
  },
  "test_case_steps": [
   {
    "step": "创建人工及配件退单并提交",
    "result": "退单状态为\"申请撤销\""
   },
   {
    "step": "CC完成SAP操作后返回DMS点击【确认完成】",
    "result": "退单状态由\"申请撤销\"变更为\"已完成\""
   }
  ]
 },
 {
  "name": "人工及配件退单-关联不到历史DR订单处理",
  "case_number": "TC-PR2-CR-012",
  "module": "服务退单退票",
  "case_type": "functional",
  "preconditions": "合同编号Contract021下不存在历史DR订单",
  "remarks": "关联需求 REQ-CR-003 / FP-014 / 异常场景",
  "priority": "high",
  "test_data": {
   "合同编号": "Contract021",
   "历史DR订单": "不存在"
  },
  "test_case_steps": [
   {
    "step": "进入人工及配件退单创建页，填写不存在的合同编号Contract021",
    "result": "退单创建页正常打开"
   },
   {
    "step": "提交退单申请",
    "result": "系统提示\"未找到该合同关联的历史DR订单，无法退单\"，退单未创建"
   }
  ]
 },
 {
  "name": "服务退票订单-退票后原订单付款计划状态联动",
  "case_number": "TC-PR2-CR-013",
  "module": "服务退单退票",
  "case_type": "functional",
  "preconditions": "原服务订单ZCS2026040001（历史订单，不与POS模块新建订单冲突）含3期付款计划，第1期=已开票、第2~3期=未开票（退票针对已开票期，未开票期走撤销流程）；CR退票订单CR2026050004已对第1期完成退票",
  "remarks": "关联需求 REQ-CR-001 / FP-012 / 数据联动",
  "priority": "high",
  "test_data": {
   "原服务订单号": "ZCS2026040001",
   "退票期次": "第1期",
   "退票订单号": "CR2026050004",
   "第1期退票前状态": "已开票",
   "第1期退票后状态": "已退票",
   "第2期3期保持状态": "未开票"
  },
  "test_case_steps": [
   {
    "step": "完成CR退票订单CR2026050004的退票（针对第1期，该期已开票）",
    "result": "退票完成"
   },
   {
    "step": "查询原服务订单ZCS2026040001付款周期",
    "result": "第1期付款计划状态由\"已开票\"标记为\"已退票\"，第2期、第3期保持\"未开票\"不变"
   }
  ]
 },
 {
  "name": "撤销付款计划-退票与撤销混合场景",
  "case_number": "TC-PR2-CR-014",
  "module": "服务退单退票",
  "case_type": "functional",
  "preconditions": "CR退票订单CR2026050005包含第1期退票（已开票）与第2期撤销（未开票）两类明细；CC账号cc01已登录DMS；SAP Mock可用",
  "remarks": "关联需求 REQ-CR-002 / FP-013 / 场景补充",
  "priority": "critical",
  "test_data": {
   "退票订单号": "CR2026050005",
   "退票明细": "第1期金额1000.00",
   "撤销付款计划": "第2期"
  },
  "test_case_steps": [
   {
    "step": "提交包含第1期退票+第2期撤销的CR退票订单",
    "result": "订单创建成功，第1期退票部分自动对接SAP，第2期撤销不自动对接"
   },
   {
    "step": "查看订单状态",
    "result": "订单状态=已进入SAP（退票部分已对接，撤销部分待CC手工处理）"
   },
   {
    "step": "CC在SAP手工完成第2期撤销操作（Mock）后返回DMS点击【确认完成】",
    "result": "订单状态变更为已完成，第1期退票记录与第2期撤销记录均处理完成"
   }
  ]
 },
 {
  "name": "撤销付款计划-已开票付款计划不可撤销",
  "case_number": "TC-PR2-CR-015",
  "module": "服务退单退票",
  "case_type": "functional",
  "preconditions": "原合同Contract003存在，第1期付款计划状态=已开票；经销商账号dealer01已登录DMS",
  "remarks": "关联需求 REQ-CR-002 / FP-013 / 异常场景补充",
  "priority": "high",
  "test_data": {
   "原合同付款计划状态": "已开票",
   "撤销操作": "对已开票第1期发起撤销"
  },
  "test_case_steps": [
   {
    "step": "进入服务退票订单创建页，对已开票的第1期付款计划选择撤销操作",
    "result": "系统拒绝该操作"
   },
   {
    "step": "查看系统提示",
    "result": "系统提示\"已开票付款计划不可撤销，请走退票流程\"，退票订单未创建"
   }
  ]
 },
 {
  "name": "撤销付款计划-SAP手工撤销操作失败处理",
  "case_number": "TC-PR2-CR-016",
  "module": "服务退单退票",
  "case_type": "functional",
  "preconditions": "CR退票订单CR2026050006包含撤销付款计划，状态=已进入SAP；CC账号cc01已登录DMS；SAP Mock配置为失败",
  "remarks": "关联需求 REQ-CR-002 / FP-013 / 异常场景补充",
  "priority": "high",
  "test_data": {
   "退票订单号": "CR2026050006",
   "SAP响应": "失败",
   "订单状态": "已进入SAP"
  },
  "test_case_steps": [
   {
    "step": "CC在SAP手工执行撤销操作（Mock返回失败）",
    "result": "SAP撤销操作失败"
   },
   {
    "step": "CC返回DMS查看订单状态",
    "result": "订单状态保持\"已进入SAP\"不变，系统展示可读的失败提示，支持重新确认"
   },
   {
    "step": "SAP Mock恢复成功，CC重新执行撤销并返回DMS点击【确认完成】",
    "result": "订单状态由\"已进入SAP\"变更为\"已完成\""
   }
  ]
 },
 {
  "name": "撤销付款计划-多个撤销计划依次确认完成",
  "case_number": "TC-PR2-CR-017",
  "module": "服务退单退票",
  "case_type": "functional",
  "preconditions": "CR退票订单CR2026050007包含2个撤销付款计划；CC账号cc01已登录DMS；SAP Mock可用",
  "remarks": "关联需求 REQ-CR-002 / FP-013 / 场景补充",
  "priority": "high",
  "test_data": {
   "退票订单号": "CR2026050007",
   "撤销计划数": 2,
   "目标状态": "已完成"
  },
  "test_case_steps": [
   {
    "step": "提交含2个撤销付款计划的CR退票订单",
    "result": "订单创建成功，状态=已进入SAP"
   },
   {
    "step": "CC在SAP依次完成2个付款计划的撤销操作（Mock）",
    "result": "2个撤销操作均成功"
   },
   {
    "step": "CC返回DMS点击【确认完成】",
    "result": "订单状态由\"已进入SAP\"变更为\"已完成\"，2个撤销计划均标记处理成功"
   }
  ]
 },
 {
  "name": "服务退票订单-退票金额为0或负值拒绝",
  "case_number": "TC-PR2-CR-018",
  "module": "服务退单退票",
  "case_type": "functional",
  "preconditions": "原合同Contract004存在且含已开票付款计划；经销商账号dealer01已登录DMS",
  "remarks": "关联需求 REQ-CR-001 / FP-012 / 边界值补充",
  "priority": "high",
  "test_data": {
   "退票金额1": 0.0,
   "退票金额2": -100.0
  },
  "test_case_steps": [
   {
    "step": "进入服务退票订单创建页，退票金额输入0.00并提交",
    "result": "系统拒绝提交，提示\"退票金额必须大于0\""
   },
   {
    "step": "退票金额输入-100.00并提交",
    "result": "系统拒绝提交，提示\"退票金额必须大于0\"，退票订单未创建"
   }
  ]
 },
 {
  "name": "服务退票订单-退票金额大于原付款金额拒绝",
  "case_number": "TC-PR2-CR-019",
  "module": "服务退单退票",
  "case_type": "functional",
  "preconditions": "原合同Contract005存在，第1期付款金额=1000.00；经销商账号dealer01已登录DMS",
  "remarks": "关联需求 REQ-CR-001 / FP-012 / 异常场景补充",
  "priority": "high",
  "test_data": {
   "原付款金额": 1000.0,
   "退票金额": 1500.0
  },
  "test_case_steps": [
   {
    "step": "进入服务退票订单创建页，对第1期（付款金额1000.00）填写退票金额1500.00",
    "result": "退票金额可录入"
   },
   {
    "step": "提交退票申请",
    "result": "系统拒绝提交，提示\"退票金额不能大于原付款金额\"，退票订单未创建"
   }
  ]
 },
 {
  "name": "服务退票订单-相同退票明细重复提交幂等性",
  "case_number": "TC-PR2-CR-020",
  "module": "服务退单退票",
  "case_type": "functional",
  "preconditions": "原合同Contract006存在，第1期已开票未退票；经销商账号dealer01已登录DMS",
  "remarks": "关联需求 REQ-CR-001 / FP-012 / 幂等性补充",
  "priority": "medium",
  "test_data": {
   "原合同编号": "Contract006",
   "原合同明细行号": 1,
   "原合同明细付款行号": 1,
   "重复次数": 2
  },
  "test_case_steps": [
   {
    "step": "提交退票明细（Contract006、行号1、付款行号1、金额800.00）",
    "result": "退票订单创建成功"
   },
   {
    "step": "再次提交完全相同的退票明细",
    "result": "系统拒绝重复退票（提示\"该明细已存在退票申请\"或返回已存在订单号），未产生重复退票数据"
   }
  ]
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 16. ws-PR-1-test_cases_dressup_module_06_rule

- 来源：`workspace/testcase/PR-1/test_cases_dressup_module_06_rule.jsonl`　分组：PR-1　用例数：12

```json
[
 {
  "name": "多个弹窗按排队逻辑依次出现",
  "case_number": "TC-PR1-RULE-001",
  "module": "弹窗规则",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "用户已登录并处于房间内；关闭『隐藏特效』开关；当前无其他弹窗展示；用户未佩戴相关装扮",
  "remarks": "关联需求 REQ-DEC-005（需求点5 多个弹窗排队逻辑）",
  "test_data": {
   "弹窗1": "麦位框-萌爪闪闪（t=0秒发放）",
   "弹窗2": "座驾-星河战舰（t=1.0秒发放）",
   "发放间隔": "1.0秒"
  },
  "test_case_steps": [
   {
    "step": "服务端在t=0发放麦位框-萌爪闪闪，弹窗1弹出",
    "result": "弹窗1立即展示，仅展示麦位框-萌爪闪闪"
   },
   {
    "step": "服务端在t=1.0秒发放座驾-星河战舰，观察是否出现第2个弹窗",
    "result": "弹窗1操作完成前，弹窗2不弹出、不叠加展示"
   },
   {
    "step": "在弹窗1上点击『立即佩戴』完成操作",
    "result": "弹窗1关闭后，弹窗2立即弹出展示座驾-星河战舰"
   }
  ]
 },
 {
  "name": "开启隐藏特效时获得装扮不弹出弹窗",
  "case_number": "TC-PR1-RULE-002",
  "module": "弹窗规则",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "用户已开启『隐藏特效』开关；用户处于房间内",
  "remarks": "关联需求 REQ-DEC-005（需求点5 隐藏特效不弹窗）",
  "test_data": {
   "隐藏特效开关": "开启",
   "发放装扮": "麦位框-萌爪闪闪"
  },
  "test_case_steps": [
   {
    "step": "服务端向用户发放1件装扮：麦位框-萌爪闪闪",
    "result": "不弹出任何装扮弹窗"
   },
   {
    "step": "前往背包/个性装扮页查看该装扮",
    "result": "麦位框-萌爪闪闪已发放到背包，可在装扮列表中查到（仅不弹窗，不影响发放）"
   }
  ]
 },
 {
  "name": "关闭隐藏特效后获得装扮恢复弹窗",
  "case_number": "TC-PR1-RULE-003",
  "module": "弹窗规则",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "用户当前已开启『隐藏特效』开关",
  "remarks": "关联需求 REQ-DEC-005（需求点5 隐藏特效开关恢复）",
  "test_data": {
   "初始开关状态": "开启",
   "操作": "关闭隐藏特效",
   "发放装扮": "麦位框-萌爪闪闪"
  },
  "test_case_steps": [
   {
    "step": "在设置中关闭『隐藏特效』开关",
    "result": "开关状态变为关闭，设置保存成功"
   },
   {
    "step": "服务端发放1件装扮：麦位框-萌爪闪闪",
    "result": "正常弹出装扮弹窗展示该装扮"
   }
  ]
 },
 {
  "name": "已佩戴的装扮再次获得时不弹出该装扮弹窗",
  "case_number": "TC-PR1-RULE-004",
  "module": "弹窗规则",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "用户已佩戴麦位框-萌爪闪闪；关闭『隐藏特效』开关",
  "remarks": "关联需求 REQ-DEC-005（需求点5 已佩戴装扮再次获得不弹窗）；入包断言：不弹窗但发放须入包/续期",
  "test_data": {
   "当前已佩戴": "麦位框-萌爪闪闪",
   "再次发放": "麦位框-萌爪闪闪（同装扮）",
   "入包校验": "背包中该装扮数量+1或有效期续期"
  },
  "test_case_steps": [
   {
    "step": "服务端再次发放麦位框-萌爪闪闪",
    "result": "不弹出该装扮的弹窗，无任何弹窗出现"
   },
   {
    "step": "查看背包中该装扮的持有情况",
    "result": "再次发放的麦位框-萌爪闪闪已入包（数量按发放规则增加或有效期叠加/续期），发放未因『已佩戴不弹窗』而丢失"
   }
  ]
 },
 {
  "name": "已佩戴某类型装扮后获得同类型其他装扮正常弹窗",
  "case_number": "TC-PR1-RULE-005",
  "module": "弹窗规则",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "用户已佩戴麦位框-萌爪闪闪；关闭『隐藏特效』开关",
  "remarks": "关联需求 REQ-DEC-005（需求点5 只会弹非当前佩戴的装扮）",
  "test_data": {
   "当前已佩戴": "麦位框-萌爪闪闪",
   "再次发放": "麦位框-星河之恋（同类型不同装扮）"
  },
  "test_case_steps": [
   {
    "step": "服务端发放麦位框-星河之恋",
    "result": "弹出弹窗展示麦位框-星河之恋（该装扮非当前佩戴，正常弹窗）"
   }
  ]
 },
 {
  "name": "排队中关闭第一个弹窗后立即弹出下一个弹窗",
  "case_number": "TC-PR1-RULE-006",
  "module": "弹窗规则",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "弹窗1（麦位框-萌爪闪闪）展示中；弹窗2（座驾-星河战舰）排队等待中",
  "remarks": "关联需求 REQ-DEC-005（需求点5 排队逻辑）；入包断言：关闭弹窗1不佩戴但麦位框需入包",
  "test_data": {
   "弹窗1": "麦位框-萌爪闪闪",
   "弹窗2": "座驾-星河战舰",
   "操作": "点击弹窗1的关闭按钮",
   "入包校验": "弹窗1的麦位框已入包未佩戴"
  },
  "test_case_steps": [
   {
    "step": "点击弹窗1的『关闭』按钮",
    "result": "弹窗1直接关闭，麦位框-萌爪闪闪未被佩戴"
   },
   {
    "step": "观察弹窗2的出现",
    "result": "弹窗1关闭后弹窗2立即弹出展示座驾-星河战舰"
   },
   {
    "step": "查看背包中麦位框-萌爪闪闪",
    "result": "弹窗1关闭的装扮已入包（可查到，未佩戴），关闭操作不导致发放丢失"
   }
  ]
 },
 {
  "name": "合并发放时已佩戴装扮被过滤仅弹非当前佩戴的装扮",
  "case_number": "TC-PR1-RULE-007",
  "module": "弹窗规则",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "用户已佩戴座驾-星河战舰；关闭『隐藏特效』开关",
  "remarks": "关联需求 REQ-DEC-005（需求点5 已佩戴过滤+需求点1 合并）；标题统一口径：弹窗内展示数=1时显示『获得装扮』（与 TITLE-001/003 一致）",
  "test_data": {
   "当前已佩戴": "座驾-星河战舰",
   "0.5秒内发放": [
    "座驾-星河战舰（已佩戴）",
    "个人铭牌-闪耀之星"
   ],
   "预期弹窗内容": "仅个人铭牌-闪耀之星",
   "预期标题": "获得装扮"
  },
  "test_case_steps": [
   {
    "step": "服务端0.5秒内同时发放座驾-星河战舰（用户已佩戴）和个人铭牌-闪耀之星",
    "result": "弹窗弹出，仅展示个人铭牌-闪耀之星，已佩戴的座驾-星河战舰不进入弹窗"
   },
   {
    "step": "查看弹窗标题与卡片数",
    "result": "标题显示『获得装扮』，弹窗内仅1张卡片（个人铭牌-闪耀之星）"
   }
  ]
 },
 {
  "name": "隐藏特效开启时合并发放多件全部抑制不弹窗",
  "case_number": "TC-PR1-RULE-008",
  "module": "弹窗规则",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "用户已开启『隐藏特效』开关；用户处于房间内",
  "remarks": "关联需求 REQ-DEC-005（需求点5 隐藏特效不弹窗 × 需求点1 合并）",
  "test_data": {
   "隐藏特效开关": "开启",
   "0.5秒内发放": [
    "麦位框-萌爪闪闪",
    "座驾-星河战舰",
    "个人铭牌-闪耀之星"
   ],
   "发放间隔": "0.2秒/0.2秒"
  },
  "test_case_steps": [
   {
    "step": "服务端0.5秒内连续发放3件装扮（麦位框-萌爪闪闪、座驾-星河战舰、个人铭牌-闪耀之星）",
    "result": "不弹出任何装扮弹窗，无弹窗排队残留"
   },
   {
    "step": "查看背包中3件装扮",
    "result": "3件装扮均已入包（可在背包中查到），隐藏特效仅抑制弹窗，不影响发放"
   }
  ]
 },
 {
  "name": "隐藏特效与已佩戴过滤双条件叠加时不弹窗",
  "case_number": "TC-PR1-RULE-009",
  "module": "弹窗规则",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "用户已开启『隐藏特效』开关；用户已佩戴麦位框-萌爪闪闪",
  "remarks": "关联需求 REQ-DEC-005（需求点5 双抑制条件叠加）",
  "test_data": {
   "隐藏特效开关": "开启",
   "当前已佩戴": "麦位框-萌爪闪闪",
   "发放装扮": [
    "麦位框-萌爪闪闪（已佩戴）",
    "座驾-星河战舰（未佩戴）"
   ]
  },
  "test_case_steps": [
   {
    "step": "服务端同时发放已佩戴的麦位框-萌爪闪闪与未佩戴的座驾-星河战舰",
    "result": "不弹出任何装扮弹窗（隐藏特效抑制全部弹窗）"
   },
   {
    "step": "查看背包中座驾-星河战舰",
    "result": "座驾-星河战舰已入包（可查到），发放未丢失"
   }
  ]
 },
 {
  "name": "隐藏特效关闭后已获得的装扮不再补弹弹窗",
  "case_number": "TC-PR1-RULE-010",
  "module": "弹窗规则",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "用户已开启『隐藏特效』开关；服务端在开启期间发放麦位框-萌爪闪闪（未弹窗）",
  "remarks": "关联需求 REQ-DEC-005（需求点5）；需求未明确隐藏特效期间获得装扮在开关关闭后是否补弹，按『不补弹』假设编写，待产品确认",
  "test_data": {
   "发放时机": "隐藏特效开启期间",
   "发放装扮": "麦位框-萌爪闪闪",
   "操作": "关闭隐藏特效",
   "补弹预期": "不补弹"
  },
  "test_case_steps": [
   {
    "step": "隐藏特效开启期间服务端发放麦位框-萌爪闪闪",
    "result": "不弹出弹窗，装扮已入包"
   },
   {
    "step": "在设置中关闭『隐藏特效』开关",
    "result": "开关状态变为关闭，无任何补弹弹窗出现（已获得的装扮不补弹，待产品确认）"
   }
  ]
 },
 {
  "name": "排队中退出房间后的队列处理",
  "case_number": "TC-PR1-RULE-011",
  "module": "弹窗规则",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "弹窗1（麦位框-萌爪闪闪）展示中；弹窗2（座驾-星河战舰）排队等待中",
  "remarks": "关联需求 REQ-DEC-005（需求点5）；需求未明确排队中退出房间的队列处置，按『队列清除、重进不补弹』假设编写，待产品确认",
  "test_data": {
   "弹窗1": "麦位框-萌爪闪闪（展示中）",
   "弹窗2": "座驾-星河战舰（排队中）",
   "操作": "在弹窗1展示期间退出房间"
  },
  "test_case_steps": [
   {
    "step": "在弹窗1展示期间退出当前房间",
    "result": "退出房间成功，弹窗1与排队的弹窗2均被关闭/清除，无残留弹窗"
   },
   {
    "step": "重新进入房间，观察是否补弹",
    "result": "按假设不补弹（若产品定义重进后补弹则以产品规则为准，标注待确认）；进入房间无异常"
   }
  ]
 },
 {
  "name": "连续快速发放多个弹窗的队列顺序与完整性",
  "case_number": "TC-PR1-RULE-012",
  "module": "弹窗规则",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "用户已登录并处于房间内；关闭『隐藏特效』开关；服务端连续发放5件装扮（间隔均>0.5秒，不触发合并）",
  "remarks": "关联需求 REQ-DEC-005（需求点5）；队列上限需求未明确，若存在上限需产品确认",
  "test_data": {
   "发放件数": 5,
   "发放间隔": "0.8秒（>0.5秒）",
   "发放顺序": [
    "装扮A",
    "装扮B",
    "装扮C",
    "装扮D",
    "装扮E"
   ]
  },
  "test_case_steps": [
   {
    "step": "服务端按0.8秒间隔连续发放5件装扮",
    "result": "5个弹窗按发放顺序逐个弹出，每个弹窗操作完成后再弹出下一个，无弹窗丢失、无顺序错乱"
   },
   {
    "step": "逐个完成5个弹窗的操作",
    "result": "5个弹窗全部展示完成，最终无残留弹窗、无队列卡死"
   }
  ]
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 17. ws-PR-2-test_cases_module_05_rf

- 来源：`workspace/testcase/PR-2/test_cases_module_05_rf.jsonl`　分组：PR-2　用例数：20

```json
[
 {
  "name": "服务退票订单创建-三要素齐全创建成功",
  "case_number": "TC-PR2-RF-101",
  "module": "服务退单/退票",
  "case_type": "functional",
  "preconditions": "原合同Contract001存在且含已开票付款计划；原合同明细行号与付款行号有效；经销商账号 dealer01 已登录DMS",
  "remarks": "关联需求 REQ-CR-001 / FP-028",
  "priority": "critical",
  "test_data": {
   "原合同编号": "Contract001",
   "原合同明细行号": 1,
   "原合同明细付款行号": 1,
   "退票金额": 1000.0
  },
  "test_case_steps": [
   {
    "step": "经销商dealer01登录DMS，进入服务退票订单创建页",
    "result": "成功进入创建页"
   },
   {
    "step": "填写退票明细：原合同编号Contract001、原合同明细行号1、原合同明细付款行号1",
    "result": "退票明细录入成功"
   },
   {
    "step": "提交退票申请",
    "result": "退票订单创建成功，退票明细包含原合同编号、明细行号、付款行号三要素，状态为已提交"
   }
  ]
 },
 {
  "name": "服务退票订单创建-原合同编号缺失拒绝",
  "case_number": "TC-PR2-RF-102",
  "module": "服务退单/退票",
  "case_type": "exception",
  "preconditions": "经销商账号 dealer01 已登录DMS",
  "remarks": "关联需求 REQ-CR-001 / FP-028 / 三要素缺失",
  "priority": "critical",
  "test_data": {
   "原合同编号": "",
   "原合同明细行号": 1,
   "原合同明细付款行号": 1
  },
  "test_case_steps": [
   {
    "step": "进入服务退票订单创建页",
    "result": "成功进入创建页"
   },
   {
    "step": "原合同编号留空，填写明细行号与付款行号",
    "result": "明细行号与付款行号可填写"
   },
   {
    "step": "提交退票申请",
    "result": "系统拒绝创建退票订单，提示\"原合同编号为必填项\"，退票订单未创建"
   }
  ]
 },
 {
  "name": "服务退票订单创建-原合同明细行号缺失拒绝",
  "case_number": "TC-PR2-RF-103",
  "module": "服务退单/退票",
  "case_type": "exception",
  "preconditions": "经销商账号 dealer01 已登录DMS",
  "remarks": "关联需求 REQ-CR-001 / FP-028 / 三要素缺失",
  "priority": "critical",
  "test_data": {
   "原合同编号": "Contract001",
   "原合同明细行号": "",
   "原合同明细付款行号": 1
  },
  "test_case_steps": [
   {
    "step": "进入服务退票订单创建页",
    "result": "成功进入创建页"
   },
   {
    "step": "填写原合同编号Contract001、付款行号1，明细行号留空",
    "result": "原合同编号与付款行号可填写"
   },
   {
    "step": "提交退票申请",
    "result": "系统拒绝创建退票订单，提示\"原合同明细行号为必填项\"，退票订单未创建"
   }
  ]
 },
 {
  "name": "服务退票订单创建-原合同明细付款行号缺失拒绝",
  "case_number": "TC-PR2-RF-104",
  "module": "服务退单/退票",
  "case_type": "exception",
  "preconditions": "经销商账号 dealer01 已登录DMS",
  "remarks": "关联需求 REQ-CR-001 / FP-028 / 三要素缺失",
  "priority": "critical",
  "test_data": {
   "原合同编号": "Contract001",
   "原合同明细行号": 1,
   "原合同明细付款行号": ""
  },
  "test_case_steps": [
   {
    "step": "进入服务退票订单创建页",
    "result": "成功进入创建页"
   },
   {
    "step": "填写原合同编号Contract001、明细行号1，付款行号留空",
    "result": "原合同编号与明细行号可填写"
   },
   {
    "step": "提交退票申请",
    "result": "系统拒绝创建退票订单，提示\"原合同明细付款行号为必填项\"，退票订单未创建"
   }
  ]
 },
 {
  "name": "退票匹配SAP行号-匹配成功创建CR退票订单",
  "case_number": "TC-PR2-RF-105",
  "module": "服务退单/退票",
  "case_type": "functional",
  "preconditions": "原合同Contract001的付款行号1存在对应SAP行号SAP-LINE-001；经销商账号 dealer01 已登录DMS",
  "remarks": "关联需求 REQ-CR-001 / FP-029",
  "priority": "critical",
  "test_data": {
   "原合同编号": "Contract001",
   "原合同明细行号": 1,
   "原合同明细付款行号": 1,
   "匹配SAP行号": "SAP-LINE-001"
  },
  "test_case_steps": [
   {
    "step": "发起退票申请，退票明细填写原合同Contract001、明细行号1、付款行号1",
    "result": "退票明细录入成功"
   },
   {
    "step": "提交退票申请",
    "result": "系统成功匹配原付款明细SAP行号SAP-LINE-001，创建CR退票订单，订单状态为已提交"
   }
  ]
 },
 {
  "name": "退票匹配SAP行号-匹配失败处理",
  "case_number": "TC-PR2-RF-106",
  "module": "服务退单/退票",
  "case_type": "exception",
  "preconditions": "原合同Contract002存在但付款行号3无对应SAP行号；经销商账号 dealer01 已登录DMS",
  "remarks": "关联需求 REQ-CR-001 / FP-029 / 异常场景",
  "priority": "critical",
  "test_data": {
   "原合同编号": "Contract002",
   "原合同明细行号": 1,
   "原合同明细付款行号": 3,
   "匹配SAP行号": "不存在"
  },
  "test_case_steps": [
   {
    "step": "发起退票申请，退票明细填写原合同Contract002、明细行号1、付款行号3",
    "result": "退票明细录入成功"
   },
   {
    "step": "提交退票申请",
    "result": "系统无法匹配原付款明细SAP行号，返回明确错误提示，退票订单未创建，无脏数据"
   }
  ]
 },
 {
  "name": "服务退票自动对接SAP-部分自动对接",
  "case_number": "TC-PR2-RF-107",
  "module": "服务退单/退票",
  "case_type": "functional",
  "preconditions": "CR退票订单CR2026050001已创建；SAP对接接口Mock可用",
  "remarks": "关联需求 REQ-CR-001 / FP-030",
  "priority": "high",
  "test_data": {
   "退票订单号": "CR2026050001",
   "服务退票部分金额": 1000.0
  },
  "test_case_steps": [
   {
    "step": "CR退票订单创建成功后触发对接",
    "result": "服务退票部分自动对接SAP接口调用成功"
   },
   {
    "step": "查看退票订单状态",
    "result": "退票订单状态由\"已提交\"变更为\"已进入SAP\"，服务退票部分对接数据正确"
   }
  ]
 },
 {
  "name": "撤销付款计划-未开票的撤销需CC手工在SAP操作",
  "case_number": "TC-PR2-RF-108",
  "module": "服务退单/退票",
  "case_type": "security",
  "preconditions": "CR退票订单CR2026050002包含未开票付款计划（撤销类型）；CC账号cc01已登录DMS；SAP Mock可用",
  "remarks": "关联需求 REQ-CR-002 / FP-031",
  "priority": "high",
  "test_data": {
   "退票订单号": "CR2026050002",
   "付款计划类型": "撤销",
   "CC账号": "cc01"
  },
  "test_case_steps": [
   {
    "step": "提交包含撤销付款计划的CR退票订单",
    "result": "订单创建成功，未开票的撤销付款计划不自动对接SAP"
   },
   {
    "step": "检查SAP对接接口Mock调用记录",
    "result": "SAP自动对接接口无该撤销付款计划的调用记录（需CC手工操作）"
   },
   {
    "step": "CC账号cc01在SAP手工执行撤销操作（Mock）",
    "result": "SAP撤销操作完成，CC在SAP可正常操作该撤销付款计划"
   }
  ]
 },
 {
  "name": "CC退票完成确认-完成SAP操作后DMS确认成功",
  "case_number": "TC-PR2-RF-109",
  "module": "服务退单/退票",
  "case_type": "functional",
  "preconditions": "CR退票订单CR2026050001状态=已进入SAP；CC账号cc01已登录DMS",
  "remarks": "关联需求 REQ-CR-002 / FP-032",
  "priority": "critical",
  "test_data": {
   "退票订单号": "CR2026050001",
   "初始状态": "已进入SAP",
   "CC账号": "cc01"
  },
  "test_case_steps": [
   {
    "step": "CC账号cc01完成SAP退票操作后返回DMS，打开CR退票订单CR2026050001",
    "result": "退票订单详情正常展示"
   },
   {
    "step": "点击【退票完成确认】按钮",
    "result": "退票完成确认成功，订单状态变更为\"已完成\"，操作记录新增CC确认记录"
   }
  ]
 },
 {
  "name": "CC退票完成确认-非CC角色越权拒绝",
  "case_number": "TC-PR2-RF-110",
  "module": "服务退单/退票",
  "case_type": "security",
  "preconditions": "CR退票订单CR2026050003状态=已进入SAP；普通经销商dealer02已登录DMS（非CC角色）",
  "remarks": "关联需求 REQ-CR-002 / FP-032 / 权限控制",
  "priority": "critical",
  "test_data": {
   "退票订单号": "CR2026050003",
   "操作角色": "dealer02（普通经销商）",
   "初始状态": "已进入SAP"
  },
  "test_case_steps": [
   {
    "step": "普通经销商dealer02打开CR退票订单CR2026050003",
    "result": "订单详情正常展示"
   },
   {
    "step": "尝试点击【退票完成确认】按钮或直接调用确认接口",
    "result": "确认按钮对非CC角色不可见，或接口返回无权限错误（403），订单状态保持\"已进入SAP\"不变"
   }
  ]
 },
 {
  "name": "服务退票状态流转-已提交至已完成全流程",
  "case_number": "TC-PR2-RF-111",
  "module": "服务退单/退票",
  "case_type": "functional",
  "preconditions": "CR退票订单CR2026050004已创建，状态=已提交；SAP退票处理Mock返回成功；CC账号cc01已登录DMS",
  "remarks": "关联需求 REQ-CR-002 / FP-033 / 状态转换",
  "priority": "critical",
  "test_data": {
   "退票订单号": "CR2026050004",
   "初始状态": "已提交",
   "中间状态": "已进入SAP",
   "目标状态": "已完成"
  },
  "test_case_steps": [
   {
    "step": "提交CR退票订单",
    "result": "订单状态=已提交"
   },
   {
    "step": "服务退票部分自动对接SAP",
    "result": "订单状态变更为\"已进入SAP\""
   },
   {
    "step": "CC完成SAP操作后返回DMS点击【退票完成确认】",
    "result": "订单状态变更为\"已完成\""
   }
  ]
 },
 {
  "name": "服务退票状态流转-仅含撤销操作时已进入SAP至已完成",
  "case_number": "TC-PR2-RF-112",
  "module": "服务退单/退票",
  "case_type": "boundary",
  "preconditions": "CR退票订单CR2026050005仅包含撤销（Cancel）类型的付款计划，无退票明细；CC账号cc01已登录DMS",
  "remarks": "关联需求 REQ-CR-002 / FP-033 / 状态转换边界",
  "priority": "critical",
  "test_data": {
   "退票订单号": "CR2026050005",
   "付款计划类型": "仅撤销",
   "初始状态": "已进入SAP",
   "目标状态": "已完成"
  },
  "test_case_steps": [
   {
    "step": "提交仅包含撤销操作的CR退票订单",
    "result": "订单状态直接为\"已进入SAP\"（不经过已提交后的自动对接流程）"
   },
   {
    "step": "CC完成SAP手工撤销操作后返回DMS点击【退票完成确认】",
    "result": "订单状态由\"已进入SAP\"变更为\"已完成\""
   }
  ]
 },
 {
  "name": "服务退票状态流转-非法状态跳转拦截",
  "case_number": "TC-PR2-RF-113",
  "module": "服务退单/退票",
  "case_type": "boundary",
  "preconditions": "CR退票订单CR2026050006状态=已提交；DMS接口可直接调用",
  "remarks": "关联需求 REQ-CR-002 / FP-033 / 状态机",
  "priority": "critical",
  "test_data": {
   "退票订单号": "CR2026050006",
   "初始状态": "已提交",
   "非法跳转目标": "已完成"
  },
  "test_case_steps": [
   {
    "step": "通过接口直接尝试将CR退票订单CR2026050006状态从已提交改为已完成（跳过已进入SAP）",
    "result": "接口返回状态机校验错误，拒绝非法跳转"
   },
   {
    "step": "查询该订单当前状态",
    "result": "订单状态保持\"已提交\"不变，未产生非法状态变更记录"
   }
  ]
 },
 {
  "name": "人工及配件退单-根据合同编号关联历史DR订单创建",
  "case_number": "TC-PR2-RF-114",
  "module": "服务退单/退票",
  "case_type": "functional",
  "preconditions": "历史DR订单DR2026040001存在且关联合同Contract020；经销商账号 dealer01 已登录DMS",
  "remarks": "关联需求 REQ-CR-003 / FP-034",
  "priority": "high",
  "test_data": {
   "合同编号": "Contract020",
   "历史DR订单号": "DR2026040001",
   "退单类型": "配件及人工退单"
  },
  "test_case_steps": [
   {
    "step": "经销商dealer01进入人工及配件退单创建页，填写合同编号Contract020",
    "result": "退单创建页正常打开"
   },
   {
    "step": "提交退单申请",
    "result": "系统根据合同编号Contract020自动关联历史DR订单DR2026040001，人工及配件退单创建成功"
   }
  ]
 },
 {
  "name": "人工及配件退单-关联不到历史DR订单处理",
  "case_number": "TC-PR2-RF-115",
  "module": "服务退单/退票",
  "case_type": "exception",
  "preconditions": "合同编号Contract021下不存在历史DR订单；经销商账号 dealer01 已登录DMS",
  "remarks": "关联需求 REQ-CR-003 / FP-034 / 异常场景",
  "priority": "high",
  "test_data": {
   "合同编号": "Contract021",
   "历史DR订单": "不存在"
  },
  "test_case_steps": [
   {
    "step": "进入人工及配件退单创建页，填写不存在的合同编号Contract021",
    "result": "退单创建页正常打开"
   },
   {
    "step": "提交退单申请",
    "result": "系统提示\"未找到该合同关联的历史DR订单，无法退单\"，退单未创建"
   }
  ]
 },
 {
  "name": "原DR订单状态调整-退单完成后调整为已完成",
  "case_number": "TC-PR2-RF-116",
  "module": "服务退单/退票",
  "case_type": "functional",
  "preconditions": "原DR订单DR2026040001状态=已确认（非终态）；人工及配件退单CRDR2026050001已创建并关联该订单；CC账号cc01已登录DMS",
  "remarks": "关联需求 REQ-CR-003 / FP-035 / 数据联动",
  "priority": "high",
  "test_data": {
   "退单号": "CRDR2026050001",
   "原DR订单号": "DR2026040001",
   "原DR订单初始状态": "已确认",
   "原DR订单目标状态": "已完成"
  },
  "test_case_steps": [
   {
    "step": "CC账号cc01完成SAP操作后返回DMS打开退单CRDR2026050001",
    "result": "退单详情正常展示"
   },
   {
    "step": "点击【确认完成】按钮完成单据撤销",
    "result": "退单确认完成成功，单据撤销生效"
   },
   {
    "step": "查询原DR订单DR2026040001状态",
    "result": "原DR订单状态由\"已确认\"调整为\"已完成\""
   }
  ]
 },
 {
  "name": "原DR订单状态调整-退单只能整单操作不可部分退",
  "case_number": "TC-PR2-RF-117",
  "module": "服务退单/退票",
  "case_type": "boundary",
  "preconditions": "人工及配件退单CRDR2026050002已创建，包含2条配件明细",
  "remarks": "关联需求 REQ-CR-003 / FP-035 / 边界场景",
  "priority": "high",
  "test_data": {
   "退单号": "CRDR2026050002",
   "明细条数": 2,
   "操作范围": "整单"
  },
  "test_case_steps": [
   {
    "step": "打开人工及配件退单CRDR2026050002",
    "result": "退单详情展示2条配件明细"
   },
   {
    "step": "尝试只选择其中1条明细进行退单操作",
    "result": "系统禁止部分退单，提示\"退单只能整单操作\"，无法选择部分明细提交"
   },
   {
    "step": "整单提交确认",
    "result": "整单退单操作成功"
   }
  ]
 },
 {
  "name": "配件退单状态流转-申请撤销至已完成",
  "case_number": "TC-PR2-RF-118",
  "module": "服务退单/退票",
  "case_type": "functional",
  "preconditions": "人工及配件退单CRDR2026050003已创建；CC账号cc01已登录DMS",
  "remarks": "关联需求 REQ-CR-003 / FP-036 / 状态转换",
  "priority": "high",
  "test_data": {
   "退单号": "CRDR2026050003",
   "初始状态": "申请撤销",
   "目标状态": "已完成"
  },
  "test_case_steps": [
   {
    "step": "创建人工及配件退单并提交",
    "result": "退单状态为\"申请撤销\""
   },
   {
    "step": "CC完成SAP操作后返回DMS点击【确认完成】",
    "result": "退单状态由\"申请撤销\"变更为\"已完成\""
   }
  ]
 },
 {
  "name": "配件退单状态流转-非法状态跳转拦截",
  "case_number": "TC-PR2-RF-119",
  "module": "服务退单/退票",
  "case_type": "boundary",
  "preconditions": "人工及配件退单CRDR2026050004状态=申请撤销；DMS接口可直接调用",
  "remarks": "关联需求 REQ-CR-003 / FP-036 / 状态机",
  "priority": "high",
  "test_data": {
   "退单号": "CRDR2026050004",
   "初始状态": "申请撤销",
   "非法跳转目标": "已完成"
  },
  "test_case_steps": [
   {
    "step": "通过接口直接尝试将退单CRDR2026050004状态从申请撤销改为已完成（跳过CC确认）",
    "result": "接口返回状态机校验错误，拒绝非法跳转"
   },
   {
    "step": "查询该退单当前状态",
    "result": "退单状态保持\"申请撤销\"不变，未产生非法状态变更记录"
   }
  ]
 },
 {
  "name": "服务退票订单创建-自由文本字段SQL注入与XSS防护",
  "case_number": "TC-PR2-RF-120",
  "module": "服务退单/退票",
  "case_type": "security",
  "preconditions": "经销商账号 dealer01 已登录DMS；原合同数据可独立构造",
  "remarks": "关联需求 REQ-CR-001 / FP-028 / 安全红线",
  "priority": "high",
  "test_data": {
   "原合同编号": "' OR '1'='1",
   "原合同明细行号": 1,
   "原合同明细付款行号": "<script>alert(1)</script>"
  },
  "test_case_steps": [
   {
    "step": "进入服务退票订单创建页",
    "result": "表单正常加载"
   },
   {
    "step": "原合同编号输入SQL注入Payload：' OR '1'='1，付款行号字段输入XSS Payload：<script>alert(1)</script>",
    "result": "系统拒绝提交并提示参数校验错误，Payload原样展示不执行，无500服务器错误"
   },
   {
    "step": "查询数据库订单表与系统日志",
    "result": "订单表无新增记录，日志中无SQL异常堆栈，无XSS脚本被执行痕迹"
   }
  ]
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 18. ws-PR-1-test_cases_dressup_module_01_merge

- 来源：`workspace/testcase/PR-1/test_cases_dressup_module_01_merge.jsonl`　分组：PR-1　用例数：10

```json
[
 {
  "name": "单件装扮获得时弹出单卡片弹窗",
  "case_number": "TC-PR1-MERGE-001",
  "module": "合并展示",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "用户已登录并处于房间内；关闭『隐藏特效』开关；服务端向用户发放1件装扮『麦位框-萌爪闪闪』（剩余有效期30天）；用户当前未佩戴该装扮",
  "remarks": "关联需求 REQ-DEC-001（需求点1 多个装扮合并展示）",
  "test_data": {
   "发放装扮数": 1,
   "装扮": "麦位框-萌爪闪闪",
   "剩余有效期": "30天",
   "发放间隔": "单件无间隔"
  },
  "test_case_steps": [
   {
    "step": "服务端向用户发放1件装扮：麦位框-萌爪闪闪",
    "result": "弹窗弹出，仅展示1张装扮卡片"
   },
   {
    "step": "观察弹窗内的滑动指示器与按钮区域",
    "result": "弹窗内无左右滑动指示器；底部仅显示1个按钮『立即佩戴』；标题显示『获得装扮』"
   }
  ]
 },
 {
  "name": "0.5秒内获得2件装扮合并到同一弹窗展示",
  "case_number": "TC-PR1-MERGE-002",
  "module": "合并展示",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "用户已登录并处于房间内；关闭『隐藏特效』开关；用户当前未佩戴『麦位框-萌爪闪闪』和『座驾-星河战舰』",
  "remarks": "关联需求 REQ-DEC-001（需求点1）",
  "test_data": {
   "发放装扮数": 2,
   "装扮1": "麦位框-萌爪闪闪",
   "装扮2": "座驾-星河战舰",
   "发放间隔": "0.3秒",
   "滑动操作": "左滑1次"
  },
  "test_case_steps": [
   {
    "step": "服务端在0.5秒内依次发放2件装扮：先发麦位框-萌爪闪闪，间隔0.3秒后发座驾-星河战舰",
    "result": "仅弹出1个弹窗，不出现2个独立弹窗"
   },
   {
    "step": "观察弹窗内容",
    "result": "弹窗内合并展示2张装扮卡片，可左右滑动切换预览；标题显示『获得2件装扮』；底部显示『佩戴当前』和『全部佩戴』2个按钮"
   },
   {
    "step": "在弹窗内向左滑动1次",
    "result": "从第1张（麦位框-萌爪闪闪）切换到第2张（座驾-星河战舰）预览，名称/有效期/说明文案同步切换，滑动切换功能正常"
   }
  ]
 },
 {
  "name": "0.5秒内获得3件及以上装扮全部合并展示",
  "case_number": "TC-PR1-MERGE-003",
  "module": "合并展示",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "用户已登录并处于房间内；关闭『隐藏特效』开关；用户当前未佩戴将要发放的3件装扮",
  "remarks": "关联需求 REQ-DEC-001（需求点1）",
  "test_data": {
   "发放装扮数": 3,
   "装扮1": "麦位框-萌爪闪闪",
   "装扮2": "座驾-星河战舰",
   "装扮3": "个人铭牌-闪耀之星",
   "发放间隔": "0.2秒/0.2秒"
  },
  "test_case_steps": [
   {
    "step": "服务端在0.5秒内依次发放3件装扮（间隔各0.2秒）：麦位框-萌爪闪闪、座驾-星河战舰、个人铭牌-闪耀之星",
    "result": "仅弹出1个弹窗，合并展示3张装扮卡片"
   },
   {
    "step": "观察弹窗标题与滑动切换",
    "result": "标题显示『获得3件装扮』；可左右滑动依次切换3张预览"
   }
  ]
 },
 {
  "name": "发放间隔超过0.5秒的装扮不合并按先后弹出",
  "case_number": "TC-PR1-MERGE-004",
  "module": "合并展示",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "用户已登录并处于房间内；关闭『隐藏特效』开关；用户当前未佩戴相关装扮；执行期间保持弹窗1处于未操作状态（勿点击任何按钮）",
  "remarks": "关联需求 REQ-DEC-001（需求点1 合并窗口0.5秒）；排队细节由 TC-PR1-RULE-001 单独覆盖",
  "test_data": {
   "装扮1": "麦位框-萌爪闪闪",
   "装扮2": "座驾-星河战舰",
   "发放间隔": "1.0秒（>0.5秒）"
  },
  "test_case_steps": [
   {
    "step": "服务端发放麦位框-萌爪闪闪（t=0秒）",
    "result": "立即弹出第1个弹窗展示该麦位框"
   },
   {
    "step": "服务端在t=1.0秒发放座驾-星河战舰，保持弹窗1未操作，观察弹窗出现情况",
    "result": "第2个弹窗不立即弹出（在弹窗1展示期间排队等待，具体排队行为见 TC-PR1-RULE-001）；2件装扮未合并到同一弹窗"
   }
  ]
 },
 {
  "name": "发放间隔恰好0.5秒的合并边界判断",
  "case_number": "TC-PR1-MERGE-005",
  "module": "合并展示",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "用户已登录并处于房间内；关闭『隐藏特效』开关；用户当前未佩戴相关装扮",
  "remarks": "关联需求 REQ-DEC-001；边界值场景——『0.5秒内』窗口语义（≤0.5秒或<0.5秒）需开发确认后二选一落地",
  "test_data": {
   "装扮1": "麦位框-萌爪闪闪",
   "装扮2": "座驾-星河战舰",
   "发放间隔": "0.50秒（边界值）"
  },
  "test_case_steps": [
   {
    "step": "服务端发放麦位框-萌爪闪闪（t=0秒）",
    "result": "弹出弹窗展示第1件装扮"
   },
   {
    "step": "服务端在t=0.50秒发放座驾-星河战舰，观察2件装扮是否合并",
    "result": "路径A（窗口为≤0.5秒含边界）：2件装扮合并到同一弹窗，展示2张卡片，标题『获得2件装扮』；路径B（窗口为<0.5秒开区间）：分为2个独立弹窗。判定方式：由开发确认窗口语义后，按对应路径断言执行"
   }
  ]
 },
 {
  "name": "合并展示按装扮发放先后顺序排序",
  "case_number": "TC-PR1-MERGE-006",
  "module": "合并展示",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "用户已登录并处于房间内；关闭『隐藏特效』开关；用户当前未佩戴相关装扮",
  "remarks": "关联需求 REQ-DEC-001（需求点1 根据装扮发放先后顺序排序）",
  "test_data": {
   "发放顺序": [
    "麦位框-萌爪闪闪",
    "座驾-星河战舰"
   ],
   "发放间隔": "0.2秒"
  },
  "test_case_steps": [
   {
    "step": "服务端0.5秒内先发放麦位框-萌爪闪闪，再发放座驾-星河战舰",
    "result": "弹窗弹出，合并展示2张卡片"
   },
   {
    "step": "观察弹窗内卡片顺序并左右滑动",
    "result": "第1张卡片为麦位框-萌爪闪闪（先发放），第2张卡片为座驾-星河战舰（后发放）；滑动顺序与发放顺序一致"
   }
  ]
 },
 {
  "name": "合并弹窗支持左右滑动切换预览",
  "case_number": "TC-PR1-MERGE-007",
  "module": "合并展示",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "合并弹窗已展示3张装扮卡片：麦位框-萌爪闪闪、座驾-星河战舰、个人铭牌-闪耀之星",
  "remarks": "关联需求 REQ-DEC-001（需求点1 可滑动切换装扮预览）",
  "test_data": {
   "卡片1": "麦位框-萌爪闪闪",
   "卡片2": "座驾-星河战舰",
   "卡片3": "个人铭牌-闪耀之星",
   "滑动操作": "左滑1次/左滑2次/右滑1次"
  },
  "test_case_steps": [
   {
    "step": "在弹窗内向左滑动1次",
    "result": "切换到第2张卡片（座驾-星河战舰），预览、名称、有效期、关系信息同步切换"
   },
   {
    "step": "再向左滑动1次",
    "result": "切换到第3张卡片（个人铭牌-闪耀之星）"
   },
   {
    "step": "在第3张卡片上继续向左滑动，观察是否越界",
    "result": "已到最右侧卡片，不再滑动/有回弹，不会循环到错误卡片；再向右滑动可依次切回卡片2、卡片1"
   }
  ]
 },
 {
  "name": "0.5秒合并窗口内部分装扮发放失败的处理",
  "case_number": "TC-PR1-MERGE-008",
  "module": "合并展示",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "用户已登录并处于房间内；关闭『隐藏特效』开关；服务端在0.5秒内先发放麦位框-萌爪闪闪（成功），第2件座驾-星河战舰的发放请求模拟失败（服务端返回发放错误码）",
  "remarks": "关联需求 REQ-DEC-001；异常场景——发放失败件是否补发/重试待产品确认",
  "test_data": {
   "装扮1": "麦位框-萌爪闪闪（发放成功）",
   "装扮2": "座驾-星河战舰（发放失败）",
   "发放间隔": "0.2秒"
  },
  "test_case_steps": [
   {
    "step": "服务端在0.5秒内发放麦位框-萌爪闪闪（成功）后发放座驾-星河战舰（失败），观察弹窗",
    "result": "弹窗仅展示发放成功的麦位框-萌爪闪闪1张卡片，标题显示『获得装扮』；发放失败的座驾不进入弹窗，无异常报错弹窗"
   },
   {
    "step": "查看背包中座驾-星河战舰",
    "result": "座驾-星河战舰未发放成功，背包中无该装扮（或按服务端补发策略在后续补发，需产品确认）"
   }
  ]
 },
 {
  "name": "合并弹窗卡片素材加载失败时的兜底表现",
  "case_number": "TC-PR1-MERGE-009",
  "module": "合并展示",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "合并弹窗展示2张卡片，第2张卡片（座驾-星河战舰）的预览素材资源模拟加载失败（资源404/网络断开）",
  "remarks": "关联需求 REQ-DEC-001；异常场景——兜底表现需求未明确，按『加载失败占位+可重试』假设编写，待产品确认",
  "test_data": {
   "卡片1": "麦位框-萌爪闪闪（素材正常）",
   "卡片2": "座驾-星河战舰（素材加载失败）"
  },
  "test_case_steps": [
   {
    "step": "打开合并弹窗，滑动到第2张卡片（座驾-星河战舰）",
    "result": "第2张卡片展示加载失败占位（默认图/失败提示标识），弹窗不崩溃、不白屏，可继续左右滑动"
   },
   {
    "step": "在加载失败卡片上触发重试（点击重试/重新滑动触发）",
    "result": "素材重新加载，加载成功后正常展示座驾预览效果"
   }
  ]
 },
 {
  "name": "0.5秒内大量发放装扮的合并上限验证",
  "case_number": "TC-PR1-MERGE-010",
  "module": "合并展示",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "用户已登录并处于房间内；关闭『隐藏特效』开关；服务端在0.5秒内连续发放10件不同类型装扮（麦位框×3、座驾×3、个人铭牌×4）",
  "remarks": "关联需求 REQ-DEC-001；边界值场景——合并件数上限需求未明确，若存在上限需产品确认（截断/滚动/分页策略）",
  "test_data": {
   "发放装扮数": 10,
   "麦位框": 3,
   "座驾": 3,
   "个人铭牌": 4,
   "发放间隔": "0.05秒"
  },
  "test_case_steps": [
   {
    "step": "服务端在0.5秒内连续发放10件装扮",
    "result": "全部合并到同一弹窗，标题显示『获得10件装扮』（多位数n完整拼接）"
   },
   {
    "step": "左右滑动遍历10张卡片",
    "result": "10张卡片均可滑动切换查看，无卡片遗漏、无截断、无错乱"
   }
  ]
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 19. ws-PR-2-test_cases_module_01_pos

- 来源：`workspace/testcase/PR-2/test_cases_module_01_pos.jsonl`　分组：PR-2　用例数：20

```json
[
 {
  "name": "POS订单创建-完整设备信息绑定成功",
  "case_number": "TC-PR2-POS-001",
  "module": "服务合同POS订单",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "DMS 系统已存在设备档案：UPN=POS-UPN-202607001，序列号=SN-JET3163-001，发货时间=2025-05-01",
  "remarks": "需求原文 一.业务说明1 | FP-001",
  "test_data": {
   "UPN": "POS-UPN-202607001",
   "序列号": "SN-JET3163-001",
   "合同编号": "C-2026-0001",
   "订单类型": "ZCS"
  },
  "test_case_steps": [
   {
    "step": "调用 DMS POS 订单创建接口，提交 UPN=POS-UPN-202607001、序列号=SN-JET3163-001、合同编号=C-2026-0001",
    "result": "接口返回 200，响应中包含订单号，订单号格式匹配 /^ZCS\\d{8}$/"
   },
   {
    "step": "查询 DMS 订单表中该订单记录",
    "result": "订单记录已创建，状态=已提交，设备UPN与序列号字段与提交数据完全一致"
   }
  ]
 },
 {
  "name": "POS订单创建-设备信息不完整拒绝创建",
  "case_number": "TC-PR2-POS-002",
  "module": "服务合同POS订单",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "无（无需预置数据）",
  "remarks": "需求原文 一.业务说明1 | FP-001",
  "test_data": {
   "UPN": "POS-UPN-202607002",
   "序列号": "",
   "合同编号": "C-2026-0002",
   "订单类型": "ZCS"
  },
  "test_case_steps": [
   {
    "step": "调用 POS 订单创建接口，仅传 UPN 不传序列号",
    "result": "接口返回 400，业务错误码标识“序列号缺失”"
   },
   {
    "step": "查询订单表确认是否生成记录",
    "result": "订单表无新增记录，无脏数据产生"
   }
  ]
 },
 {
  "name": "POS订单创建-重复UPN拒绝创建",
  "case_number": "TC-PR2-POS-003",
  "module": "服务合同POS订单",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "已存在 UPN=POS-UPN-202607003 且状态为已提交的有效 POS 订单",
  "remarks": "需求原文 一.业务说明1 | FP-001",
  "test_data": {
   "UPN": "POS-UPN-202607003",
   "序列号": "SN-JET3163-003",
   "合同编号": "C-2026-0003"
  },
  "test_case_steps": [
   {
    "step": "使用已存在的 UPN=POS-UPN-202607003 再次调用创建接口",
    "result": "接口返回业务错误，错误码标识“UPN已存在”，不创建新订单"
   },
   {
    "step": "查询订单表确认该 UPN 对应订单数量",
    "result": "该 UPN 对应有效订单仍为 1 条"
   }
  ]
 },
 {
  "name": "POS订单创建-序列号非法格式拦截",
  "case_number": "TC-PR2-POS-004",
  "module": "服务合同POS订单",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "无",
  "remarks": "需求原文 一.业务说明1 | FP-001",
  "test_data": {
   "UPN": "POS-UPN-202607004",
   "序列号": "SN-JET3163-004<script>alert(1)</script>ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcdefghijklmno",
   "合同编号": "C-2026-0004"
  },
  "test_case_steps": [
   {
    "step": "调用创建接口，序列号字段传入含特殊字符且长度超过32位的非法值",
    "result": "接口返回 400，错误码标识“序列号格式非法（仅允许字母数字与连字符，长度≤32）”"
   },
   {
    "step": "查询订单表确认无记录生成",
    "result": "订单表无新增记录"
   }
  ]
 },
 {
  "name": "POS订单创建-SQL注入与XSS攻击防护",
  "case_number": "TC-PR2-POS-005",
  "module": "服务合同POS订单",
  "case_type": "security",
  "priority": "high",
  "preconditions": "无",
  "remarks": "需求原文 一.业务说明1 | FP-001",
  "test_data": {
   "UPN": "' OR '1'='1",
   "序列号": "SN-JET3163-005'; DROP TABLE pos_order;--",
   "合同编号": "<script>alert(document.cookie)</script>"
  },
  "test_case_steps": [
   {
    "step": "在 UPN、序列号、合同编号字段分别注入 SQL 注入与 XSS payload 后调用创建接口",
    "result": "接口返回 400 参数校验错误，payload 原样被拒绝，无 500 服务器错误"
   },
   {
    "step": "查询订单表与系统日志",
    "result": "订单表无新增/删除异常记录，日志中 payload 未被原样拼接到 SQL 或页面输出"
   }
  ]
 },
 {
  "name": "POS订单-对接模式直接使用合同系统服务周期推送SAP",
  "case_number": "TC-PR2-POS-006",
  "module": "服务合同POS订单",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "合同系统已对接该合同：服务周期=2026-06-01~2029-05-31，开票时间=2026-06-02",
  "remarks": "需求原文 一.业务说明2 | FP-002",
  "test_data": {
   "合同编号": "C-2026-0006",
   "对接标记": "已对接",
   "对接服务起始": "2026-06-01",
   "对接服务截止": "2029-05-31",
   "对接开票时间": "2026-06-02"
  },
  "test_case_steps": [
   {
    "step": "创建 POS 订单并触发对接 SAP",
    "result": "订单成功创建，状态进入已提交"
   },
   {
    "step": "捕获推送 SAP 的报文并核对服务周期与开票时间字段",
    "result": "报文服务起始=2026-06-01、服务截止=2029-05-31、开票时间=2026-06-02，与合同系统对接数据完全一致，未做本地重新推算"
   }
  ]
 },
 {
  "name": "POS订单-计算模式标准值x=12且n=3服务周期计算",
  "case_number": "TC-PR2-POS-007",
  "module": "服务合同POS订单",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "合同系统未对接服务周期；设备 UPN+序列号可查到发货时间=2025-05-01",
  "remarks": "需求原文 一.业务说明3 | FP-003",
  "test_data": {
   "发货时间": "2025-05-01",
   "服务月数x": "12",
   "延保年数n": "3"
  },
  "test_case_steps": [
   {
    "step": "创建 POS 订单并触发服务周期计算",
    "result": "服务起始时间=2026-05-01（发货时间2025-05-01 + 12月）"
   },
   {
    "step": "核对服务截止时间字段",
    "result": "服务截止时间=2029-04-30（起始2026-05-01 + 12*3月 - 1天），与截图示例一致"
   },
   {
    "step": "核对推送 SAP 报文中的服务周期",
    "result": "报文服务周期=2026-05-01~2029-04-30"
   }
  ]
 },
 {
  "name": "POS订单-计算模式x边界值验证",
  "case_number": "TC-PR2-POS-008",
  "module": "服务合同POS订单",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "合同系统未对接；设备发货时间=2025-06-15",
  "remarks": "需求原文 一.业务说明3 | FP-003（阻塞假设1：x为1~36正整数）",
  "test_data": {
   "发货时间": "2025-06-15",
   "x_min": "1",
   "x_max": "36",
   "n": "1"
  },
  "test_case_steps": [
   {
    "step": "以 x=1 创建订单，核对服务起始时间",
    "result": "服务起始时间=2025-07-15（发货2025-06-15+1月）"
   },
   {
    "step": "以 x=36 创建订单，核对服务起始时间",
    "result": "服务起始时间=2028-06-15（发货2025-06-15+36月）"
   },
   {
    "step": "以 x=1 且 n=1 创建订单，核对服务截止时间",
    "result": "服务截止时间=2026-07-14（起始2025-07-15+12月-1天）"
   }
  ]
 },
 {
  "name": "POS订单-计算模式非法x值拒绝",
  "case_number": "TC-PR2-POS-009",
  "module": "服务合同POS订单",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "合同系统未对接；设备发货时间=2025-06-15",
  "remarks": "需求原文 一.业务说明3 | FP-003（阻塞假设1：x为1~36正整数）",
  "test_data": {
   "x_0": "0",
   "x_37": "37",
   "x_小数": "12.5",
   "x_负数": "-3"
  },
  "test_case_steps": [
   {
    "step": "分别以 x=0、x=37、x=12.5、x=-3 调用创建接口",
    "result": "接口均返回 400，错误码标识“服务月数x需为1~36的整数”"
   },
   {
    "step": "查询订单表",
    "result": "以上 4 种输入均未生成订单记录"
   }
  ]
 },
 {
  "name": "POS订单-计算模式n边界值验证",
  "case_number": "TC-PR2-POS-010",
  "module": "服务合同POS订单",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "合同系统未对接；设备发货时间=2025-03-10；x=12",
  "remarks": "需求原文 一.业务说明3 | FP-003（阻塞假设2：n为1~5正整数）",
  "test_data": {
   "发货时间": "2025-03-10",
   "x": "12",
   "n_min": "1",
   "n_max": "5"
  },
  "test_case_steps": [
   {
    "step": "以 n=1 创建订单，核对服务起始与截止时间",
    "result": "起始=2026-03-10，截止=2027-03-09（起始+12月-1天）"
   },
   {
    "step": "以 n=5 创建订单，核对服务起始与截止时间",
    "result": "起始=2026-03-10，截止=2031-03-09（起始+60月-1天）"
   }
  ]
 },
 {
  "name": "POS订单-计算模式月末跨月日期处理",
  "case_number": "TC-PR2-POS-011",
  "module": "服务合同POS订单",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "合同系统未对接；设备发货时间=2025-01-31（月末）",
  "remarks": "需求原文 一.业务说明3 | FP-003（阻塞假设3：跨月末取自然月对齐）",
  "test_data": {
   "发货时间": "2025-01-31",
   "x": "1",
   "n": "1"
  },
  "test_case_steps": [
   {
    "step": "以发货时间2025-01-31、x=1、n=1 创建订单并计算服务周期",
    "result": "服务起始时间=2025-02-28（2025年2月无31日，取2月末），服务截止时间=2026-02-27"
   },
   {
    "step": "核对计算过程中无日期溢出错误",
    "result": "接口返回 200，无日期异常错误，周期字段为上述值"
   }
  ]
 },
 {
  "name": "POS订单-开票时间等于对接SAP时间加1天",
  "case_number": "TC-PR2-POS-012",
  "module": "服务合同POS订单",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "订单已创建并成功对接 SAP，对接成功时间=2026-05-01 10:00:00",
  "remarks": "需求原文 一.业务说明3 | FP-004（阻塞假设3：截止/开票按+1天）",
  "test_data": {
   "对接SAP时间": "2026-05-01 10:00:00",
   "期望开票时间": "2026-05-02"
  },
  "test_case_steps": [
   {
    "step": "订单对接 SAP 成功后查询订单的开票时间字段",
    "result": "服务开票时间=2026-05-02，格式为 YYYY-mm-DD，时分秒被截断"
   },
   {
    "step": "核对开票时间与对接时间的差值",
    "result": "开票时间=对接日期+1天"
   }
  ]
 },
 {
  "name": "POS订单-开票时间月末年末闰年边界",
  "case_number": "TC-PR2-POS-013",
  "module": "服务合同POS订单",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "订单创建接口可正常对接 SAP",
  "remarks": "需求原文 一.业务说明3 | FP-004",
  "test_data": {
   "对接2026-12-31": "开票应为2027-01-01",
   "对接2026-02-28非闰年": "开票应为2026-03-01",
   "对接2024-02-29闰年": "开票应为2024-03-01"
  },
  "test_case_steps": [
   {
    "step": "分别在对接 SAP 时间为 2026-12-31、2026-02-28、2024-02-29 的场景下查询开票时间",
    "result": "开票时间按三种场景依次为 2027-01-01、2026-03-01、2024-03-01，跨月与跨年进位正确"
   }
  ]
 },
 {
  "name": "POS订单-服务周期与开票周期仅维护一项时拦截",
  "case_number": "TC-PR2-POS-014",
  "module": "服务合同POS订单",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "合同系统仅维护了服务周期(2026-06-01~2029-05-31)，未维护开票周期",
  "remarks": "需求原文 一.业务说明4 | FP-005",
  "test_data": {
   "维护状态": "仅服务周期",
   "服务周期": "2026-06-01~2029-05-31",
   "开票周期": ""
  },
  "test_case_steps": [
   {
    "step": "以仅维护服务周期的合同创建 POS 订单",
    "result": "接口返回业务错误，错误码标识“服务周期与开票周期需成对维护”"
   },
   {
    "step": "查询订单表",
    "result": "订单未创建，无记录生成"
   }
  ]
 },
 {
  "name": "POS订单-对接后直接提交无需经销商二次确认",
  "case_number": "TC-PR2-POS-015",
  "module": "服务合同POS订单",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "POS 订单创建完成且对接 SAP 成功",
  "remarks": "需求原文 一.业务说明5 | FP-006",
  "test_data": {
   "订单编号": "ZCS-20260501-015",
   "对接完成": "是"
  },
  "test_case_steps": [
   {
    "step": "订单对接完成后以经销商角色登录 DMS 并打开该订单详情",
    "result": "订单直接处于“已提交”状态"
   },
   {
    "step": "检查订单操作按钮区域",
    "result": "无“确认”“驳回”“二次提交”等经销商确认按钮，经销商仅可查看"
   }
  ]
 },
 {
  "name": "POS订单-GSMS服务周期五要素回写成功",
  "case_number": "TC-PR2-POS-016",
  "module": "服务合同POS订单",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "存在服务订单编号=ZCS-20260501-016；GSMS 存在五要素匹配的设备记录（产品编号050599-010/批号LOT-2025-001/序列号SN-JET3163-016/UPN=POS-UPN-202607016）",
  "remarks": "需求原文 一.业务说明6 | FP-007",
  "test_data": {
   "服务订单编号": "ZCS-20260501-016",
   "设备产品编号": "050599-010",
   "设备批号": "LOT-2025-001",
   "设备序列号": "SN-JET3163-016",
   "POS服务UPN": "POS-UPN-202607016"
  },
  "test_case_steps": [
   {
    "step": "触发 GSMS 实际服务周期回写接口",
    "result": "返回更新成功标识，回写报文按“服务订单编号+设备产品编号+设备批号+设备序列号+POS服务UPN”五要素定位记录"
   },
   {
    "step": "查询 GSMS 工单维保效期与 DMS 订单服务周期",
    "result": "GSMS 工单实际维保效期已更新，与 DMS 订单服务周期一致"
   }
  ]
 },
 {
  "name": "POS订单-GSMS服务周期回写匹配失败处理",
  "case_number": "TC-PR2-POS-017",
  "module": "服务合同POS订单",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "GSMS 无对应五要素组合的设备记录",
  "remarks": "需求原文 一.业务说明6 | FP-007（阻塞假设6：回写失败返回错误码可重试）",
  "test_data": {
   "服务订单编号": "ZCS-20260501-017",
   "设备产品编号": "050599-999",
   "设备批号": "LOT-X",
   "设备序列号": "SN-NOTFOUND",
   "POS服务UPN": "POS-UPN-000000"
  },
  "test_case_steps": [
   {
    "step": "用不存在的五要素组合触发 GSMS 回写",
    "result": "返回明确错误码标识“未找到匹配记录”"
   },
   {
    "step": "查询 DMS 订单状态",
    "result": "订单保持原状态不变，未产生脏数据或半更新状态"
   },
   {
    "step": "修正五要素后重试回写",
    "result": "重试成功，返回更新成功标识"
   }
  ]
 },
 {
  "name": "POS订单-CC确认权限控制",
  "case_number": "TC-PR2-POS-018",
  "module": "服务合同POS订单",
  "case_type": "security",
  "priority": "high",
  "preconditions": "存在已进入SAP状态的 POS 订单编号=ZCS-20260501-018；具备普通经销商账号与 CC 账号各一个",
  "remarks": "需求原文 一.业务说明7 | FP-008",
  "test_data": {
   "订单编号": "ZCS-20260501-018",
   "经销商账号": "dealer_test_01",
   "CC账号": "cc_test_01"
  },
  "test_case_steps": [
   {
    "step": "使用普通经销商账号调用 CC 订单确认接口",
    "result": "接口返回 403 无权限，订单状态保持“已进入SAP”"
   },
   {
    "step": "使用 CC 账号调用订单确认接口",
    "result": "确认成功，订单状态变为“已确认”"
   }
  ]
 },
 {
  "name": "POS订单-状态完整正向流转",
  "case_number": "TC-PR2-POS-019",
  "module": "服务合同POS订单",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "POS 订单创建成功，处于“已提交”状态",
  "remarks": "需求原文 一.业务说明8 | FP-009",
  "test_data": {
   "订单编号": "ZCS-20260501-019",
   "状态链": "已提交→已进入SAP→已确认→部分开票→完全开票"
  },
  "test_case_steps": [
   {
    "step": "依次触发：提交订单→对接SAP→CC确认→开票一期→开票全部期次",
    "result": "订单状态按“已提交→已进入SAP→已确认→部分开票→完全开票”顺序流转，无跳步"
   },
   {
    "step": "查询操作记录表",
    "result": "每一步状态变化均生成一条操作记录，操作人与时间完整"
   }
  ]
 },
 {
  "name": "POS订单-状态非法跳转拦截",
  "case_number": "TC-PR2-POS-020",
  "module": "服务合同POS订单",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "POS 订单处于“已提交”状态，编号=ZCS-20260501-020",
  "remarks": "需求原文 一.业务说明8 | FP-009",
  "test_data": {
   "订单编号": "ZCS-20260501-020",
   "当前状态": "已提交",
   "非法目标状态": "完全开票"
  },
  "test_case_steps": [
   {
    "step": "调用接口尝试将订单直接从“已提交”跳转到“完全开票”（跳过中间态）",
    "result": "接口返回状态机校验错误，错误码标识“非法状态流转”"
   },
   {
    "step": "查询订单当前状态",
    "result": "订单状态仍为“已提交”，未发生变化"
   }
  ]
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 20. ws-PR-1-test_cases_module_03_captcha

- 来源：`workspace/testcase/PR-1/test_cases_module_03_captcha.jsonl`　分组：PR-1　用例数：12

```json
[
 {
  "name": "同一手机号当日第5次发送触发图形验证码",
  "case_number": "TC-PR1-CAPTCHA-001",
  "module": "图形验证码",
  "case_type": "functional",
  "preconditions": "手机号17012340005当日已发送4次验证码(未触发图形验证码), 风控开启",
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "该手机号发起第5次验证码发送",
    "result": "系统弹出图形验证码，短信发送被拦截"
   },
   {
    "step": "通过图形验证码后再次点击发送",
    "result": "验证码短信发送成功"
   }
  ],
  "test_data": {
   "手机号": "17012340005",
   "当日已发送次数": 4,
   "触发阈值": "当日≥5次(含5)"
  },
  "remarks": "FP-009 边界值 需求FR-03触发条件① 默认假设1(含边界值)"
 },
 {
  "name": "同一手机号当日第4次发送不触发图形验证码",
  "case_number": "TC-PR1-CAPTCHA-002",
  "module": "图形验证码",
  "case_type": "functional",
  "preconditions": "手机号17012340005当日已发送3次验证码",
  "priority": "high",
  "test_case_steps": [
   {
    "step": "该手机号发起第4次验证码发送",
    "result": "不弹出图形验证码，直接发送短信成功"
   }
  ],
  "test_data": {
   "手机号": "17012340005",
   "当日已发送次数": 3,
   "触发阈值": "当日≥5次(含5)"
  },
  "remarks": "FP-009 边界值min-1 需求FR-03触发条件①"
 },
 {
  "name": "同一IP 1分钟内第10次请求触发图形验证码",
  "case_number": "TC-PR1-CAPTCHA-003",
  "module": "图形验证码",
  "case_type": "functional",
  "preconditions": "IP 203.0.113.3 在1分钟内已发起9次验证码发送请求",
  "priority": "high",
  "test_case_steps": [
   {
    "step": "该IP在1分钟内发起第10次发送请求",
    "result": "触发图形验证码，短信发送被拦截"
   },
   {
    "step": "通过图形验证码后重试",
    "result": "发送成功"
   }
  ],
  "test_data": {
   "IP": "203.0.113.3",
   "1分钟内请求数": 9,
   "触发阈值": "同IP 1分钟≥10次(含10)"
  },
  "remarks": "FP-009 边界值 需求FR-03触发条件② 默认假设1"
 },
 {
  "name": "同一IP 1分钟内第9次请求不触发",
  "case_number": "TC-PR1-CAPTCHA-004",
  "module": "图形验证码",
  "case_type": "functional",
  "preconditions": "IP 203.0.113.3 在1分钟内已发起8次请求",
  "priority": "high",
  "test_case_steps": [
   {
    "step": "该IP在1分钟内发起第9次发送请求",
    "result": "不触发图形验证码，直接发送成功"
   }
  ],
  "test_data": {
   "IP": "203.0.113.3",
   "1分钟内请求数": 8,
   "触发阈值": "同IP 1分钟≥10次(含10)"
  },
  "remarks": "FP-009 边界值min-1 需求FR-03触发条件②"
 },
 {
  "name": "风控判定异常设备或异地登录触发图形验证码",
  "case_number": "TC-PR1-CAPTCHA-005",
  "module": "图形验证码",
  "case_type": "functional",
  "preconditions": "风控系统可将指定设备标记为异常、可注入异地登录信号",
  "priority": "high",
  "test_case_steps": [
   {
    "step": "使用风控标记为异常的测试设备发起验证码发送",
    "result": "发送前弹出图形验证码"
   },
   {
    "step": "模拟异地(非常用地市)IP发起验证码发送",
    "result": "同样触发图形验证码"
   }
  ],
  "test_data": {
   "场景1": "异常设备标识",
   "场景2": "异地IP 198.51.100.9"
  },
  "remarks": "FP-009 需求FR-03触发条件③"
 },
 {
  "name": "触发后未通过图形验证码无法发送短信",
  "case_number": "TC-PR1-CAPTCHA-006",
  "module": "图形验证码",
  "case_type": "functional",
  "preconditions": "已满足图形验证码触发条件(如当日第5次发送)",
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "触发图形验证码后不输入或输入错误，直接点击发送",
    "result": "短信不发送，提示先通过图形验证码"
   },
   {
    "step": "检查短信网关",
    "result": "无任何验证码短信下发记录"
   }
  ],
  "test_data": {
   "触发场景": "当日第5次发送",
   "操作": "跳过图形验证码直接发送"
  },
  "remarks": "FP-009 FP-010 需求FR-03规则"
 },
 {
  "name": "正确输入图形验证码后发送短信成功",
  "case_number": "TC-PR1-CAPTCHA-007",
  "module": "图形验证码",
  "case_type": "functional",
  "preconditions": "已触发图形验证码，图片已加载并可见",
  "priority": "high",
  "test_case_steps": [
   {
    "step": "读取图形验证码图片内容并按图片输入字符",
    "result": "输入框接受字符，无格式报错"
   },
   {
    "step": "点击\"发送验证码\"",
    "result": "图形验证码校验通过，短信验证码发送成功，进入60秒倒计时"
   }
  ],
  "test_data": {
   "图形验证码": "从图片读取的实际字符(如Ab3d)",
   "操作": "正确输入后发送"
  },
  "remarks": "FP-010 需求FR-03规则"
 },
 {
  "name": "输入错误图形验证码提示错误并阻止发送",
  "case_number": "TC-PR1-CAPTCHA-008",
  "module": "图形验证码",
  "case_type": "functional",
  "preconditions": "已触发图形验证码，图片已加载",
  "priority": "high",
  "test_case_steps": [
   {
    "step": "输入与图片不符的验证码字符",
    "result": "提示\"图形验证码错误\"，短信不发送"
   },
   {
    "step": "检查短信网关",
    "result": "无短信下发记录"
   }
  ],
  "test_data": {
   "图形验证码": "输入与图片不符的字符(如zzzz)",
   "预期": "提示错误并阻止发送"
  },
  "remarks": "FP-010 需求FR-03规则"
 },
 {
  "name": "图形验证码校验不区分大小写",
  "case_number": "TC-PR1-CAPTCHA-009",
  "module": "图形验证码",
  "case_type": "functional",
  "preconditions": "已触发图形验证码，图片字符含字母",
  "priority": "medium",
  "test_case_steps": [
   {
    "step": "图片验证码为 Ab3d，输入小写 ab3d 后提交",
    "result": "校验通过，短信发送成功"
   },
   {
    "step": "再次触发后，图片验证码为 Ab3d，输入大写 AB3D 提交",
    "result": "同样校验通过"
   }
  ],
  "test_data": {
   "图片字符": "Ab3d",
   "输入小写": "ab3d",
   "输入大写": "AB3D"
  },
  "remarks": "FP-010 需求FR-03规则 不区分大小写"
 },
 {
  "name": "点击图片刷新生成新验证码",
  "case_number": "TC-PR1-CAPTCHA-010",
  "module": "图形验证码",
  "case_type": "functional",
  "preconditions": "已触发图形验证码，图片已加载",
  "priority": "medium",
  "test_case_steps": [
   {
    "step": "点击验证码图片的刷新区域",
    "result": "图片内容变化，生成新的验证码字符"
   },
   {
    "step": "用旧验证码字符提交",
    "result": "校验失败提示\"图形验证码错误\"，旧验证码已失效"
   }
  ],
  "test_data": {
   "刷新方式": "点击图片",
   "旧验证码": "刷新前图片字符"
  },
  "remarks": "FP-010 需求FR-03规则 点击图片可刷新"
 },
 {
  "name": "图形验证码超过2分钟有效期失效",
  "case_number": "TC-PR1-CAPTCHA-011",
  "module": "图形验证码",
  "case_type": "functional",
  "preconditions": "已触发图形验证码，已等待超过2分钟",
  "priority": "high",
  "test_case_steps": [
   {
    "step": "等待图形验证码生成超过2分钟后输入原图片字符并提交",
    "result": "提示\"图形验证码已过期，请刷新\"，短信不发送"
   },
   {
    "step": "点击图片刷新后输入新验证码",
    "result": "校验通过，短信发送成功"
   }
  ],
  "test_data": {
   "等待时长": "121秒(>2分钟)",
   "验证码有效期": "2分钟"
  },
  "remarks": "FP-010 边界值 需求FR-03规则"
 },
 {
  "name": "图形验证码防自动化识别与暴力尝试",
  "case_number": "TC-PR1-CAPTCHA-012",
  "module": "图形验证码",
  "case_type": "security",
  "preconditions": "抓包/脚本工具可用，已触发图形验证码",
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "通过脚本对图形验证码校验接口连续提交20次随机字符",
    "result": "超过尝试次数上限后该图形验证码失效，需重新刷新图片"
   },
   {
    "step": "检查接口响应",
    "result": "失败尝试不返回图形验证码明文或可破解信息，响应无验证码答案泄露"
   },
   {
    "step": "检查图片接口",
    "result": "验证码图片不包含可直接解析的答案元数据"
   }
  ],
  "test_data": {
   "脚本尝试次数": 20,
   "图片格式": "含干扰线的位图/矢量图"
  },
  "remarks": "FP-010 安全 需求FR-03规则 目标1.2防滥用"
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 21. ws-PR-2-test_cases_perm

- 来源：`workspace/testcase/PR-2/test_cases_perm.jsonl`　分组：PR-2　用例数：11

```json
[
 {
  "case_number": "TC-PR-PERM-001",
  "name": "用户管理列表页校验「数据权限」字段显示",
  "module": "精智未来云·用户管理",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "1. 登录精智未来云管理后台，当前用户拥有「用户管理」菜单权限\n2. 系统存在至少3个不同类型的内置用户（如管理员、普通用户、第三方用户）",
  "test_data": {
   "user_list_api": "/api/v1/users/list",
   "expected_fields": [
    "user_id",
    "username",
    "role",
    "status",
    "data_permission"
   ],
   "expected_page_size": 20
  },
  "test_case_steps": [
   {
    "step": "1. 进入「用户管理」菜单，打开用户列表页面",
    "result": "页面正常加载，左侧菜单「用户管理」高亮显示"
   },
   {
    "step": "2. 查看用户列表表格的列头",
    "result": "列表列头包含「数据权限」字段，位于「角色」和「状态」列之间"
   },
   {
    "step": "3. 逐一查看列表中每个用户所在行的「数据权限」列",
    "result": "每个用户均显示对应的数据权限值（「前置中心」/「内蒙古实验室」/「北京实验室」的组合，或以逗号分隔的多选值）；若未设置则显示「—」"
   },
   {
    "step": "4. 点击列表分页查看第二页数据",
    "result": "第二页用户同样展示「数据权限」字段，字段显示与第一页格式一致"
   }
  ],
  "remarks": "关联需求 FP-010"
 },
 {
  "case_number": "TC-PR-PERM-002",
  "name": "第三方用户列表校验「数据权限」字段显示",
  "module": "精智未来云·用户管理",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "1. 登录精智未来云管理后台\n2. 已配置至少2个第三方用户（如LDAP/OAuth接入）\n3. 第三方用户已分配不同的数据权限",
  "test_data": {
   "third_party_api": "/api/v1/users/third-party/list",
   "expected_fields": [
    "user_id",
    "display_name",
    "source",
    "data_permission"
   ],
   "target_users": [
    {
     "source": "LDAP",
     "expected_permission": "前置中心"
    },
    {
     "source": "OAuth",
     "expected_permission": "内蒙古实验室,北京实验室"
    }
   ]
  },
  "test_case_steps": [
   {
    "step": "1. 进入「第三方用户」列表页",
    "result": "列表页正常加载，页标题显示「第三方用户」"
   },
   {
    "step": "2. 查看第三方用户列表的表格列头",
    "result": "列表列头包含「数据权限」字段"
   },
   {
    "step": "3. 找到LDAP来源的第三方用户，查看其「数据权限」列",
    "result": "该用户显示「前置中心」"
   },
   {
    "step": "4. 找到OAuth来源的第三方用户，查看其「数据权限」列",
    "result": "该用户显示「内蒙古实验室,北京实验室」（多选用逗号分隔）"
   }
  ],
  "remarks": "关联需求 FP-010"
 },
 {
  "case_number": "TC-PR-PERM-003",
  "name": "用户详情页展示已选数据权限",
  "module": "精智未来云·用户管理",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "1. 登录管理后台\n2. 存在一个已设置数据权限为「前置中心,内蒙古实验室」的用户A\n3. 存在一个未设置任何数据权限的用户B",
  "test_data": {
   "user_detail_api": "/api/v1/users/{user_id}/detail",
   "user_A_data_permission": [
    "前置中心",
    "内蒙古实验室"
   ],
   "user_B_data_permission": []
  },
  "test_case_steps": [
   {
    "step": "1. 在用户管理列表页点击用户A的「编辑」按钮",
    "result": "弹出用户编辑对话框/跳转至用户详情页"
   },
   {
    "step": "2. 在编辑页面中找到「数据权限」字段区域",
    "result": "「数据权限」字段展示，已勾选「前置中心」和「内蒙古实验室」，未勾选「北京实验室」"
   },
   {
    "step": "3. 关闭编辑弹窗/返回列表，点击用户B的「编辑」按钮",
    "result": "用户B的编辑页面中「数据权限」字段展示，三项均未勾选，显示为空白"
   }
  ],
  "remarks": "关联需求 FP-010"
 },
 {
  "case_number": "TC-PR-PERM-004",
  "name": "数据权限选择框展示全部三个固定选项",
  "module": "精智未来云·用户管理",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "1. 登录管理后台\n2. 打开任意用户的编辑页面\n3. 数据权限功能已开启",
  "test_data": {
   "expected_options": [
    "前置中心",
    "内蒙古实验室",
    "北京实验室"
   ],
   "field_name": "data_permission",
   "control_type": "checkbox-group"
  },
  "test_case_steps": [
   {
    "step": "1. 在用户编辑页面定位「数据权限」字段",
    "result": "字段标签显示为「数据权限」"
   },
   {
    "step": "2. 点击「数据权限」字段的下拉/选择区域",
    "result": "弹出选项列表，包含「前置中心」「内蒙古实验室」「北京实验室」三个选项"
   },
   {
    "step": "3. 确认选项中不包含其他无关选项（如「上海实验室」「广州中心」等）",
    "result": "选项列表仅包含「前置中心」「内蒙古实验室」「北京实验室」三项，不存在第四项"
   },
   {
    "step": "4. 确认每个选项前均为复选框（checkbox）形态",
    "result": "每个选项前均有方框形复选框，支持多选"
   }
  ],
  "remarks": "关联需求 FP-011"
 },
 {
  "case_number": "TC-PR-PERM-005",
  "name": "数据权限多选保存后回显正确",
  "module": "精智未来云·用户管理",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "1. 登录管理后台\n2. 选择一个尚未设置数据权限的内置用户（非当前登录用户）",
  "test_data": {
   "selected_permissions": [
    "前置中心",
    "北京实验室"
   ],
   "save_api": "/api/v1/users/{user_id}/update",
   "save_payload": {
    "data_permission": [
     "前置中心",
     "北京实验室"
    ]
   },
   "get_api": "/api/v1/users/{user_id}/detail"
  },
  "test_case_steps": [
   {
    "step": "1. 进入该用户的编辑页面，勾选「前置中心」和「北京实验室」",
    "result": "「前置中心」和「北京实验室」两个复选框变为选中状态"
   },
   {
    "step": "2. 点击「保存」按钮",
    "result": "页面提示「保存成功」"
   },
   {
    "step": "3. 关闭编辑弹窗，重新进入该用户的编辑页面",
    "result": "「数据权限」字段中，「前置中心」和「北京实验室」仍为选中状态，「内蒙古实验室」为未选中"
   },
   {
    "step": "4. 在用户列表页找到该用户，查看「数据权限」列",
    "result": "列表页该用户的「数据权限」列显示「前置中心,北京实验室」"
   }
  ],
  "remarks": "关联需求 FP-011"
 },
 {
  "case_number": "TC-PR-PERM-006",
  "name": "数据权限全选全部三项并保存成功",
  "module": "精智未来云·用户管理",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "1. 登录管理后台\n2. 选择一个已有数据权限的用户或新建用户",
  "test_data": {
   "selected_permissions": [
    "前置中心",
    "内蒙古实验室",
    "北京实验室"
   ],
   "save_api": "/api/v1/users/{user_id}/update",
   "save_payload": {
    "data_permission": [
     "前置中心",
     "内蒙古实验室",
     "北京实验室"
    ]
   }
  },
  "test_case_steps": [
   {
    "step": "1. 进入用户编辑页面，同时勾选「前置中心」「内蒙古实验室」「北京实验室」三项",
    "result": "三个复选框全部变为选中状态"
   },
   {
    "step": "2. 点击「保存」按钮",
    "result": "页面提示「保存成功」"
   },
   {
    "step": "3. 刷新页面并重新进入编辑界面",
    "result": "三项数据权限依然全部选中，与保存前一致"
   },
   {
    "step": "4. 调用用户详情API查看data_permission字段",
    "result": "API返回data_permission字段为[\"前置中心\",\"内蒙古实验室\",\"北京实验室\"]"
   }
  ],
  "remarks": "关联需求 FP-011"
 },
 {
  "case_number": "TC-PR-PERM-007",
  "name": "数据权限取消全部选择（清空）后保存",
  "module": "精智未来云·用户管理",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "1. 登录管理后台\n2. 选择一个已设置「前置中心,内蒙古实验室」数据权限的用户",
  "test_data": {
   "initial_permissions": [
    "前置中心",
    "内蒙古实验室"
   ],
   "save_api": "/api/v1/users/{user_id}/update",
   "save_payload": {
    "data_permission": []
   }
  },
  "test_case_steps": [
   {
    "step": "1. 打开该用户的编辑页面，确认「前置中心」和「内蒙古实验室」均为选中状态",
    "result": "「前置中心」「内蒙古实验室」复选框已选中"
   },
   {
    "step": "2. 取消勾选「前置中心」和「内蒙古实验室」",
    "result": "三个复选框均为未选中状态"
   },
   {
    "step": "3. 点击「保存」按钮",
    "result": "页面提示「保存成功」"
   },
   {
    "step": "4. 重新进入编辑页面查看「数据权限」",
    "result": "三项复选框均未选中"
   },
   {
    "step": "5. 在用户列表页查看该用户的「数据权限」列",
    "result": "显示为「—」（表示无数据权限）"
   }
  ],
  "remarks": "关联需求 FP-011"
 },
 {
  "case_number": "TC-PR-PERM-008",
  "name": "数据权限联动XMetrix：选定实验室数据可见",
  "module": "精智未来云·用户管理",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "1. 登录精智未来云管理后台\n2. 切换用户A的数据权限为「前置中心」\n3. XMetrix平台中已存在前置中心、内蒙古实验室、北京实验室各自的指标数据\n4. 使用用户A的会话/Token访问系统",
  "test_data": {
   "user_A_permission": [
    "前置中心"
   ],
   "xmetrix_api": "/api/v1/xmetrix/data",
   "expected_visible_labs": [
    "前置中心"
   ],
   "expected_invisible_labs": [
    "内蒙古实验室",
    "北京实验室"
   ],
   "test_metrics": [
    {
     "lab": "前置中心",
     "metric": "cpu_usage",
     "expected": "可见"
    },
    {
     "lab": "内蒙古实验室",
     "metric": "cpu_usage",
     "expected": "不可见"
    },
    {
     "lab": "北京实验室",
     "metric": "cpu_usage",
     "expected": "不可见"
    }
   ]
  },
  "test_case_steps": [
   {
    "step": "1. 以用户A身份登录，进入XMetrix数据看板",
    "result": "页面正常加载，左侧导航显示XMetrix菜单"
   },
   {
    "step": "2. 查看XMetrix数据列表/看板中「前置中心」的CPU使用率数据",
    "result": "「前置中心」的CPU使用率数据正常展示，数据值与数据库中一致"
   },
   {
    "step": "3. 查看XMetrix数据中「内蒙古实验室」的CPU使用率数据",
    "result": "「内蒙古实验室」的CPU使用率数据不可见，页面不展示该实验室数据"
   },
   {
    "step": "4. 查看XMetrix数据中「北京实验室」的CPU使用率数据",
    "result": "「北京实验室」的CPU使用率数据不可见，页面不展示该实验室数据"
   }
  ],
  "remarks": "关联需求 FP-012"
 },
 {
  "case_number": "TC-PR-PERM-009",
  "name": "数据权限联动XMetrix：取消某实验室权限后数据不可见",
  "module": "精智未来云·用户管理",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "1. 用户A当前数据权限为「前置中心,内蒙古实验室」\n2. 用户A已登录且当前在XMetrix页面可以看到两个实验室的数据\n3. 系统记录用户A当前会话",
  "test_data": {
   "user_A_id": "user_demo_001",
   "initial_permissions": [
    "前置中心",
    "内蒙古实验室"
   ],
   "updated_permissions": [
    "前置中心"
   ],
   "xmetrix_api": "/api/v1/xmetrix/data",
   "verification": {
    "lab_removed": "内蒙古实验室",
    "lab_kept": "前置中心"
   }
  },
  "test_case_steps": [
   {
    "step": "1. 管理员将用户A的数据权限从「前置中心,内蒙古实验室」修改为仅「前置中心」",
    "result": "用户A的权限修改成功保存"
   },
   {
    "step": "2. 用户A刷新XMetrix数据看板页面",
    "result": "页面刷新后「前置中心」数据仍然可见展示"
   },
   {
    "step": "3. 在XMetrix页面中查找「内蒙古实验室」相关数据",
    "result": "「内蒙古实验室」的所有指标数据均不可见，已从页面消失"
   },
   {
    "step": "4. 调用XMetrix数据API并检查返回结果",
    "result": "API返回的数据列表中不包含lab字段为「内蒙古实验室」的任何数据记录"
   }
  ],
  "remarks": "关联需求 FP-012"
 },
 {
  "case_number": "TC-PR-PERM-010",
  "name": "数据权限联动XMetrix：无任何权限则XMetrix完全不可见",
  "module": "精智未来云·用户管理",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "1. 新建用户B（初始数据权限为空）\n2. XMetrix中「前置中心」「内蒙古实验室」「北京实验室」均有数据\n3. 使用用户B登录系统",
  "test_data": {
   "user_B_permission": [],
   "xmetrix_api": "/api/v1/xmetrix/data",
   "expected_data_count": 0,
   "xmetrix_menu_path": "/xmetrix/dashboard"
  },
  "test_case_steps": [
   {
    "step": "1. 以用户B身份登录系统",
    "result": "系统正常登录，进入首页"
   },
   {
    "step": "2. 检查左侧导航菜单中「XMetrix」菜单项",
    "result": "「XMetrix」菜单项可见，但点击后提示「无数据权限」或数据列表为空"
   },
   {
    "step": "3. 进入XMetrix页面后查看所有实验室的数据",
    "result": "页面展示为空，显示提示文案如「暂无可用数据，请联系管理员分配数据权限」"
   },
   {
    "step": "4. 调用XMetrix数据API查看返回结果",
    "result": "API返回空数组 []，HTTP状态码200，无任何实验室数据"
   }
  ],
  "remarks": "关联需求 FP-012"
 },
 {
  "case_number": "TC-PR-PERM-011",
  "name": "数据权限变更不影响其他平台（非XMetrix）的数据可见性",
  "module": "精智未来云·用户管理",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "1. 用户A拥有「前置中心」数据权限\n2. 用户A在其他平台（如设备管理、告警中心、报表平台）中本就可以查看所有数据\n3. XMetrix中已配置多个实验室数据",
  "test_data": {
   "user_A_permission": [
    "前置中心"
   ],
   "other_platforms": [
    {
     "name": "设备管理",
     "url": "/devices/list",
     "expected_access": "全部设备可见"
    },
    {
     "name": "告警中心",
     "url": "/alerts/list",
     "expected_access": "全部告警可见"
    },
    {
     "name": "报表平台",
     "url": "/reports/list",
     "expected_access": "全部报表数据可见"
    }
   ]
  },
  "test_case_steps": [
   {
    "step": "1. 以用户A身份登录系统中，进入「设备管理」页面",
    "result": "设备管理列表展示所有数据中心的设备，不受仅「前置中心」权限影响"
   },
   {
    "step": "2. 进入「告警中心」页面",
    "result": "告警中心展示全部来源（前置中心、内蒙古实验室、北京实验室）的告警记录"
   },
   {
    "step": "3. 进入「报表平台」页面",
    "result": "报表平台展示所有实验室的报表数据，与数据权限设置前一致"
   },
   {
    "step": "4. 进入「XMetrix」页面对比",
    "result": "XMetrix仅展示「前置中心」数据，印证数据权限仅作用于XMetrix平台，不影响其他平台"
   }
  ],
  "remarks": "关联需求 FP-012"
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 22. ws-PR-1-test_cases_module_02_session

- 来源：`workspace/testcase/PR-1/test_cases_module_02_session.jsonl`　分组：PR-1　用例数：11

```json
[
 {
  "name": "Web勾选记住我token有效期30天",
  "case_number": "TC-PR1-SESSION-001",
  "module": "登录态保持",
  "case_type": "functional",
  "preconditions": "Web端登录页可用，浏览器可正常保存Cookie",
  "priority": "high",
  "test_case_steps": [
   {
    "step": "勾选\"记住我\"后使用有效手机号验证码登录",
    "result": "登录成功，token已写入持久化Cookie，过期时间约为登录时刻后30天"
   },
   {
    "step": "关闭浏览器并重新打开，访问受保护页面",
    "result": "第29天访问仍处于登录态；第30天整点后访问需重新登录(边界验证时可将token有效期调短模拟)"
   }
  ],
  "test_data": {
   "手机号": "13812345678",
   "记住我": "勾选",
   "token有效期": "30天"
  },
  "remarks": "FP-006 需求FR-02规则2 默认假设:边界验证可缩短有效期便于执行"
 },
 {
  "name": "Web未勾选记住我token有效期24小时",
  "case_number": "TC-PR1-SESSION-002",
  "module": "登录态保持",
  "case_type": "functional",
  "preconditions": "Web端登录页可用",
  "priority": "high",
  "test_case_steps": [
   {
    "step": "不勾选\"记住我\"，使用有效手机号验证码登录",
    "result": "登录成功，token有效期设置为24小时(会话Cookie)"
   },
   {
    "step": "保持浏览器打开，24小时后访问受保护页面",
    "result": "token过期，接口返回401，页面跳转登录页"
   }
  ],
  "test_data": {
   "手机号": "13812345678",
   "记住我": "未勾选",
   "token有效期": "24小时"
  },
  "remarks": "FP-006 需求FR-02规则2"
 },
 {
  "name": "Web未勾选记住我关闭浏览器会话失效",
  "case_number": "TC-PR1-SESSION-003",
  "module": "登录态保持",
  "case_type": "functional",
  "preconditions": "Web端登录页可用",
  "priority": "high",
  "test_case_steps": [
   {
    "step": "不勾选\"记住我\"登录成功后关闭整个浏览器进程",
    "result": "会话Cookie随浏览器进程结束被清除(非持久化Cookie)"
   },
   {
    "step": "重新打开浏览器访问受保护页面",
    "result": "未携带有效token，返回401并跳转登录页"
   }
  ],
  "test_data": {
   "手机号": "13812345678",
   "记住我": "未勾选",
   "Cookie类型": "会话Cookie(内存)"
  },
  "remarks": "FP-006 需求FR-02规则2"
 },
 {
  "name": "勾选记住我关闭浏览器30天内仍保持登录",
  "case_number": "TC-PR1-SESSION-004",
  "module": "登录态保持",
  "case_type": "functional",
  "preconditions": "Web端登录页可用",
  "priority": "medium",
  "test_case_steps": [
   {
    "step": "勾选\"记住我\"登录后关闭浏览器进程",
    "result": "持久化Cookie保留在浏览器存储中"
   },
   {
    "step": "次日重新打开浏览器访问受保护页面",
    "result": "仍处于登录态，无需重新登录"
   }
  ],
  "test_data": {
   "手机号": "13812345678",
   "记住我": "勾选",
   "Cookie类型": "持久化Cookie"
  },
  "remarks": "FP-006 需求FR-02规则2"
 },
 {
  "name": "App端杀进程重启后登录态保留",
  "case_number": "TC-PR1-SESSION-005",
  "module": "登录态保持",
  "case_type": "functional",
  "preconditions": "iOS/Android设备各一台，App已安装",
  "priority": "high",
  "test_case_steps": [
   {
    "step": "App内登录成功后强制杀掉App进程",
    "result": "App进程终止无异常"
   },
   {
    "step": "重新启动App",
    "result": "启动后直接进入已登录主页，无需重新登录，token未失效"
   }
  ],
  "test_data": {
   "手机号": "13812345678",
   "端": "iOS/Android",
   "操作": "杀进程重启"
  },
  "remarks": "FP-007 需求FR-02规则1"
 },
 {
  "name": "App端不主动登出则长期保持登录",
  "case_number": "TC-PR1-SESSION-006",
  "module": "登录态保持",
  "case_type": "functional",
  "preconditions": "App已登录，token未过期(模拟有效期足够长)",
  "priority": "medium",
  "test_case_steps": [
   {
    "step": "App登录后连续使用7天，期间不执行登出操作",
    "result": "期间访问各受保护功能均正常，无被强制登出"
   },
   {
    "step": "期间多次切换前后台与锁屏",
    "result": "登录态保持，不要求重复登录"
   }
  ],
  "test_data": {
   "手机号": "13812345678",
   "操作": "7天不登出",
   "预期": "登录态长期保持"
  },
  "remarks": "FP-007 需求FR-02规则1"
 },
 {
  "name": "登出后旧token访问受保护接口返回401",
  "case_number": "TC-PR1-SESSION-007",
  "module": "登录态保持",
  "case_type": "functional",
  "preconditions": "已登录用户，抓包获取当前token",
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "执行登出操作",
    "result": "登出成功，本地token被清除"
   },
   {
    "step": "用登出前的旧token调用受保护接口(如获取订单列表)",
    "result": "接口返回401 Unauthorized，提示token无效"
   }
  ],
  "test_data": {
   "旧token": "登出前抓包的token",
   "受保护接口": "/api/v1/orders",
   "预期状态码": "401"
  },
  "remarks": "FP-008 需求FR-02规则3"
 },
 {
  "name": "被踢下线后旧token访问返回401",
  "case_number": "TC-PR1-SESSION-008",
  "module": "登录态保持",
  "case_type": "functional",
  "preconditions": "账号已在设备A登录，准备用设备B同端登录触发互踢",
  "priority": "high",
  "test_case_steps": [
   {
    "step": "设备B同端登录同一账号",
    "result": "设备A被踢并提示\"您的账号已在其他设备登录\""
   },
   {
    "step": "设备A使用旧token调用受保护接口",
    "result": "接口返回401，设备A无法继续访问"
   }
  ],
  "test_data": {
   "设备A": "手机iOS",
   "设备B": "手机Android",
   "预期状态码": "401"
  },
  "remarks": "FP-008 需求FR-02规则3"
 },
 {
  "name": "token过期后访问要求重新登录",
  "case_number": "TC-PR1-SESSION-009",
  "module": "登录态保持",
  "case_type": "functional",
  "preconditions": "token有效期可配置(测试环境调短便于验证)",
  "priority": "high",
  "test_case_steps": [
   {
    "step": "登录后等待token超过有效期",
    "result": "期间token在服务端已过期"
   },
   {
    "step": "访问受保护接口",
    "result": "返回401且响应体含token过期标识，前端跳转登录页并要求重新登录"
   }
  ],
  "test_data": {
   "token有效期": "测试环境调短",
   "过期后访问": "受保护接口",
   "预期状态码": "401"
  },
  "remarks": "FP-008 需求FR-02规则3"
 },
 {
  "name": "安全无token访问受保护接口返回401",
  "case_number": "TC-PR1-SESSION-010",
  "module": "登录态保持",
  "case_type": "security",
  "preconditions": "抓包工具可用",
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "不携带Authorization头直接调用受保护接口",
    "result": "接口返回401 Unauthorized"
   },
   {
    "step": "携带空的Authorization头(Bearer后无内容)调用",
    "result": "同样返回401，不返回任何业务数据"
   }
  ],
  "test_data": {
   "请求方式": "无token调用",
   "受保护接口": "/api/v1/orders",
   "预期状态码": "401"
  },
  "remarks": "FP-008 安全 需求FR-02规则3"
 },
 {
  "name": "安全篡改token访问返回401",
  "case_number": "TC-PR1-SESSION-011",
  "module": "登录态保持",
  "case_type": "security",
  "preconditions": "已登录用户，抓包获取有效token",
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "修改token中间段负载的user_id字段后重新签名请求(或无签名直接请求)",
    "result": "服务端校验签名失败，返回401，拒绝访问"
   },
   {
    "step": "将token中的过期时间篡改为过期值后请求",
    "result": "同样返回401，无业务数据泄露"
   }
  ],
  "test_data": {
   "篡改方式": "修改payload/过期时间",
   "预期状态码": "401"
  },
  "remarks": "FP-008 安全 需求FR-02规则3"
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 23. ws-PR-2-test_cases_module_01

- 来源：`workspace/testcase/PR-2/test_cases_module_01.jsonl`　分组：PR-2　用例数：17

```json
[
 {
  "name": "列表字段展示确认包含地点ID/地点名称/地点类型/地点位置",
  "case_number": "TC-PR2-LOC-001",
  "module": "地点管理",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "系统已登录管理后台，系统中存在至少1条地点数据",
  "remarks": "REQ-变更① / FP-001",
  "test_data": {
   "页面路径": "采样点管理→地点管理",
   "操作类型": "列表展示验证"
  },
  "test_case_steps": [
   {
    "step": "进入「采样点管理→地点管理」页面",
    "result": "页面正常加载，副标题显示「地点管理」"
   },
   {
    "step": "观察列表表头字段",
    "result": "表头包含：地点ID（采样点ID）、地点名称（采样点名称）、地点类型、地点位置（采样点位置）、状态，共5列；字段名称与需求一致，体现「采样点改为地点」的变更"
   }
  ]
 },
 {
  "name": "按地点名称关键词搜索返回匹配结果",
  "case_number": "TC-PR2-LOC-002",
  "module": "地点管理",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "系统中存在地点「广医门诊四楼」（地点ID SP000022）等测试数据",
  "remarks": "REQ-变更① / FP-002",
  "test_data": {
   "搜索关键词": "广医",
   "预期匹配记录": "广医门诊四楼"
  },
  "test_case_steps": [
   {
    "step": "在地点管理列表搜索框输入关键词「广医」",
    "result": "搜索框可正常输入文本"
   },
   {
    "step": "点击「搜索」按钮",
    "result": "列表仅显示地点名称包含「广医」的记录，其中「广医门诊四楼」记录可见"
   }
  ]
 },
 {
  "name": "搜索无匹配关键词时显示空列表",
  "case_number": "TC-PR2-LOC-003",
  "module": "地点管理",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "系统已登录管理后台",
  "remarks": "FP-002",
  "test_data": {
   "搜索关键词": "ZZZZ不存在地点",
   "预期结果": "无匹配记录"
  },
  "test_case_steps": [
   {
    "step": "在搜索框输入不存在的关键词「ZZZZ不存在地点」",
    "result": "搜索框可正常输入"
   },
   {
    "step": "点击「搜索」按钮",
    "result": "列表显示空数据状态（无记录），页面不报错"
   }
  ]
 },
 {
  "name": "搜索框SQL注入防护验证",
  "case_number": "TC-PR2-LOC-004",
  "module": "地点管理",
  "case_type": "security",
  "priority": "critical",
  "preconditions": "系统已登录管理后台",
  "remarks": "用例质量红线第6条（安全） / FP-002",
  "test_data": {
   "注入载荷": "1' OR '1'='1",
   "攻击场景": "SQL注入"
  },
  "test_case_steps": [
   {
    "step": "在搜索框输入注入载荷「1' OR '1'='1」",
    "result": "搜索框可正常输入该字符串"
   },
   {
    "step": "点击「搜索」按钮",
    "result": "列表不返回全部地点数据；系统无SQL语法错误信息泄露；页面正常显示空列表或提示无结果"
   }
  ]
 },
 {
  "name": "新增地点-填写全部字段（含地点类型）成功保存",
  "case_number": "TC-PR2-LOC-005",
  "module": "地点管理",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "用户拥有管理/操作权限，系统已登录管理后台",
  "remarks": "REQ-变更①+② / FP-003",
  "test_data": {
   "地点名称": "广州中山医院采样点",
   "地点类型": "采样点",
   "地点位置": "广州市越秀区中山二路58号",
   "地点ID": "系统自动生成(SP+6位数字)"
  },
  "test_case_steps": [
   {
    "step": "点击「新增」按钮打开新增弹窗",
    "result": "弹窗正常打开，包含地点名称/地点类型/地点位置字段"
   },
   {
    "step": "输入地点名称「广州中山医院采样点」",
    "result": "输入正常显示"
   },
   {
    "step": "选择地点类型「采样点」",
    "result": "下拉选中「采样点」"
   },
   {
    "step": "输入地点位置「广州市越秀区中山二路58号」",
    "result": "输入正常显示"
   },
   {
    "step": "点击「保存」按钮",
    "result": "保存成功，弹窗关闭；列表刷新，新增记录出现在列表中；地点ID自动生成且格式为SP+6位数字；地点名称/类型/位置均与输入一致"
   }
  ]
 },
 {
  "name": "新增地点-地点位置留空保存成功（位置非必填）",
  "case_number": "TC-PR2-LOC-006",
  "module": "地点管理",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "用户拥有管理/操作权限",
  "remarks": "已确认假设②（位置非必填） / FP-003",
  "test_data": {
   "地点名称": "测试地点无位置",
   "地点类型": "采样点",
   "地点位置": "(留空)"
  },
  "test_case_steps": [
   {
    "step": "点击「新增」按钮打开新增弹窗",
    "result": "弹窗正常打开"
   },
   {
    "step": "输入地点名称「测试地点无位置」，选择地点类型「采样点」",
    "result": "输入与选择正常"
   },
   {
    "step": "地点位置字段留空，点击「保存」按钮",
    "result": "保存成功，弹窗关闭；列表新增该记录，地点位置列显示为空"
   }
  ]
 },
 {
  "name": "新增地点-地点类型未选择时保存失败",
  "case_number": "TC-PR2-LOC-007",
  "module": "地点管理",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "用户拥有管理/操作权限",
  "remarks": "REQ-变更② / FP-004 / RAG·TC-ADD-005",
  "test_data": {
   "地点名称": "测试采样点",
   "地点类型": "(未选择)",
   "地点位置": "测试位置"
  },
  "test_case_steps": [
   {
    "step": "点击「新增」按钮打开新增弹窗",
    "result": "弹窗正常打开"
   },
   {
    "step": "输入地点名称「测试采样点」和地点位置「测试位置」",
    "result": "输入正常显示"
   },
   {
    "step": "地点类型保持未选择状态，点击「保存」按钮",
    "result": "保存失败；提示错误信息「请选择地点类型」；弹窗不关闭"
   }
  ]
 },
 {
  "name": "新增地点-地点名称为空时保存失败",
  "case_number": "TC-PR2-LOC-008",
  "module": "地点管理",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "用户拥有管理/操作权限",
  "remarks": "FP-005",
  "test_data": {
   "地点名称": "(空)",
   "地点类型": "采样点",
   "地点位置": "测试位置"
  },
  "test_case_steps": [
   {
    "step": "点击「新增」按钮打开新增弹窗",
    "result": "弹窗正常打开"
   },
   {
    "step": "地点名称留空，选择地点类型「采样点」，输入地点位置「测试位置」",
    "result": "类型与位置可正常填写"
   },
   {
    "step": "点击「保存」按钮",
    "result": "保存失败；提示「请输入地点名称」或等价必填提示；弹窗不关闭"
   }
  ]
 },
 {
  "name": "新增地点-输入已存在的同名地点保存失败",
  "case_number": "TC-PR2-LOC-009",
  "module": "地点管理",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "系统中已存在地点「广医门诊四楼」",
  "remarks": "已确认假设①（名称不允许重复） / FP-006",
  "test_data": {
   "地点名称": "广医门诊四楼(与已有记录同名)",
   "已有同名记录": "广医门诊四楼",
   "地点类型": "采样点"
  },
  "test_case_steps": [
   {
    "step": "点击「新增」按钮打开新增弹窗",
    "result": "弹窗正常打开"
   },
   {
    "step": "输入与已有记录同名的地点名称「广医门诊四楼」，选择地点类型「采样点」",
    "result": "输入与选择正常"
   },
   {
    "step": "点击「保存」按钮",
    "result": "保存失败；提示「地点名称已存在」或等价重复提示；弹窗不关闭"
   }
  ]
 },
 {
  "name": "新增地点-名称含前后空格与已有名称重复时校验",
  "case_number": "TC-PR2-LOC-010",
  "module": "地点管理",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "系统中已存在地点「广医门诊四楼」",
  "remarks": "FP-006 / 边界场景",
  "test_data": {
   "地点名称": "含前后空格同名(去空格后=广医门诊四楼)",
   "已有记录": "广医门诊四楼",
   "备注": "若系统不做trim则保存成功，需人工确认"
  },
  "test_case_steps": [
   {
    "step": "点击「新增」按钮打开新增弹窗",
    "result": "弹窗正常打开"
   },
   {
    "step": "输入带前后空格的地点名称（空格+广医门诊四楼+空格），选择地点类型「采样点」",
    "result": "输入正常显示"
   },
   {
    "step": "点击「保存」按钮",
    "result": "若系统对名称做去空格处理：去除空格后与「广医门诊四楼」重复，保存失败并提示重复；若系统不做去空格处理：保存成功。此项为边界确认点，需在评审中确认系统行为"
   }
  ]
 },
 {
  "name": "编辑地点-修改地点类型后保存成功",
  "case_number": "TC-PR2-LOC-011",
  "module": "地点管理",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "系统中存在至少1条地点记录，用户拥有管理/操作权限",
  "remarks": "REQ-变更② / FP-007 / RAG·TC-EDIT-001",
  "test_data": {
   "地点类型": "原类型→检测实验室",
   "其他字段": "保持不变"
  },
  "test_case_steps": [
   {
    "step": "点击某条地点记录的「编辑」按钮",
    "result": "编辑弹窗打开，各字段回显原值"
   },
   {
    "step": "将地点类型修改为「检测实验室」",
    "result": "下拉选中「检测实验室」"
   },
   {
    "step": "点击「保存」按钮",
    "result": "保存成功，弹窗关闭；列表中该记录的地点类型已更新为「检测实验室」"
   }
  ]
 },
 {
  "name": "编辑地点-地点ID字段只读不可编辑",
  "case_number": "TC-PR2-LOC-012",
  "module": "地点管理",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "系统中存在至少1条地点记录（如地点ID SP000022）",
  "remarks": "REQ-变更① / FP-008 / RAG·TC-EDIT-002",
  "test_data": {
   "地点ID字段": "SP000022",
   "操作": "尝试修改地点ID"
  },
  "test_case_steps": [
   {
    "step": "点击某条地点记录的「编辑」按钮",
    "result": "编辑弹窗打开，地点ID字段展示原值"
   },
   {
    "step": "观察地点ID字段的展示状态并尝试修改",
    "result": "地点ID字段为只读状态（灰化/禁用）；无法修改地点ID的值"
   }
  ]
 },
 {
  "name": "地点状态-启用切换为禁用即时生效",
  "case_number": "TC-PR2-LOC-013",
  "module": "地点管理",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "系统中存在1条启用状态的地点记录",
  "remarks": "已确认假设③（两态即时生效） / FP-009",
  "test_data": {
   "原状态": "启用",
   "切换后状态": "禁用",
   "操作": "点击状态开关"
  },
  "test_case_steps": [
   {
    "step": "找到一条启用状态的地点记录",
    "result": "该记录状态列显示「启用」"
   },
   {
    "step": "点击该记录的状态开关切换为禁用",
    "result": "切换即时生效，无需额外保存操作；该记录状态列立即显示为「禁用」"
   }
  ]
 },
 {
  "name": "地点状态-禁用切换为启用即时生效",
  "case_number": "TC-PR2-LOC-014",
  "module": "地点管理",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "系统中存在1条禁用状态的地点记录",
  "remarks": "FP-009 / 已确认假设③",
  "test_data": {
   "原状态": "禁用",
   "切换后状态": "启用",
   "操作": "点击状态开关"
  },
  "test_case_steps": [
   {
    "step": "找到一条禁用状态的地点记录",
    "result": "该记录状态列显示「禁用」"
   },
   {
    "step": "点击该记录的状态开关切换为启用",
    "result": "切换即时生效；该记录状态列立即显示为「启用」"
   }
  ]
 },
 {
  "name": "按地点类型筛选列表-选择检测实验室仅显示该类记录",
  "case_number": "TC-PR2-LOC-015",
  "module": "地点管理",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "系统中存在至少3条地点记录，涵盖至少2种地点类型",
  "remarks": "REQ-变更② / FP-010 / RAG·TC-TYPE-002",
  "test_data": {
   "筛选条件": "地点类型=检测实验室"
  },
  "test_case_steps": [
   {
    "step": "在地点管理列表页找到地点类型筛选条件",
    "result": "筛选组件正常展示"
   },
   {
    "step": "选择筛选条件「检测实验室」",
    "result": "列表仅显示地点类型为「检测实验室」的记录；其他类型的记录被过滤"
   }
  ]
 },
 {
  "name": "按地点类型筛选-清除筛选条件恢复全部数据",
  "case_number": "TC-PR2-LOC-016",
  "module": "地点管理",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "列表当前已按地点类型筛选",
  "remarks": "FP-010",
  "test_data": {
   "操作": "清除筛选条件"
  },
  "test_case_steps": [
   {
    "step": "在已按地点类型筛选的状态下，点击清除筛选条件",
    "result": "筛选条件被清除"
   },
   {
    "step": "观察列表",
    "result": "列表恢复显示全部地点数据"
   }
  ]
 },
 {
  "name": "新增地点-地点名称输入超长字符的保存处理",
  "case_number": "TC-PR2-LOC-017",
  "module": "地点管理",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "用户拥有管理/操作权限",
  "remarks": "FP-003 / 错误推测-边界；名称长度上限未在需求中定义，需人工确认",
  "test_data": {
   "地点名称长度": "200个字符",
   "地点类型": "采样点",
   "备注": "长度上限未定义，若实际有限制则超长应被拦截"
  },
  "test_case_steps": [
   {
    "step": "点击「新增」按钮打开新增弹窗",
    "result": "弹窗正常打开"
   },
   {
    "step": "输入200个字符的地点名称，选择地点类型「采样点」",
    "result": "输入框接受该文本输入"
   },
   {
    "step": "点击「保存」按钮",
    "result": "若字段有长度限制：保存失败并提示名称超长；若无限长限制：保存成功；两种情况均不出现系统异常报错"
   }
  ]
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 24. ws-PR-1-test_cases_dressup_module_02_title

- 来源：`workspace/testcase/PR-1/test_cases_dressup_module_02_title.jsonl`　分组：PR-1　用例数：9

```json
[
 {
  "name": "单件装扮弹窗标题为『获得装扮』",
  "case_number": "TC-PR1-TITLE-001",
  "module": "标题与说明",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "弹窗内仅展示1件装扮（麦位框-萌爪闪闪）",
  "remarks": "关联需求 REQ-DEC-002（需求点2 标题文案）；标题规则统一口径：弹窗内展示的装扮数=1时一律显示『获得装扮』（含单件弹窗/合并佩戴至剩1件/过滤后剩1件），与 TITLE-003、RULE-007 一致",
  "test_data": {
   "弹窗内装扮数": 1,
   "预期标题": "获得装扮"
  },
  "test_case_steps": [
   {
    "step": "打开装扮弹窗，查看标题栏文案",
    "result": "标题显示『获得装扮』，文案中不包含数字；与『获得n件装扮』格式区分"
   }
  ]
 },
 {
  "name": "多件装扮弹窗标题为『获得n件装扮』且n等于装扮总数",
  "case_number": "TC-PR1-TITLE-002",
  "module": "标题与说明",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "合并弹窗已展示2件装扮：麦位框-萌爪闪闪、座驾-星河战舰",
  "remarks": "关联需求 REQ-DEC-002（需求点2 标题文案 n为弹窗内装扮数）",
  "test_data": {
   "弹窗内装扮数": 2,
   "预期标题": "获得2件装扮"
  },
  "test_case_steps": [
   {
    "step": "打开合并弹窗，查看标题栏文案",
    "result": "标题显示『获得2件装扮』，n=2与弹窗内实际展示装扮数一致"
   }
  ]
 },
 {
  "name": "标题中的n随佩戴当前操作实时递减",
  "case_number": "TC-PR1-TITLE-003",
  "module": "标题与说明",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "合并弹窗已展示3件装扮：麦位框-萌爪闪闪、座驾-星河战舰、个人铭牌-闪耀之星，标题当前为『获得3件装扮』",
  "remarks": "关联需求 REQ-DEC-002（需求点2 n为实时数量）；标题统一口径：弹窗内展示数=1时显示『获得装扮』（与 TITLE-001/RULE-007 一致）；若产品确认合并弹窗保持『获得n件装扮』格式则需三用例同步调整",
  "test_data": {
   "初始装扮数": 3,
   "初始标题": "获得3件装扮",
   "佩戴操作": "佩戴当前×2次"
  },
  "test_case_steps": [
   {
    "step": "点击『佩戴当前』佩戴第1件装扮，查看标题变化",
    "result": "标题实时更新为『获得2件装扮』，与弹窗内剩余装扮数一致"
   },
   {
    "step": "再次点击『佩戴当前』佩戴第2件装扮，查看标题变化",
    "result": "标题实时更新为『获得装扮』（弹窗内展示数=1时按统一口径显示，不含数字），弹窗内仅剩1张卡片"
   }
  ]
 },
 {
  "name": "麦位框装扮说明文案正确",
  "case_number": "TC-PR1-TITLE-004",
  "module": "标题与说明",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "单件麦位框装扮弹窗已展示（麦位框-萌爪闪闪）",
  "remarks": "关联需求 REQ-DEC-002（需求点2 说明文案按类型展示）",
  "test_data": {
   "装扮类型": "麦位框",
   "预期说明文案": "佩戴后，展示在房间麦位头像上"
  },
  "test_case_steps": [
   {
    "step": "查看弹窗内说明文案",
    "result": "说明文案显示为『佩戴后，展示在房间麦位头像上』，内容与麦位框类型一致"
   }
  ]
 },
 {
  "name": "座驾装扮说明文案正确",
  "case_number": "TC-PR1-TITLE-005",
  "module": "标题与说明",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "单件座驾装扮弹窗已展示（座驾-星河战舰）",
  "remarks": "关联需求 REQ-DEC-002（需求点2 说明文案按类型展示）",
  "test_data": {
   "装扮类型": "座驾",
   "预期说明文案": "佩戴后，进房时展示动画效果"
  },
  "test_case_steps": [
   {
    "step": "查看弹窗内说明文案",
    "result": "说明文案显示为『佩戴后，进房时展示动画效果』，内容与座驾类型一致"
   }
  ]
 },
 {
  "name": "个人铭牌装扮说明文案正确",
  "case_number": "TC-PR1-TITLE-006",
  "module": "标题与说明",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "单件个人铭牌装扮弹窗已展示（个人铭牌-闪耀之星）",
  "remarks": "关联需求 REQ-DEC-002（需求点2 说明文案按类型展示）",
  "test_data": {
   "装扮类型": "个人铭牌",
   "预期说明文案": "佩戴后，展示在个人资料页面"
  },
  "test_case_steps": [
   {
    "step": "查看弹窗内说明文案",
    "result": "说明文案显示为『佩戴后，展示在个人资料页面』，内容与个人铭牌类型一致"
   }
  ]
 },
 {
  "name": "合并展示时说明文案随当前预览装扮类型切换",
  "case_number": "TC-PR1-TITLE-007",
  "module": "标题与说明",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "合并弹窗已展示2件装扮：麦位框-萌爪闪闪（第1张）、座驾-星河战舰（第2张），当前预览第1张",
  "remarks": "关联需求 REQ-DEC-002（需求点2 合并展示时文案随当前预览的装扮类型切换）",
  "test_data": {
   "卡片1": "麦位框-萌爪闪闪",
   "卡片2": "座驾-星河战舰",
   "卡片1说明": "佩戴后，展示在房间麦位头像上",
   "卡片2说明": "佩戴后，进房时展示动画效果"
  },
  "test_case_steps": [
   {
    "step": "当前预览第1张麦位框卡片，查看说明文案",
    "result": "说明文案显示『佩戴后，展示在房间麦位头像上』"
   },
   {
    "step": "向左滑动切换到第2张座驾卡片，查看说明文案",
    "result": "说明文案切换为『佩戴后，进房时展示动画效果』，与当前预览的装扮类型一致"
   }
  ]
 },
 {
  "name": "板子进房特效座驾说明文案验证",
  "case_number": "TC-PR1-TITLE-008",
  "module": "标题与说明",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "单件板子进房特效座驾装扮弹窗已展示（座驾-专属板子）",
  "remarks": "关联需求 REQ-DEC-002；需求点2 说明文案按『座驾』类型展示，板子与坐骑同属座驾类型；若产品为板子配置独立文案需按产品定义断言",
  "test_data": {
   "装扮类型": "座驾（板子进房特效）",
   "预期说明文案": "佩戴后，进房时展示动画效果"
  },
  "test_case_steps": [
   {
    "step": "查看弹窗内说明文案",
    "result": "说明文案显示『佩戴后，进房时展示动画效果』，与坐骑进房特效座驾说明文案一致（板子/坐骑同属座驾类型）"
   }
  ]
 },
 {
  "name": "多位数n的标题文案拼接验证",
  "case_number": "TC-PR1-TITLE-009",
  "module": "标题与说明",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "合并弹窗已展示10件装扮（麦位框×3、座驾×3、个人铭牌×4）",
  "remarks": "关联需求 REQ-DEC-002（需求点2 n为弹窗内装扮数）；边界值场景",
  "test_data": {
   "弹窗内装扮数": 10,
   "预期标题": "获得10件装扮"
  },
  "test_case_steps": [
   {
    "step": "打开合并弹窗，查看标题栏文案",
    "result": "标题显示『获得10件装扮』，多位数n完整拼接无截断、无格式错乱"
   }
  ]
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 25. ws-tc_sysconfig_v2

- 来源：`workspace/testcase/tc_sysconfig_v2.jsonl`　分组：(root)　用例数：30

```json
[
 {
  "case_number": "TC-PR-CONFIG-001",
  "name": "端口号列表加载正常-下拉菜单显示可用端口",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "软件已启动，串口驱动正常，系统至少有一个可用COM端口",
  "remarks": "关联需求 FP-001 端口号选择与连接",
  "test_data": {
   "port_list": "COM1, COM2, COM3"
  },
  "test_case_steps": [
   {
    "step": "1. 进入系统配置页面",
    "result": "页面加载完成"
   },
   {
    "step": "2. 点击端口号下拉框",
    "result": "下拉列表展开，显示系统中所有可用的COM端口列表"
   }
  ],
  "expected_result": "下拉列表正确显示所有可用COM端口，如COM1、COM2等"
 },
 {
  "case_number": "TC-PR-CONFIG-002",
  "name": "端口号选择有效端口-连接成功",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "串口设备已连接至COM1，且该端口未被其他程序占用",
  "remarks": "关联需求 FP-001 端口号选择与连接",
  "test_data": {
   "port": "COM1"
  },
  "test_case_steps": [
   {
    "step": "1. 进入系统配置页面，从端口号下拉框选择COM1",
    "result": "下拉框显示COM1"
   },
   {
    "step": "2. 点击【连接】按钮",
    "result": "连接成功，按钮状态变为已连接，状态提示区显示'已连接'"
   }
  ],
  "expected_result": "连接成功，界面显示已连接状态，连接按钮变为断开按钮"
 },
 {
  "case_number": "TC-PR-CONFIG-003",
  "name": "端口号已被占用-连接失败提示",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "COM1已被其他程序占用",
  "remarks": "关联需求 FP-001 端口号选择与连接",
  "test_data": {
   "port": "COM1"
  },
  "test_case_steps": [
   {
    "step": "1. 进入系统配置页面，从端口号下拉框选择COM1",
    "result": "下拉框显示COM1"
   },
   {
    "step": "2. 点击【连接】按钮",
    "result": "连接失败，弹窗或状态区提示'端口已被占用，请选择其他端口'"
   }
  ],
  "expected_result": "连接失败，系统给出明确错误提示"
 },
 {
  "case_number": "TC-PR-CONFIG-004",
  "name": "设备未就绪-连接失败提示",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "未连接串口设备或设备未上电，系统可用COM列表为空",
  "remarks": "关联需求 FP-001 端口号选择与连接",
  "test_data": {
   "port_status": "无可选端口"
  },
  "test_case_steps": [
   {
    "step": "1. 进入系统配置页面",
    "result": "页面加载完成"
   },
   {
    "step": "2. 查看端口号下拉列表",
    "result": "下拉列表为空或显示'无可用端口'，连接按钮置灰不可点击"
   }
  ],
  "expected_result": "当无可用端口时，连接按钮置灰不可点击，或点击后提示'无可用端口'"
 },
 {
  "case_number": "TC-PR-CONFIG-005",
  "name": "已连接状态下重复点击连接-拒绝操作",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "已成功连接至COM1，处于已连接状态",
  "remarks": "关联需求 FP-001 端口号选择与连接",
  "test_data": {
   "port": "COM1"
  },
  "test_case_steps": [
   {
    "step": "1. 确认当前已连接至COM1，连接按钮已变为断开按钮",
    "result": "界面显示已连接状态"
   },
   {
    "step": "2. 尝试再次点击已变为断开按钮的连接区域",
    "result": "系统执行断开操作或连接按钮置灰不可重复点击"
   }
  ],
  "expected_result": "已连接状态下不会重复发起连接请求，防止资源冲突"
 },
 {
  "case_number": "TC-PR-CONFIG-006",
  "name": "端口连接成功后断开-断开正常",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "已成功连接至COM1",
  "remarks": "关联需求 FP-001 端口号选择与连接",
  "test_data": {
   "port": "COM1"
  },
  "test_case_steps": [
   {
    "step": "1. 确认当前已连接至COM1",
    "result": "界面显示已连接状态"
   },
   {
    "step": "2. 点击【断开】按钮",
    "result": "连接断开，按钮恢复为【连接】状态，状态提示区显示'已断开'"
   }
  ],
  "expected_result": "断开成功，界面恢复到可重新连接状态"
 },
 {
  "case_number": "TC-PR-CONFIG-007",
  "name": "端口号为空时点击连接-拒绝操作",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "端口号下拉未选择任何端口（默认空值）",
  "remarks": "关联需求 FP-001 端口号选择与连接",
  "test_data": {
   "port": "未选择"
  },
  "test_case_steps": [
   {
    "step": "1. 进入系统配置页面，保持端口号下拉为未选择状态",
    "result": "下拉框显示默认提示如'请选择端口'"
   },
   {
    "step": "2. 点击【连接】按钮",
    "result": "连接按钮置灰不可点击，或点击后提示'请先选择端口'"
   }
  ],
  "expected_result": "未选择端口时连接操作被阻止，提示用户先选择端口"
 },
 {
  "case_number": "TC-PR-CONFIG-008",
  "name": "查询周期默认值100ms预填验证",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "首次进入系统配置页面，未保存过配置",
  "remarks": "关联需求 FP-004 查询周期配置",
  "test_data": {
   "expected_default": "100"
  },
  "test_case_steps": [
   {
    "step": "1. 进入系统配置页面",
    "result": "页面加载完成"
   },
   {
    "step": "2. 查看查询周期输入框",
    "result": "输入框中默认显示'100'，单位显示ms"
   }
  ],
  "expected_result": "查询周期输入框默认值为100ms（需求明确标注）"
 },
 {
  "case_number": "TC-PR-CONFIG-009",
  "name": "查询周期输入有效值1000ms-保存并回显成功",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "查询周期输入框显示默认值100ms",
  "remarks": "关联需求 FP-004 查询周期配置",
  "test_data": {
   "query_cycle": "1000"
  },
  "test_case_steps": [
   {
    "step": "1. 进入系统配置页面",
    "result": "页面加载完成"
   },
   {
    "step": "2. 在查询周期输入框中输入'1000'",
    "result": "输入框显示1000"
   },
   {
    "step": "3. 点击【保存】按钮",
    "result": "保存成功提示"
   },
   {
    "step": "4. 刷新/重新进入系统配置页面",
    "result": "查询周期输入框仍显示1000"
   }
  ],
  "expected_result": "合法值1000ms保存成功，重新加载后配置持久化回显一致"
 },
 {
  "case_number": "TC-PR-CONFIG-010",
  "name": "查询周期最小值1ms边界测试",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "查询周期输入框为空或为默认值",
  "remarks": "关联需求 FP-004 查询周期配置 — 基于假设：最小允许值≥1ms",
  "test_data": {
   "query_cycle": "1"
  },
  "test_case_steps": [
   {
    "step": "1. 进入系统配置页面",
    "result": "页面加载完成"
   },
   {
    "step": "2. 在查询周期输入框中输入'1'",
    "result": "输入框显示1"
   },
   {
    "step": "3. 点击【保存】按钮",
    "result": "保存成功提示"
   }
  ],
  "expected_result": "最小值1ms保存成功，系统接受该边界值"
 },
 {
  "case_number": "TC-PR-CONFIG-011",
  "name": "查询周期输入0ms-拒绝保存",
  "module": "系统配置",
  "case_type": "boundary",
  "priority": "high",
  "preconditions": "查询周期输入框为空",
  "remarks": "关联需求 FP-004 查询周期配置 — 基于假设：0ms为非法",
  "test_data": {
   "query_cycle": "0"
  },
  "test_case_steps": [
   {
    "step": "1. 进入系统配置页面",
    "result": "页面加载完成"
   },
   {
    "step": "2. 在查询周期输入框中输入'0'",
    "result": "输入框显示0"
   },
   {
    "step": "3. 点击【保存】按钮",
    "result": "保存失败，提示'查询周期不能小于1ms'"
   }
  ],
  "expected_result": "0ms被拒绝保存，系统给出明确错误提示"
 },
 {
  "case_number": "TC-PR-CONFIG-012",
  "name": "查询周期输入极大值100000ms边界测试",
  "module": "系统配置",
  "case_type": "boundary",
  "priority": "high",
  "preconditions": "查询周期输入框为空",
  "remarks": "关联需求 FP-004 查询周期配置",
  "test_data": {
   "query_cycle": "100000"
  },
  "test_case_steps": [
   {
    "step": "1. 进入系统配置页面",
    "result": "页面加载完成"
   },
   {
    "step": "2. 在查询周期输入框中输入'100000'",
    "result": "输入框显示100000"
   },
   {
    "step": "3. 点击【保存】按钮",
    "result": "保存成功提示"
   }
  ],
  "expected_result": "极大值100000ms保存成功或根据实际限制给出提示"
 },
 {
  "case_number": "TC-PR-CONFIG-013",
  "name": "查询周期输入负数-拒绝保存",
  "module": "系统配置",
  "case_type": "boundary",
  "priority": "high",
  "preconditions": "查询周期输入框为空",
  "remarks": "关联需求 FP-004 查询周期配置",
  "test_data": {
   "query_cycle": "-100"
  },
  "test_case_steps": [
   {
    "step": "1. 进入系统配置页面",
    "result": "页面加载完成"
   },
   {
    "step": "2. 在查询周期输入框中输入'-100'",
    "result": "输入框显示-100"
   },
   {
    "step": "3. 点击【保存】按钮",
    "result": "保存失败，提示'查询周期不能为负数'"
   }
  ],
  "expected_result": "负数被拒绝保存，系统给出明确错误提示"
 },
 {
  "case_number": "TC-PR-CONFIG-014",
  "name": "所有配置项合法-保存成功",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "端口已成功连接，所有配置项输入框已填写合法值",
  "remarks": "关联需求 FP-006 保存配置",
  "test_data": {
   "stable_time": "30",
   "volume_threshold": "10",
   "query_cycle": "100",
   "flow_threshold": "5"
  },
  "test_case_steps": [
   {
    "step": "1. 配气稳定时间输入'30'",
    "result": "显示30"
   },
   {
    "step": "2. 配气总量偏差阈值输入'10'",
    "result": "显示10"
   },
   {
    "step": "3. 查询周期输入'100'",
    "result": "显示100"
   },
   {
    "step": "4. 流量偏差阈值输入'5'",
    "result": "显示5"
   },
   {
    "step": "5. 点击【保存】按钮",
    "result": "提示'保存成功'"
   }
  ],
  "expected_result": "所有合法配置保存成功，系统给出成功提示"
 },
 {
  "case_number": "TC-PR-CONFIG-015",
  "name": "保存成功后重新进入页面-配置回显一致",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "已完成一次配置保存操作（稳定时间30s、偏差阈值10ml、查询周期100ms、流量阈值5ml/min）",
  "remarks": "关联需求 FP-006/FP-007 保存配置与页面回显",
  "test_data": {
   "stable_time": "30",
   "volume_threshold": "10",
   "query_cycle": "100",
   "flow_threshold": "5"
  },
  "test_case_steps": [
   {
    "step": "1. 关闭系统配置页面或切换到其他菜单",
    "result": "页面切换成功"
   },
   {
    "step": "2. 重新进入系统配置页面",
    "result": "页面加载完成"
   },
   {
    "step": "3. 查看各配置项输入框的值",
    "result": "配气稳定时间=30，配气总量偏差阈值=10，查询周期=100，流量偏差阈值=5"
   }
  ],
  "expected_result": "所有已保存配置字段正确回显，与保存时一致"
 },
 {
  "case_number": "TC-PR-CONFIG-016",
  "name": "非法输入时保存按钮拦截-保存失败",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "任一项配置输入框为非法值（如负数/非数字字符）",
  "remarks": "关联需求 FP-006 保存配置",
  "test_data": {
   "stable_time": "abc"
  },
  "test_case_steps": [
   {
    "step": "1. 配气稳定时间输入'abc'（非数字）",
    "result": "输入框显示abc"
   },
   {
    "step": "2. 点击【保存】按钮",
    "result": "保存失败，系统提示'配气稳定时间必须为数值'，或保存按钮置灰"
   }
  ],
  "expected_result": "输入非法值时保存操作被阻止，系统给出对应的错误提示"
 },
 {
  "case_number": "TC-PR-CONFIG-017",
  "name": "系统异常时保存失败-给出提示",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "所有配置项已输入合法值，但系统出现异常（如数据库写入失败）",
  "remarks": "关联需求 FP-006 保存配置",
  "test_data": {
   "stable_time": "30",
   "volume_threshold": "10",
   "query_cycle": "100",
   "flow_threshold": "5"
  },
  "test_case_steps": [
   {
    "step": "1. 所有配置项输入合法值",
    "result": "输入框显示正常"
   },
   {
    "step": "2. 模拟系统异常（如磁盘满/数据库不可写）",
    "result": "异常已注入"
   },
   {
    "step": "3. 点击【保存】按钮",
    "result": "保存失败，提示'保存失败，请稍后重试'或给出具体错误信息"
   }
  ],
  "expected_result": "系统异常时保存失败并给出明确提示，配置信息不丢失"
 },
 {
  "case_number": "TC-PR-CONFIG-018",
  "name": "保存空值字段-提示必填",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "端口已成功连接，所有配置项输入框均为空",
  "remarks": "关联需求 FP-006 保存配置 — 基于假设：所有配置项为必填",
  "test_data": {
   "stable_time": "",
   "volume_threshold": "",
   "query_cycle": "",
   "flow_threshold": ""
  },
  "test_case_steps": [
   {
    "step": "1. 保持所有配置项输入框为空",
    "result": "所有输入框为空"
   },
   {
    "step": "2. 点击【保存】按钮",
    "result": "保存失败，空字段下方提示'此项为必填'或汇总提示'请填写所有必填项'"
   }
  ],
  "expected_result": "空字段保存被拒绝，系统提示必填项"
 },
 {
  "case_number": "TC-PR-CONFIG-019",
  "name": "首次进入系统配置页-显示默认值",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "全新安装或配置未初始化，从未保存过任何配置",
  "remarks": "关联需求 FP-007 页面加载与回显",
  "test_data": {
   "query_cycle_default": "100",
   "other_fields": "empty"
  },
  "test_case_steps": [
   {
    "step": "1. 首次进入系统配置页面",
    "result": "页面加载完成"
   },
   {
    "step": "2. 查看各配置项输入框",
    "result": "配气稳定时间为空；配气总量偏差阈值为空；查询周期显示'100'（默认值）；流量偏差阈值为空"
   },
   {
    "step": "3. 端口号下拉框默认显示提示文字如'请选择端口'",
    "result": "下拉框未选择任何端口"
   }
  ],
  "expected_result": "首次加载时：查询周期默认100ms预填，其他配置项为空，端口号未选择"
 },
 {
  "case_number": "TC-PR-CONFIG-020",
  "name": "从其他菜单切换回系统配置-配置回显正常",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "已保存过配置（稳定时间=30s，偏差阈值=10ml，查询周期=100ms，流量阈值=5ml/min）",
  "remarks": "关联需求 FP-007 页面加载与回显",
  "test_data": {
   "stable_time": "30",
   "volume_threshold": "10",
   "query_cycle": "100",
   "flow_threshold": "5"
  },
  "test_case_steps": [
   {
    "step": "1. 切换至【任务管理】菜单",
    "result": "任务管理页面加载"
   },
   {
    "step": "2. 再切换回【系统配置】菜单",
    "result": "系统配置页面加载"
   },
   {
    "step": "3. 检查各配置项值",
    "result": "配气稳定时间=30，配气总量偏差阈值=10，查询周期=100，流量偏差阈值=5，端口号保持之前的选择"
   }
  ],
  "expected_result": "从其他菜单切换回时，已保存的配置正确回显"
 },
 {
  "case_number": "TC-PR-CONFIG-021",
  "name": "配气稳定时间输入合法正数-保存成功",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "其他配置项已填入合法值",
  "remarks": "关联需求 FP-002 配气稳定时间配置",
  "test_data": {
   "stable_time": "60"
  },
  "test_case_steps": [
   {
    "step": "1. 在配气稳定时间输入框中输入'60'",
    "result": "输入框显示60"
   },
   {
    "step": "2. 点击【保存】按钮",
    "result": "保存成功"
   }
  ],
  "expected_result": "合法值60秒保存成功"
 },
 {
  "case_number": "TC-PR-CONFIG-022",
  "name": "配气稳定时间输入0值-拒绝保存",
  "module": "系统配置",
  "case_type": "boundary",
  "priority": "high",
  "preconditions": "其他配置项已填入合法值",
  "remarks": "关联需求 FP-002 配气稳定时间配置 — 基于假设：稳定时间须为正数",
  "test_data": {
   "stable_time": "0"
  },
  "test_case_steps": [
   {
    "step": "1. 在配气稳定时间输入框中输入'0'",
    "result": "输入框显示0"
   },
   {
    "step": "2. 点击【保存】按钮",
    "result": "保存失败，提示'配气稳定时间必须大于0'"
   }
  ],
  "expected_result": "0值被拒绝保存，系统给出错误提示"
 },
 {
  "case_number": "TC-PR-CONFIG-023",
  "name": "配气稳定时间输入负数-拒绝保存",
  "module": "系统配置",
  "case_type": "boundary",
  "priority": "high",
  "preconditions": "其他配置项已填入合法值",
  "remarks": "关联需求 FP-002 配气稳定时间配置",
  "test_data": {
   "stable_time": "-30"
  },
  "test_case_steps": [
   {
    "step": "1. 在配气稳定时间输入框中输入'-30'",
    "result": "输入框显示-30"
   },
   {
    "step": "2. 点击【保存】按钮",
    "result": "保存失败，提示'配气稳定时间不能为负数'"
   }
  ],
  "expected_result": "负数被拒绝保存，系统给出错误提示"
 },
 {
  "case_number": "TC-PR-CONFIG-024",
  "name": "配气稳定时间输入极大值测试",
  "module": "系统配置",
  "case_type": "boundary",
  "priority": "high",
  "preconditions": "其他配置项已填入合法值",
  "remarks": "关联需求 FP-002 配气稳定时间配置",
  "test_data": {
   "stable_time": "999999"
  },
  "test_case_steps": [
   {
    "step": "1. 在配气稳定时间输入框中输入'999999'",
    "result": "输入框显示999999"
   },
   {
    "step": "2. 点击【保存】按钮",
    "result": "根据系统约束，保存成功或提示'请检查配气稳定时间范围'"
   }
  ],
  "expected_result": "系统对极大值有合理处理：或接受保存，或给出范围提示"
 },
 {
  "case_number": "TC-PR-CONFIG-025",
  "name": "配气稳定时间输入非数字字符-拒绝接受",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "其他配置项已填入合法值",
  "remarks": "关联需求 FP-002 配气稳定时间配置",
  "test_data": {
   "stable_time": "@#$%"
  },
  "test_case_steps": [
   {
    "step": "1. 在配气稳定时间输入框中输入特殊字符'@#$%'",
    "result": "输入框显示对应字符"
   },
   {
    "step": "2. 点击【保存】按钮",
    "result": "保存失败，提示'配气稳定时间必须为有效数字'"
   }
  ],
  "expected_result": "非数字字符被拒绝保存，系统给出错误提示"
 },
 {
  "case_number": "TC-PR-CONFIG-026",
  "name": "配气总量偏差阈值输入合法正数-保存成功",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "其他配置项已填入合法值",
  "remarks": "关联需求 FP-003 配气总量偏差阈值配置",
  "test_data": {
   "volume_threshold": "5.5"
  },
  "test_case_steps": [
   {
    "step": "1. 在配气总量偏差阈值输入框中输入'5.5'",
    "result": "输入框显示5.5"
   },
   {
    "step": "2. 点击【保存】按钮",
    "result": "保存成功"
   }
  ],
  "expected_result": "合法值5.5ml保存成功"
 },
 {
  "case_number": "TC-PR-CONFIG-027",
  "name": "配气总量偏差阈值输入0值-拒绝保存",
  "module": "系统配置",
  "case_type": "boundary",
  "priority": "high",
  "preconditions": "其他配置项已填入合法值",
  "remarks": "关联需求 FP-003 配气总量偏差阈值配置 — 基于假设：偏差阈值须为正数",
  "test_data": {
   "volume_threshold": "0"
  },
  "test_case_steps": [
   {
    "step": "1. 在配气总量偏差阈值输入框中输入'0'",
    "result": "输入框显示0"
   },
   {
    "step": "2. 点击【保存】按钮",
    "result": "保存失败，提示'配气总量偏差阈值必须大于0'"
   }
  ],
  "expected_result": "0值被拒绝保存，系统给出错误提示"
 },
 {
  "case_number": "TC-PR-CONFIG-028",
  "name": "配气总量偏差阈值输入负数-拒绝保存",
  "module": "系统配置",
  "case_type": "boundary",
  "priority": "high",
  "preconditions": "其他配置项已填入合法值",
  "remarks": "关联需求 FP-003 配气总量偏差阈值配置",
  "test_data": {
   "volume_threshold": "-10"
  },
  "test_case_steps": [
   {
    "step": "1. 在配气总量偏差阈值输入框中输入'-10'",
    "result": "输入框显示-10"
   },
   {
    "step": "2. 点击【保存】按钮",
    "result": "保存失败，提示'配气总量偏差阈值不能为负数'"
   }
  ],
  "expected_result": "负数被拒绝保存，系统给出错误提示"
 },
 {
  "case_number": "TC-PR-CONFIG-029",
  "name": "配气总量偏差阈值输入极大值测试",
  "module": "系统配置",
  "case_type": "boundary",
  "priority": "high",
  "preconditions": "其他配置项已填入合法值",
  "remarks": "关联需求 FP-003 配气总量偏差阈值配置",
  "test_data": {
   "volume_threshold": "99999.99"
  },
  "test_case_steps": [
   {
    "step": "1. 在配气总量偏差阈值输入框中输入'99999.99'",
    "result": "输入框显示99999.99"
   },
   {
    "step": "2. 点击【保存】按钮",
    "result": "根据系统约束，保存成功或提示超出范围"
   }
  ],
  "expected_result": "系统对极大值有合理处理"
 },
 {
  "case_number": "TC-PR-CONFIG-030",
  "name": "配气总量偏差阈值输入非数字字符-拒绝保存",
  "module": "系统配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "其他配置项已填入合法值",
  "remarks": "关联需求 FP-003 配气总量偏差阈值配置",
  "test_data": {
   "volume_threshold": "abc!@#"
  },
  "test_case_steps": [
   {
    "step": "1. 在配气总量偏差阈值输入框中输入'abc!@#'",
    "result": "输入框显示对应字符"
   },
   {
    "step": "2. 点击【保存】按钮",
    "result": "保存失败，提示'配气总量偏差阈值必须为有效数字'"
   }
  ],
  "expected_result": "非数字字符被拒绝保存，系统给出错误提示"
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 26. ws-PR-1-test_cases_dressup_module_04_single

- 来源：`workspace/testcase/PR-1/test_cases_dressup_module_04_single.jsonl`　分组：PR-1　用例数：7

```json
[
 {
  "name": "非合并弹窗仅显示『立即佩戴』一个按钮",
  "case_number": "TC-PR1-SINGLE-001",
  "module": "单装扮操作",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "单件装扮弹窗已展示（麦位框-萌爪闪闪），弹窗内装扮数为1",
  "remarks": "关联需求 REQ-DEC-004（需求点4 按钮数量与文案）",
  "test_data": {
   "弹窗内装扮数": 1,
   "按钮1": "立即佩戴",
   "不应显示按钮": [
    "佩戴当前",
    "全部佩戴"
   ]
  },
  "test_case_steps": [
   {
    "step": "查看弹窗底部按钮区域",
    "result": "仅显示1个按钮『立即佩戴』，不显示『佩戴当前』和『全部佩戴』"
   }
  ]
 },
 {
  "name": "点击立即佩戴成功后关闭弹窗并toast提示",
  "case_number": "TC-PR1-SINGLE-002",
  "module": "单装扮操作",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "单件麦位框装扮弹窗已展示（麦位框-萌爪闪闪）；网络正常",
  "remarks": "关联需求 REQ-DEC-004（需求点4 非合并立即佩戴逻辑）",
  "test_data": {
   "装扮": "麦位框-萌爪闪闪",
   "操作": "点击立即佩戴",
   "预期toast": "装扮已佩戴",
   "预期服务端结果": "佩戴接口返回业务成功码"
  },
  "test_case_steps": [
   {
    "step": "点击『立即佩戴』按钮，观察佩戴请求",
    "result": "麦位框佩戴请求发送成功，服务端返回业务成功码（HTTP 200/业务成功响应），无错误码返回"
   },
   {
    "step": "观察弹窗与toast提示",
    "result": "弹窗自动关闭；toast提示『装扮已佩戴』"
   }
  ]
 },
 {
  "name": "立即佩戴后麦位框实际生效于房间麦位头像",
  "case_number": "TC-PR1-SINGLE-003",
  "module": "单装扮操作",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "用户已通过『立即佩戴』成功佩戴麦位框-萌爪闪闪",
  "remarks": "关联需求 REQ-DEC-004（需求点4 佩戴后生效）",
  "test_data": {
   "已佩戴装扮": "麦位框-萌爪闪闪",
   "验证位置": "房间麦位头像"
  },
  "test_case_steps": [
   {
    "step": "返回房间页面，查看自己的麦位头像",
    "result": "房间麦位头像上展示佩戴的麦位框-萌爪闪闪效果（含动效）"
   }
  ]
 },
 {
  "name": "座驾立即佩戴后进房展示动画效果",
  "case_number": "TC-PR1-SINGLE-004",
  "module": "单装扮操作",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "用户已通过『立即佩戴』成功佩戴座驾-星河战舰",
  "remarks": "关联需求 REQ-DEC-004（需求点4 座驾佩戴后进房展示动画）",
  "test_data": {
   "已佩戴装扮": "座驾-星河战舰",
   "验证方式": "退出房间后重新进入"
  },
  "test_case_steps": [
   {
    "step": "退出当前房间",
    "result": "退出房间成功，无异常"
   },
   {
    "step": "重新进入房间",
    "result": "进房时展示佩戴的座驾-星河战舰动画效果（坐骑进房特效）"
   }
  ]
 },
 {
  "name": "点击关闭按钮直接关闭弹窗且不佩戴装扮",
  "case_number": "TC-PR1-SINGLE-005",
  "module": "单装扮操作",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "单件麦位框装扮弹窗已展示（麦位框-萌爪闪闪）",
  "remarks": "关联需求 REQ-DEC-004（需求点4 关闭按钮）；入包断言：关闭=不佩戴但发放必须入包",
  "test_data": {
   "装扮": "麦位框-萌爪闪闪",
   "操作": "点击关闭按钮",
   "入包校验": "背包中可查到该装扮且数量+1"
  },
  "test_case_steps": [
   {
    "step": "点击弹窗『关闭』按钮",
    "result": "弹窗直接关闭，无toast提示"
   },
   {
    "step": "查看麦位框-萌爪闪闪的佩戴状态",
    "result": "麦位框-萌爪闪闪未被佩戴（仍处于未佩戴状态）"
   },
   {
    "step": "查看背包中该装扮",
    "result": "麦位框-萌爪闪闪已入包（背包中可查到，发放数量+1，有效期按发放规则叠加/刷新），关闭弹窗不导致发放丢失"
   }
  ]
 },
 {
  "name": "立即佩戴接口失败时弹窗不关闭并提示",
  "case_number": "TC-PR1-SINGLE-006",
  "module": "单装扮操作",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "单件麦位框装扮弹窗已展示（麦位框-萌爪闪闪）；服务端佩戴接口被模拟为返回失败（网络异常/服务端错误，返回明确错误码）",
  "remarks": "关联需求 REQ-DEC-004；异常场景——失败提示具体文案以服务端错误码映射为准，待开发确认",
  "test_data": {
   "装扮": "麦位框-萌爪闪闪",
   "服务端响应": "佩戴接口返回失败错误码（如网络错误/服务端5xx）",
   "操作": "点击立即佩戴",
   "失败提示": "展示错误码对应的失败提示（如『佩戴失败，请稍后重试』）"
  },
  "test_case_steps": [
   {
    "step": "点击『立即佩戴』按钮",
    "result": "弹窗不关闭，展示服务端错误码对应的失败提示信息（如『佩戴失败，请稍后重试』），无崩溃、无卡死"
   },
   {
    "step": "检查装扮佩戴状态并再次尝试",
    "result": "装扮未被佩戴；可再次点击『立即佩戴』重试，重试后无重复toast、无异常"
   }
  ]
 },
 {
  "name": "立即佩戴接口超时挂起时的处理",
  "case_number": "TC-PR1-SINGLE-007",
  "module": "单装扮操作",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "单件麦位框装扮弹窗已展示（麦位框-萌爪闪闪）；佩戴接口被模拟为长时间无响应（超时10秒）",
  "remarks": "关联需求 REQ-DEC-004；异常场景",
  "test_data": {
   "装扮": "麦位框-萌爪闪闪",
   "服务端行为": "佩戴接口超时无响应（10秒）",
   "操作": "点击立即佩戴"
  },
  "test_case_steps": [
   {
    "step": "点击『立即佩戴』按钮，等待接口超时",
    "result": "接口超时后弹窗不关闭、无崩溃，展示超时/失败提示信息"
   },
   {
    "step": "超时后再次点击『立即佩戴』",
    "result": "可正常发起重试请求，无重复toast、无卡死；重试成功则按成功流程处理"
   }
  ]
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 27. ws-s53_test_cases

- 来源：`workspace/testcase/s53_test_cases.jsonl`　分组：(root)　用例数：30

```json
[
 {
  "case_number": "TC-S53-MAINT-001",
  "name": "定期维护-开始时间新增3天后选项",
  "module": "设置-定期维护",
  "case_type": "functional",
  "priority": "high",
  "preconditions": [
   "系统时间设置为2025-07-10 10:00:00",
   "用户已登录设置页面"
  ],
  "test_case_steps": [
   {
    "step": "进入设置-定期维护页面",
    "result": "页面正常加载"
   },
   {
    "step": "点击开始时间下拉框",
    "result": "下拉选项中包含'3天后'选项"
   },
   {
    "step": "选择'3天后'选项",
    "result": "选项被正确选中，开始时间显示为当前时间+3天"
   }
  ],
  "test_data": {
   "系统时间": "2025-07-10 10:00:00",
   "预期时间": "2025-07-13 10:00:00"
  },
  "remarks": "关联需求 REQ-S53-02"
 },
 {
  "case_number": "TC-S53-MAINT-002",
  "name": "定期维护-开始时间新增5天后选项",
  "module": "设置-定期维护",
  "case_type": "functional",
  "priority": "high",
  "preconditions": [
   "系统时间设置为2025-07-10 10:00:00",
   "用户已登录设置页面"
  ],
  "test_case_steps": [
   {
    "step": "进入设置-定期维护页面",
    "result": "页面正常加载"
   },
   {
    "step": "点击开始时间下拉框",
    "result": "下拉选项中包含'5天后'选项"
   },
   {
    "step": "选择'5天后'选项",
    "result": "选项被正确选中，开始时间显示为当前时间+5天"
   }
  ],
  "test_data": {
   "系统时间": "2025-07-10 10:00:00",
   "预期时间": "2025-07-15 10:00:00"
  },
  "remarks": "关联需求 REQ-S53-02"
 },
 {
  "case_number": "TC-S53-MAINT-003",
  "name": "定期维护-开始时间新增7天后选项",
  "module": "设置-定期维护",
  "case_type": "functional",
  "priority": "high",
  "preconditions": [
   "系统时间设置为2025-07-10 10:00:00",
   "用户已登录设置页面"
  ],
  "test_case_steps": [
   {
    "step": "进入设置-定期维护页面",
    "result": "页面正常加载"
   },
   {
    "step": "点击开始时间下拉框",
    "result": "下拉选项中包含'7天后'选项"
   },
   {
    "step": "选择'7天后'选项",
    "result": "选项被正确选中，开始时间显示为当前时间+7天"
   }
  ],
  "test_data": {
   "系统时间": "2025-07-10 10:00:00",
   "预期时间": "2025-07-17 10:00:00"
  },
  "remarks": "关联需求 REQ-S53-02"
 },
 {
  "case_number": "TC-S53-MAINT-004",
  "name": "定期维护-原时间改为中文显示",
  "module": "设置-定期维护",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": [
   "用户已登录设置页面"
  ],
  "test_case_steps": [
   {
    "step": "进入设置-定期维护页面",
    "result": "页面正常加载"
   },
   {
    "step": "查看开始时间下拉选项中已有的时间选项",
    "result": "原时间显示为中文格式，如'1小时后'、'2小时后'等，而非英文格式"
   }
  ],
  "test_data": {
   "预期显示": "1小时后、2小时后、3天后、5天后、7天后"
  },
  "remarks": "关联需求 REQ-S53-02"
 },
 {
  "case_number": "TC-S53-MAINT-005",
  "name": "自动老化-开始时间新增选项",
  "module": "设置-自动老化",
  "case_type": "functional",
  "priority": "high",
  "preconditions": [
   "系统时间设置为2025-07-10 10:00:00",
   "用户已登录设置页面"
  ],
  "test_case_steps": [
   {
    "step": "进入设置-自动老化页面",
    "result": "页面正常加载"
   },
   {
    "step": "点击开始时间下拉框",
    "result": "下拉选项中包含'3天后'、'5天后'、'7天后'选项"
   },
   {
    "step": "分别选择各选项",
    "result": "各选项被正确选中，时间计算正确"
   }
  ],
  "test_data": {
   "系统时间": "2025-07-10 10:00:00",
   "预期": "3天后:2025-07-13, 5天后:2025-07-15, 7天后:2025-07-17"
  },
  "remarks": "关联需求 REQ-S53-02"
 },
 {
  "case_number": "TC-S53-RES-001",
  "name": "结果页面-初始布局验证",
  "module": "结果页面",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": [
   "存在≥3条检测完成的任务数据",
   "用户已登录系统"
  ],
  "test_case_steps": [
   {
    "step": "进入结果页面",
    "result": "页面正常加载"
   },
   {
    "step": "查看页面分布",
    "result": "谱图占页面1/2，结果列表展示2条"
   }
  ],
  "test_data": {
   "任务数量": "≥3条"
  },
  "remarks": "关联需求 REQ-S53-03"
 },
 {
  "case_number": "TC-S53-RES-002",
  "name": "结果页面-记住展示结果-切换页面",
  "module": "结果页面",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": [
   "结果页面展示特定结果（如B001、B002）"
  ],
  "test_case_steps": [
   {
    "step": "结果页面展示特定结果",
    "result": "结果正常展示"
   },
   {
    "step": "切换到其他页面（如检测页面）",
    "result": "切换成功"
   },
   {
    "step": "返回结果页面",
    "result": "之前展示的结果保持不变"
   }
  ],
  "test_data": {
   "任务": "B001、B002"
  },
  "remarks": "关联需求 REQ-S53-03"
 },
 {
  "case_number": "TC-S53-RES-003",
  "name": "结果页面-记住展示结果-重新登录",
  "module": "结果页面",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": [
   "结果页面展示特定结果（如B001、B002）"
  ],
  "test_case_steps": [
   {
    "step": "结果页面展示特定结果",
    "result": "结果正常展示"
   },
   {
    "step": "退出登录",
    "result": "退出成功"
   },
   {
    "step": "重新登录进入结果页面",
    "result": "之前展示的结果保持不变"
   }
  ],
  "test_data": {
   "任务": "B001、B002"
  },
  "remarks": "关联需求 REQ-S53-03"
 },
 {
  "case_number": "TC-S53-RES-004",
  "name": "结果页面-仅显示选中-开启",
  "module": "结果页面",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": [
   "存在多条检测完成的任务"
  ],
  "test_case_steps": [
   {
    "step": "开启'仅显示选中'功能",
    "result": "功能开启成功"
   },
   {
    "step": "选中1个任务（如B001）",
    "result": "列表仅展示选中的任务B001"
   }
  ],
  "test_data": {
   "选中任务": "B001"
  },
  "remarks": "关联需求 REQ-S53-03"
 },
 {
  "case_number": "TC-S53-RES-005",
  "name": "结果页面-仅显示选中-取消选中恢复",
  "module": "结果页面",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": [
   "已开启'仅显示选中'并选中了任务"
  ],
  "test_case_steps": [
   {
    "step": "开启'仅显示选中'并选中任务B001",
    "result": "列表仅显示B001"
   },
   {
    "step": "取消选中B001",
    "result": "列表恢复显示所有任务"
   }
  ],
  "test_data": {
   "操作": "取消选中"
  },
  "remarks": "关联需求 REQ-S53-03"
 },
 {
  "case_number": "TC-S53-RES-006",
  "name": "结果页面-标题去掉验证",
  "module": "结果页面",
  "case_type": "functional",
  "priority": "high",
  "preconditions": [
   "用户已登录系统"
  ],
  "test_case_steps": [
   {
    "step": "进入结果页面",
    "result": "页面正常加载"
   },
   {
    "step": "查看页面标题区域",
    "result": "页面无'检测结果''谱图展示''结果详情'标题"
   }
  ],
  "test_data": {},
  "remarks": "关联需求 REQ-S53-03"
 },
 {
  "case_number": "TC-S53-RES-007",
  "name": "结果页面-框选放大谱图功能",
  "module": "结果页面",
  "case_type": "functional",
  "priority": "high",
  "preconditions": [
   "存在含谱图数据的任务"
  ],
  "test_case_steps": [
   {
    "step": "在谱图上框选区域",
    "result": "框选操作正常"
   },
   {
    "step": "查看谱图",
    "result": "谱图放大到框选区域，无拉伸条"
   }
  ],
  "test_data": {},
  "remarks": "关联需求 REQ-S53-03"
 },
 {
  "case_number": "TC-S53-RES-008",
  "name": "结果页面-拖拽线样式验证",
  "module": "结果页面",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": [
   "用户已登录结果页面"
  ],
  "test_case_steps": [
   {
    "step": "查看谱图与列表之间的拖拽线",
    "result": "拖拽线变细"
   }
  ],
  "test_data": {},
  "remarks": "关联需求 REQ-S53-03"
 },
 {
  "case_number": "TC-S53-RES-009",
  "name": "结果页面-框选/重置/标本编码纵向排列",
  "module": "结果页面",
  "case_type": "functional",
  "priority": "high",
  "preconditions": [
   "用户已登录结果页面"
  ],
  "test_case_steps": [
   {
    "step": "查看谱图区域的操作按钮布局",
    "result": "框选谱图、重置、标本编码按钮纵向排列"
   }
  ],
  "test_data": {},
  "remarks": "关联需求 REQ-S53-03"
 },
 {
  "case_number": "TC-S53-RES-010",
  "name": "结果页面-查看报告按钮位置",
  "module": "结果页面",
  "case_type": "functional",
  "priority": "high",
  "preconditions": [
   "用户已登录结果页面"
  ],
  "test_case_steps": [
   {
    "step": "查看结果页面标签行",
    "result": "'查看报告'按钮位于标签行内"
   }
  ],
  "test_data": {},
  "remarks": "关联需求 REQ-S53-03"
 },
 {
  "case_number": "TC-S53-RES-011",
  "name": "结果页面-谱图样式验证",
  "module": "结果页面",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": [
   "存在含谱图数据的任务"
  ],
  "test_case_steps": [
   {
    "step": "查看谱图显示",
    "result": "谱图颜色为黄色，白色底框线颜色调浅，横纵坐标和单位清晰"
   }
  ],
  "test_data": {},
  "remarks": "关联需求 REQ-S53-03"
 },
 {
  "case_number": "TC-S53-RES-012",
  "name": "结果页面-历史改为详情显示定标编码",
  "module": "结果页面",
  "case_type": "functional",
  "priority": "high",
  "preconditions": [
   "任务关联定标编码CA20251223110914"
  ],
  "test_case_steps": [
   {
    "step": "查看结果列表中的操作列",
    "result": "'历史'已改为'详情'"
   },
   {
    "step": "点击'详情'",
    "result": "显示关联的定标编码"
   }
  ],
  "test_data": {
   "定标编码": "CA20251223110914"
  },
  "remarks": "关联需求 REQ-S53-03"
 },
 {
  "case_number": "TC-S53-DEV-001",
  "name": "设备控制工具-设置参数显示",
  "module": "设备控制工具",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": [
   "设备控制工具已打开"
  ],
  "test_case_steps": [
   {
    "step": "打开设备控制工具",
    "result": "工具正常打开"
   },
   {
    "step": "查看参数显示区域",
    "result": "设置参数正常显示"
   }
  ],
  "test_data": {},
  "remarks": "关联需求 REQ-S53-04"
 },
 {
  "case_number": "TC-S53-DEV-002",
  "name": "设备控制工具-全部显示3位小数-正常值",
  "module": "设备控制工具",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": [
   "设备控制工具已打开"
  ],
  "test_case_steps": [
   {
    "step": "输入含多位小数的参数值12.3456",
    "result": "输入成功"
   },
   {
    "step": "查看显示",
    "result": "显示为12.346（四舍五入保留3位小数）"
   },
   {
    "step": "输入参数值5.5",
    "result": "输入成功"
   },
   {
    "step": "查看显示",
    "result": "显示为5.500"
   }
  ],
  "test_data": {
   "输入值1": "12.3456",
   "预期显示1": "12.346",
   "输入值2": "5.5",
   "预期显示2": "5.500"
  },
  "remarks": "关联需求 REQ-S53-04"
 },
 {
  "case_number": "TC-S53-DEV-003",
  "name": "设备控制工具-全部显示3位小数-边界值",
  "module": "设备控制工具",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": [
   "设备控制工具已打开"
  ],
  "test_case_steps": [
   {
    "step": "输入整数100",
    "result": "输入成功"
   },
   {
    "step": "查看显示",
    "result": "显示为100.000"
   },
   {
    "step": "输入极小值0.0001",
    "result": "输入成功"
   },
   {
    "step": "查看显示",
    "result": "显示为0.000"
   }
  ],
  "test_data": {
   "输入值1": "100",
   "预期显示1": "100.000",
   "输入值2": "0.0001",
   "预期显示2": "0.000"
  },
  "remarks": "关联需求 REQ-S53-04"
 },
 {
  "case_number": "TC-S53-TEMP-001",
  "name": "检测阀温度-新增字段显示",
  "module": "设置-设备配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": [
   "用户已登录设置页面"
  ],
  "test_case_steps": [
   {
    "step": "进入设置-设备配置页面",
    "result": "页面正常加载"
   },
   {
    "step": "查看检测模块1配置",
    "result": "配置中包含'检测阀温度'和'检测阀温度阈值'字段"
   },
   {
    "step": "依次查看检测模块2、3、4配置",
    "result": "每个检测模块配置中均有'检测阀温度'和'检测阀温度阈值'字段"
   }
  ],
  "test_data": {},
  "remarks": "关联需求 REQ-S53-05"
 },
 {
  "case_number": "TC-S53-TEMP-002",
  "name": "检测阀温度-正常输入",
  "module": "设置-设备配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": [
   "用户已登录设置页面"
  ],
  "test_case_steps": [
   {
    "step": "在检测阀温度输入80",
    "result": "输入成功"
   },
   {
    "step": "点击保存",
    "result": "保存成功，显示输入值80"
   }
  ],
  "test_data": {
   "检测阀温度": "80℃"
  },
  "remarks": "关联需求 REQ-S53-05"
 },
 {
  "case_number": "TC-S53-TEMP-003",
  "name": "检测阀温度阈值-正常输入",
  "module": "设置-设备配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": [
   "用户已登录设置页面"
  ],
  "test_case_steps": [
   {
    "step": "在检测阀温度阈值输入100",
    "result": "输入成功"
   },
   {
    "step": "点击保存",
    "result": "保存成功，显示输入值100"
   }
  ],
  "test_data": {
   "检测阀温度阈值": "100℃"
  },
  "remarks": "关联需求 REQ-S53-05"
 },
 {
  "case_number": "TC-S53-TEMP-004",
  "name": "检测阀温度-空值保存",
  "module": "设置-设备配置",
  "case_type": "functional",
  "priority": "high",
  "preconditions": [
   "用户已登录设置页面"
  ],
  "test_case_steps": [
   {
    "step": "不填写检测阀温度",
    "result": "字段为空"
   },
   {
    "step": "点击保存",
    "result": "保存成功（无默认值，允许为空）"
   }
  ],
  "test_data": {
   "检测阀温度": "空值"
  },
  "remarks": "关联需求 REQ-S53-05，基于假设：无默认值，允许为空"
 },
 {
  "case_number": "TC-S53-TEMP-005",
  "name": "检测阀温度-极端值输入",
  "module": "设置-设备配置",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": [
   "用户已登录设置页面"
  ],
  "test_case_steps": [
   {
    "step": "在检测阀温度输入9999",
    "result": "输入成功"
   },
   {
    "step": "点击保存",
    "result": "保存成功"
   },
   {
    "step": "在检测阀温度输入-100",
    "result": "输入成功"
   },
   {
    "step": "点击保存",
    "result": "保存成功"
   }
  ],
  "test_data": {
   "输入值1": "9999℃",
   "输入值2": "-100℃"
  },
  "remarks": "关联需求 REQ-S53-05，基于假设：无范围限制"
 },
 {
  "case_number": "TC-S53-LEAK-001",
  "name": "开盖后检漏-弹窗提示",
  "module": "检测-吸附管模式",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": [
   "设备处于待机状态",
   "上次开盖后未进行检漏"
  ],
  "test_case_steps": [
   {
    "step": "打开设备上盖",
    "result": "开盖成功"
   },
   {
    "step": "查看系统提示",
    "result": "弹出'上次开盖后未进行设备检漏，是否开始检漏？'对话框"
   }
  ],
  "test_data": {},
  "remarks": "关联需求 REQ-S53-06"
 },
 {
  "case_number": "TC-S53-LEAK-002",
  "name": "开盖后检漏-选择忽略",
  "module": "检测-吸附管模式",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": [
   "已弹出检漏提示对话框"
  ],
  "test_case_steps": [
   {
    "step": "弹出检漏提示",
    "result": "对话框显示"
   },
   {
    "step": "点击'忽略'",
    "result": "对话框关闭，不执行检漏，进入正常操作流程"
   }
  ],
  "test_data": {},
  "remarks": "关联需求 REQ-S53-06"
 },
 {
  "case_number": "TC-S53-LEAK-003",
  "name": "开盖后检漏-选择开始检漏",
  "module": "检测-吸附管模式",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": [
   "已弹出检漏提示对话框"
  ],
  "test_case_steps": [
   {
    "step": "弹出检漏提示",
    "result": "对话框显示"
   },
   {
    "step": "点击'开始检漏'",
    "result": "系统执行检漏流程"
   }
  ],
  "test_data": {},
  "remarks": "关联需求 REQ-S53-06"
 },
 {
  "case_number": "TC-S53-LEAK-004",
  "name": "下位机开盖-系统自动识别检漏",
  "module": "检测-吸附管模式",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": [
   "下位机处于待机状态"
  ],
  "test_case_steps": [
   {
    "step": "下位机开盖",
    "result": "开盖成功"
   },
   {
    "step": "查看系统响应",
    "result": "系统自动识别开盖状态并进行检漏"
   }
  ],
  "test_data": {},
  "remarks": "关联需求 REQ-S53-06"
 },
 {
  "case_number": "TC-S53-LEAK-005",
  "name": "吸附管模式-进度百分比调整",
  "module": "检测-吸附管模式",
  "case_type": "functional",
  "priority": "high",
  "preconditions": [
   "设备配置已设置整体时间",
   "家新已提供升温、检漏预估时间"
  ],
  "test_case_steps": [
   {
    "step": "进入吸附管模式执行检测",
    "result": "检测开始执行"
   },
   {
    "step": "查看任务进度",
    "result": "进度百分比按设备配置读取整体时间计算，含升温、检漏预估时间"
   }
  ],
  "test_data": {},
  "remarks": "关联需求 REQ-S53-06"
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 28. ws-PR-1-test_cases_module_05_multi

- 来源：`workspace/testcase/PR-1/test_cases_module_05_multi.jsonl`　分组：PR-1　用例数：8

```json
[
 {
  "name": "同端后登录者顶掉先登录者",
  "case_number": "TC-PR1-MULTI-001",
  "module": "多端登录策略",
  "case_type": "functional",
  "preconditions": "手机A(iOS)已登录账号13812345678，手机B(Android)可用",
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "手机B使用同一账号登录",
    "result": "手机B登录成功，进入主页"
   },
   {
    "step": "观察手机A状态",
    "result": "手机A被强制登出，跳转登录页"
   }
  ],
  "test_data": {
   "设备A": "手机iOS 13812345678",
   "设备B": "手机Android",
   "策略": "同端互踢"
  },
  "remarks": "FP-012 需求FR-05 默认假设5(按设备类型判定同端)"
 },
 {
  "name": "被踢端收到已在其他设备登录提示",
  "case_number": "TC-PR1-MULTI-002",
  "module": "多端登录策略",
  "case_type": "functional",
  "preconditions": "手机A已登录，手机B准备同端登录同一账号",
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "手机B同端登录后观察手机A界面提示",
    "result": "手机A弹出提示\"您的账号已在其他设备登录\""
   },
   {
    "step": "手机A点击提示确认",
    "result": "跳转至登录页"
   }
  ],
  "test_data": {
   "提示文案": "您的账号已在其他设备登录"
  },
  "remarks": "FP-012 需求FR-05"
 },
 {
  "name": "被踢端token立即失效",
  "case_number": "TC-PR1-MULTI-003",
  "module": "多端登录策略",
  "case_type": "security",
  "preconditions": "手机A已登录并抓包获取其token",
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "手机B同端登录同一账号触发互踢",
    "result": "手机A被踢下线"
   },
   {
    "step": "用手机A的旧token调用受保护接口",
    "result": "返回401，被踢端token已失效"
   }
  ],
  "test_data": {
   "被踢端token": "手机A抓包获取",
   "受保护接口": "/api/v1/orders",
   "预期状态码": "401"
  },
  "remarks": "FP-012 安全 需求FR-05"
 },
 {
  "name": "手机网页平板三种异端同时在线互不影响",
  "case_number": "TC-PR1-MULTI-004",
  "module": "多端登录策略",
  "case_type": "functional",
  "preconditions": "账号13812345678已登录手机端",
  "priority": "medium",
  "test_case_steps": [
   {
    "step": "网页端、平板端分别登录同一账号",
    "result": "三端均登录成功，无任何一端被踢"
   },
   {
    "step": "在手机端刷新用户信息后检查网页端",
    "result": "网页端数据正常同步，会话保持"
   },
   {
    "step": "三端同时调用受保护接口",
    "result": "均返回200，互不干扰"
   }
  ],
  "test_data": {
   "端1": "手机",
   "端2": "网页",
   "端3": "平板",
   "策略": "异端共存"
  },
  "remarks": "FP-013 需求FR-05"
 },
 {
  "name": "设置页展示最近10台登录设备",
  "case_number": "TC-PR1-MULTI-005",
  "module": "多端登录策略",
  "case_type": "functional",
  "preconditions": "账号已在多台设备登录过(含Web/iOS/Android)",
  "priority": "medium",
  "test_case_steps": [
   {
    "step": "进入设置页\"登录设备管理\"",
    "result": "展示设备列表，最多展示最近10台设备"
   },
   {
    "step": "统计列表数量",
    "result": "列表条数≤10，按最近登录时间倒序排列"
   }
  ],
  "test_data": {
   "登录设备数": "≥10",
   "展示上限": "10台"
  },
  "remarks": "FP-014 需求FR-05"
 },
 {
  "name": "设备列表字段含设备名地点时间",
  "case_number": "TC-PR1-MULTI-006",
  "module": "多端登录策略",
  "case_type": "functional",
  "preconditions": "账号已有历史登录设备记录",
  "priority": "medium",
  "test_case_steps": [
   {
    "step": "打开设备管理列表",
    "result": "每台设备展示：设备名(如iPhone 15)、登录地点(如北京市)、登录时间(格式YYYY-MM-DD HH:mm)"
   },
   {
    "step": "核对最新一条设备信息",
    "result": "与本次登录实际设备名、IP归属地、时间一致"
   }
  ],
  "test_data": {
   "设备名字段": "iPhone 15",
   "地点字段": "北京市",
   "时间字段": "YYYY-MM-DD HH:mm"
  },
  "remarks": "FP-014 需求FR-05"
 },
 {
  "name": "单设备踢出后该设备token失效",
  "case_number": "TC-PR1-MULTI-007",
  "module": "多端登录策略",
  "case_type": "functional",
  "preconditions": "同一账号已在手机B登录且被展示在设备列表",
  "priority": "high",
  "test_case_steps": [
   {
    "step": "在设备管理列表对手机B执行\"踢出\"操作",
    "result": "操作成功，手机B从在线设备列表移除"
   },
   {
    "step": "在手机B上尝试访问受保护接口",
    "result": "返回401，手机B被强制登出"
   }
  ],
  "test_data": {
   "被踢设备": "手机B",
   "预期状态码": "401"
  },
  "remarks": "FP-014 需求FR-05"
 },
 {
  "name": "设备数超过10台仅展示最近10台",
  "case_number": "TC-PR1-MULTI-008",
  "module": "多端登录策略",
  "case_type": "functional",
  "preconditions": "账号历史登录设备数≥11台(可通过多次不同设备登录构造)",
  "priority": "low",
  "test_case_steps": [
   {
    "step": "构造账号在11台不同设备上登录",
    "result": "11台设备均有登录记录"
   },
   {
    "step": "打开设备管理列表",
    "result": "仅展示最近10台设备，最早登录的设备不展示"
   }
  ],
  "test_data": {
   "设备总数": 11,
   "展示数": "10台"
  },
  "remarks": "FP-014 边界值 需求FR-05"
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 29. ws-test_cases_isolate

- 来源：`workspace/testcase/test_cases_isolate.jsonl`　分组：(root)　用例数：8

```json
[
 {
  "case_number": "TC-PR-ISOLATE-001",
  "name": "不同用户间的任务完全隔离——用户A创建的任务用户B不可见",
  "module": "METRIX呼析云·数据隔离",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "1. 系统已部署并正常运行，用户管理功能正常<br>2. 预先准备两个普通用户账号：用户A（zhangsan/123456，研发部）和用户B（lisi/123456，研发部）<br>3. 两个用户均未拥有任何管理员权限<br>4. 系统任务列表初始状态为空",
  "test_data": {
   "userA": {
    "username": "zhangsan",
    "displayName": "张三",
    "role": "普通用户",
    "department": "研发部"
   },
   "userB": {
    "username": "lisi",
    "displayName": "李四",
    "role": "普通用户",
    "department": "研发部"
   },
   "tasksCreatedByA": [
    {
     "taskName": "Q1数据分析报告",
     "taskId": "TASK-2025-001",
     "taskType": "数据分析",
     "createdAt": "2025-01-15 10:00:00"
    },
    {
     "taskName": "客户流失预测模型训练",
     "taskId": "TASK-2025-002",
     "taskType": "模型训练",
     "createdAt": "2025-01-15 10:30:00"
    },
    {
     "taskName": "月度销售数据看板",
     "taskId": "TASK-2025-003",
     "taskType": "数据看板",
     "createdAt": "2025-01-15 11:00:00"
    }
   ]
  },
  "test_case_steps": [
   {
    "step": "1. 用户A（zhangsan）登录系统，进入「任务管理」页面",
    "result": "页面正常加载，任务列表显示为空（无任何任务）"
   },
   {
    "step": "2. 用户A依次创建3个任务：「Q1数据分析报告」「客户流失预测模型训练」「月度销售数据看板」，填写必要的任务参数后点击保存",
    "result": "3个任务均创建成功，每个任务保存后页面提示「创建成功」，用户A的任务列表显示3条刚刚创建的任务记录"
   },
   {
    "step": "3. 用户A退出登录，清除浏览器本地缓存和Session",
    "result": "用户A成功退出，页面跳转至登录页"
   },
   {
    "step": "4. 用户B（lisi）使用自己的账号登录系统，进入「任务管理」页面",
    "result": "用户B成功登录，任务列表显示为空（0条任务），看不到用户A创建的任何任务"
   },
   {
    "step": "5. 用户B在任务列表页点击「刷新」按钮或按F5刷新页面",
    "result": "任务列表仍为空，确认无用户A的任务出现在用户B的视野中"
   },
   {
    "step": "6. 用户B在搜索框中输入用户A创建的任务名称「Q1数据分析报告」进行搜索",
    "result": "搜索结果为空，提示「未找到匹配的任务」"
   }
  ],
  "remarks": "关联需求 FP-016：数据隔离-任务级隔离"
 },
 {
  "case_number": "TC-PR-ISOLATE-002",
  "name": "多个普通用户间任务列表严格隔离——每位用户只能看到自己创建的任务",
  "module": "METRIX呼析云·数据隔离",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "1. 系统已部署且用户管理功能正常<br>2. 预先准备3个普通用户账号：用户A（zhangsan/123456）、用户B（lisi/123456）、用户C（wangwu/123456）<br>3. 各用户均无管理员权限<br>4. 确认系统中不存在任何共享任务或公共任务文件夹",
  "test_data": {
   "users": [
    "zhangsan",
    "lisi",
    "wangwu"
   ],
   "tasks": {
    "zhangsan": [
     {
      "taskName": "数据清洗任务",
      "taskId": "TASK-2025-004",
      "taskType": "数据处理"
     },
     {
      "taskName": "ETL流水线配置",
      "taskId": "TASK-2025-005",
      "taskType": "数据集成"
     }
    ],
    "lisi": [
     {
      "taskName": "数据标注任务",
      "taskId": "TASK-2025-006",
      "taskType": "数据标注"
     },
     {
      "taskName": "训练数据集划分",
      "taskId": "TASK-2025-007",
      "taskType": "数据预处理"
     }
    ],
    "wangwu": [
     {
      "taskName": "模型评估报告",
      "taskId": "TASK-2025-008",
      "taskType": "模型评估"
     },
     {
      "taskName": "A/B测试结果分析",
      "taskId": "TASK-2025-009",
      "taskType": "数据分析"
     }
    ]
   }
  },
  "test_case_steps": [
   {
    "step": "1. 用户A（zhangsan）登录→创建任务「数据清洗任务」和「ETL流水线配置」→退出登录",
    "result": "2个任务创建成功，用户A任务列表显示2条记录"
   },
   {
    "step": "2. 用户B（lisi）登录→创建任务「数据标注任务」和「训练数据集划分」→退出登录",
    "result": "2个任务创建成功，用户B任务列表显示2条记录，且不包含用户A的任一任务"
   },
   {
    "step": "3. 用户C（wangwu）登录→创建任务「模型评估报告」和「A/B测试结果分析」→退出登录",
    "result": "2个任务创建成功，用户C任务列表显示2条记录，且不包含用户A和用户B的任务"
   },
   {
    "step": "4. 用户A再次登录系统，查看任务列表",
    "result": "用户A任务列表严格显示为自己创建的2个任务（数据清洗任务、ETL流水线配置），不包含用户B和用户C的任务"
   },
   {
    "step": "5. 在用户A的页面上，分别验证任务总数、任务名称、任务ID均与用户B、用户C的任务无交集",
    "result": "用户A的任务ID为TASK-2025-004和TASK-2025-005，与用户B（TASK-2025-006、007）和用户C（TASK-2025-008、009）完全不同，确认为独立数据集"
   },
   {
    "step": "6. 用户B再次登录，重复步骤5的验证",
    "result": "用户B的任务列表严格显示为自己创建的2个任务，总数、ID、名称均与其他用户无交集"
   }
  ],
  "remarks": "关联需求 FP-016：数据隔离-任务级隔离"
 },
 {
  "case_number": "TC-PR-ISOLATE-003",
  "name": "管理员创建的任务对普通用户完全不可见——权限级隔离",
  "module": "METRIX呼析云·数据隔离",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "1. 系统已部署且用户角色权限管理功能正常<br>2. 预先准备管理员账号（admin_li/admin123）和普通用户账号（zhaoliu/123456）<br>3. 普通用户zhaoliu未被授予任何管理员角色或任务管理权限<br>4. 系统中不存在公共任务池或共享任务默认可见的配置",
  "test_data": {
   "admin": {
    "username": "admin_li",
    "displayName": "管理员·李",
    "role": "系统管理员",
    "permissions": [
     "task:create",
     "task:assign",
     "task:view_all"
    ]
   },
   "regularUser": {
    "username": "zhaoliu",
    "displayName": "赵六",
    "role": "普通用户",
    "permissions": [
     "task:view_own"
    ]
   },
   "adminTasks": [
    {
     "taskName": "全局系统监控告警配置",
     "taskId": "TASK-ADMIN-001",
     "taskType": "系统配置",
     "visibility": "admin_only"
    },
    {
     "taskName": "全员数据安全审计",
     "taskId": "TASK-ADMIN-002",
     "taskType": "审计",
     "visibility": "admin_only"
    },
    {
     "taskName": "平台性能基准测试",
     "taskId": "TASK-ADMIN-003",
     "taskType": "运维",
     "visibility": "admin_only"
    }
   ]
  },
  "test_case_steps": [
   {
    "step": "1. 管理员（admin_li）登录系统，进入「任务管理」页面",
    "result": "管理员成功登录，任务管理页面正常展示"
   },
   {
    "step": "2. 管理员依次创建3个管理级任务：「全局系统监控告警配置」「全员数据安全审计」「平台性能基准测试」",
    "result": "3个任务均创建成功，管理员的任务列表显示3条任务记录"
   },
   {
    "step": "3. 管理员退出登录，清除Session",
    "result": "管理员安全退出，跳转至登录页"
   },
   {
    "step": "4. 普通用户（zhaoliu）使用自己的账号登录系统，进入「任务管理」页面",
    "result": "普通用户成功登录，任务列表显示为空（0条任务）"
   },
   {
    "step": "5. 普通用户在搜索框中分别输入管理员创建的3个任务名称进行精确搜索",
    "result": "每次搜索均返回空结果，提示「未找到匹配的任务」"
   },
   {
    "step": "6. 普通用户尝试通过浏览器地址栏直接访问管理员任务的详情URL（如 /tasks/TASK-ADMIN-001）",
    "result": "页面返回403 Forbidden 或重定向至任务列表页，无法查看任务详情"
   }
  ],
  "remarks": "关联需求 FP-017：数据隔离-权限级隔离"
 },
 {
  "case_number": "TC-PR-ISOLATE-004",
  "name": "管理员将任务分配给普通用户后——该用户可见，其他用户仍不可见",
  "module": "METRIX呼析云·数据隔离",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "1. 系统已部署且任务分配功能正常<br>2. 管理员账号（admin_li/admin123）<br>3. 两个普通用户账号：用户A（zhangsan/123456）和用户B（lisi/123456）<br>4. 管理员已创建任务「用户行为分析任务」（TASK-ADMIN-004），初始未分配给任何人",
  "test_data": {
   "admin": {
    "username": "admin_li",
    "role": "系统管理员"
   },
   "userA": {
    "username": "zhangsan",
    "displayName": "张三",
    "role": "普通用户"
   },
   "userB": {
    "username": "lisi",
    "displayName": "李四",
    "role": "普通用户"
   },
   "task": {
    "taskName": "用户行为分析任务",
    "taskId": "TASK-ADMIN-004",
    "taskType": "数据分析",
    "assignedTo": "",
    "assignedAt": "",
    "status": "待分配",
    "description": "分析Q1用户行为数据，输出用户画像报告"
   }
  },
  "test_case_steps": [
   {
    "step": "1. 管理员登录系统，查看任务「用户行为分析任务」（TASK-ADMIN-004）的详情页",
    "result": "任务详情页正常展示，当前「负责人」字段为空，状态为「待分配」"
   },
   {
    "step": "2. 管理员操作任务分配：在负责人字段选择用户A（zhangsan），点击「保存分配」",
    "result": "系统提示「分配成功」，任务负责人更新为zhangsan，任务状态自动变为「进行中」"
   },
   {
    "step": "3. 管理员退出登录，用户A（zhangsan）登录系统，进入任务列表",
    "result": "用户A的任务列表中出现了1条新任务「用户行为分析任务」（TASK-ADMIN-004），之前为空的任务列表现在显示为1条"
   },
   {
    "step": "4. 用户A点击该任务进入详情页",
    "result": "任务详情页正常展示，显示负责人为zhangsan，任务描述、参数等完整可见"
   },
   {
    "step": "5. 用户A退出登录，用户B（lisi）登录系统，进入任务列表",
    "result": "用户B的任务列表仍为空（0条），看不到被分配给用户A的任务"
   },
   {
    "step": "6. 用户B尝试搜索「用户行为分析任务」",
    "result": "搜索结果为空，用户B无法感知该任务的存在"
   }
  ],
  "remarks": "关联需求 FP-017：数据隔离-权限级隔离"
 },
 {
  "case_number": "TC-PR-ISOLATE-005",
  "name": "跨角色任务范围隔离——管理员可见全部任务，普通用户仅见自己的任务",
  "module": "METRIX呼析云·数据隔离",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "1. 系统已部署且角色权限模型已配置<br>2. 管理员账号（admin_li/admin123）<br>3. 两个分属不同部门的普通用户：研发部zhangsan和财务部sunqi<br>4. 各部门用户各自拥有自己创建的任务",
  "test_data": {
   "admin": {
    "username": "admin_li",
    "role": "系统管理员"
   },
   "userRD": {
    "username": "zhangsan",
    "displayName": "张三",
    "role": "普通用户",
    "department": "研发部"
   },
   "userFin": {
    "username": "sunqi",
    "displayName": "孙七",
    "role": "普通用户",
    "department": "财务部"
   },
   "tasks": {
    "admin": [
     {
      "taskName": "全平台数据质量巡检",
      "taskId": "TASK-ADMIN-005",
      "taskType": "运维巡检"
     }
    ],
    "zhangsan": [
     {
      "taskName": "研发部代码覆盖率分析",
      "taskId": "TASK-2025-010",
      "taskType": "研发分析"
     },
     {
      "taskName": "模型训练GPU资源监控",
      "taskId": "TASK-2025-011",
      "taskType": "资源监控"
     }
    ],
    "sunqi": [
     {
      "taskName": "财务部季度预算分析",
      "taskId": "TASK-2025-012",
      "taskType": "财务分析"
     },
     {
      "taskName": "部门成本分摊报表",
      "taskId": "TASK-2025-013",
      "taskType": "报表生成"
     }
    ]
   }
  },
  "test_case_steps": [
   {
    "step": "1. 先由3个账号分别在自己的会话中创建各自的任务：管理员创建1条，zhangsan创建2条，sunqi创建2条",
    "result": "各账号任务分别创建成功，各自的任务列表仅显示自己创建的任务"
   },
   {
    "step": "2. 管理员登录系统，进入任务列表，记录任务总数和每条任务的创建者",
    "result": "管理员的任务列表显示全部5条任务（管理员的1条 + zhangsan的2条 + sunqi的2条），每个任务旁标注了创建者信息"
   },
   {
    "step": "3. 管理员点击任意一条普通用户创建的任务（如「研发部代码覆盖率分析」），查看详情",
    "result": "管理员可以正常查看该任务的完整详情信息"
   },
   {
    "step": "4. 管理员退出登录，研发部用户zhangsan登录系统",
    "result": "zhangsan的任务列表仅显示2条自己创建的任务（研发部代码覆盖率分析、模型训练GPU资源监控），看不到管理员的任务和sunqi的任务"
   },
   {
    "step": "5. 财务部用户sunqi登录系统",
    "result": "sunqi的任务列表仅显示2条自己创建的任务（财务部季度预算分析、部门成本分摊报表），看不到管理员和zhangsan的任务"
   },
   {
    "step": "6. 分别以zhangsan和sunqi的身份尝试搜索系统中存在的其他用户任务名称",
    "result": "zhangsan搜索「预算」「报表」返回空；sunqi搜索「代码」「GPU」返回空；确认跨角色完全隔离"
   }
  ],
  "remarks": "关联需求 FP-016 + FP-017：数据隔离-任务级隔离 + 权限级隔离"
 },
 {
  "case_number": "TC-PR-ISOLATE-006",
  "name": "跨用户搜索隔离——搜索功能按用户维度过滤，不返回其他用户的任务",
  "module": "METRIX呼析云·数据隔离",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "1. 系统已部署且搜索功能正常<br>2. 用户A（zhangsan）已创建任务「数据采集任务」（TASK-2025-014）<br>3. 用户B（lisi）已创建任务「数据处理任务」（TASK-2025-015）和「数据可视化任务」（TASK-2025-016）<br>4. 两个任务名称均包含关键词「数据」",
  "test_data": {
   "userA": {
    "username": "zhangsan",
    "role": "普通用户"
   },
   "userB": {
    "username": "lisi",
    "role": "普通用户"
   },
   "searchScenarios": [
    {
     "searchKeyword": "数据",
     "description": "通用关键词搜索",
     "expectedForUserA": 1,
     "expectedForUserB": 2
    },
    {
     "searchKeyword": "数据处理",
     "description": "精确匹配用户B的任务名",
     "expectedForUserA": 0,
     "expectedForUserB": 1
    },
    {
     "searchKeyword": "采集",
     "description": "仅用户A的任务包含该词",
     "expectedForUserA": 1,
     "expectedForUserB": 0
    },
    {
     "searchKeyword": "TASK-2025-015",
     "description": "按任务ID搜索——用户B的任务ID",
     "expectedForUserA": 0,
     "expectedForUserB": 1
    }
   ]
  },
  "test_case_steps": [
   {
    "step": "1. 用户A（zhangsan）登录系统，在搜索框中输入关键词「数据」并执行搜索",
    "result": "搜索结果中仅返回1条任务「数据采集任务」（TASK-2025-014），不包括用户B的「数据处理任务」和「数据可视化任务」"
   },
   {
    "step": "2. 用户A分别搜索「数据处理」「采集」「TASK-2025-015」",
    "result": "搜索「数据处理」→ 0条结果；搜索「采集」→ 1条结果（数据采集任务）；搜索「TASK-2025-015」→ 0条结果（看不到用户B的任务ID）"
   },
   {
    "step": "3. 用户A退出，用户B（lisi）登录，搜索关键词「数据」",
    "result": "搜索结果返回2条任务：「数据处理任务」和「数据可视化任务」，不包括用户A的「数据采集任务」"
   },
   {
    "step": "4. 用户B分别搜索「数据处理」「采集」「TASK-2025-015」",
    "result": "搜索「数据处理」→ 1条结果（数据处理任务）；搜索「采集」→ 0条结果；搜索「TASK-2025-015」→ 1条结果（自己的任务）"
   },
   {
    "step": "5. 用户B搜索「TASK-2025-014」（用户A的任务ID）",
    "result": "搜索结果为空，确认无法通过任务ID越权搜索到其他用户的任务"
   }
  ],
  "remarks": "关联需求 FP-016：数据隔离-任务级隔离——搜索过滤"
 },
 {
  "case_number": "TC-PR-ISOLATE-007",
  "name": "直接URL访问隔离——用户无法通过URL直接访问其他用户的任务详情",
  "module": "METRIX呼析云·数据隔离",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "1. 系统已部署且URL路由权限校验功能正常<br>2. 用户A（zhangsan）已创建涉密任务「涉密数据分析报告」（TASK-2025-017）<br>3. 用户B（lisi）为另一个独立普通用户<br>4. 用户B已知用户A的任务详情页URL路径",
  "test_data": {
   "userA": {
    "username": "zhangsan",
    "role": "普通用户",
    "department": "研发部"
   },
   "userB": {
    "username": "lisi",
    "role": "普通用户",
    "department": "研发部"
   },
   "targetTask": {
    "taskName": "涉密数据分析报告",
    "taskId": "TASK-2025-017",
    "taskType": "数据分析",
    "sensitiveLevel": "L2-内部",
    "detailUrl": "/tasks/TASK-2025-017",
    "apiUrl": "/api/v1/tasks/TASK-2025-017"
   },
   "attackVectors": [
    {
     "method": "浏览器地址栏直接访问详情页",
     "url": "/tasks/TASK-2025-017"
    },
    {
     "method": "直接调用任务详情API",
     "url": "/api/v1/tasks/TASK-2025-017"
    },
    {
     "method": "尝试通过任务编辑接口访问",
     "url": "/api/v1/tasks/TASK-2025-017/edit"
    }
   ]
  },
  "test_case_steps": [
   {
    "step": "1. 用户A（zhangsan）登录→创建任务「涉密数据分析报告」→记录任务详情页URL",
    "result": "任务创建成功，URL为 /tasks/TASK-2025-017，用户A可正常访问该详情页"
   },
   {
    "step": "2. 用户A退出登录，清除所有浏览器缓存和Session，关闭标签页",
    "result": "用户A登出成功，浏览器Session已清除"
   },
   {
    "step": "3. 用户B（lisi）登录系统，在浏览器地址栏直接输入用户A的任务详情页URL /tasks/TASK-2025-017 并回车",
    "result": "页面返回403 Forbidden 错误，或被重定向至用户B自己的任务列表页，无法看到任何任务详情内容"
   },
   {
    "step": "4. 用户B打开浏览器开发者工具，在Console中通过Fetch/Ajax直接调用任务详情API：GET /api/v1/tasks/TASK-2025-017",
    "result": "API返回HTTP 403状态码，响应体包含错误信息如「{\"code\":403,\"message\":\"无权访问该任务\"}」，不返回任何任务数据"
   },
   {
    "step": "5. 用户B尝试通过任务编辑接口 POST /api/v1/tasks/TASK-2025-017/edit 提交编辑请求",
    "result": "API返回HTTP 403或401状态码，编辑请求被拒绝，无法修改其他用户的任务"
   },
   {
    "step": "6. 用户B在浏览器的无痕/隐私模式下重复步骤3",
    "result": "同样返回403或被重定向，确认无绕过方式可访问其他用户的任务详情"
   }
  ],
  "remarks": "关联需求 FP-016：数据隔离-任务级隔离——URL级安全防护"
 },
 {
  "case_number": "TC-PR-ISOLATE-008",
  "name": "管理员批量分配任务后——仅被分配的用户可见，其余用户隔离",
  "module": "METRIX呼析云·数据隔离",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "1. 系统已部署且批量任务分配功能正常<br>2. 管理员账号（admin_li/admin123）<br>3. 三个普通用户：用户A（zhangsan）、用户B（lisi）、用户C（wangwu）<br>4. 管理员已创建任务「跨部门协作分析任务」（TASK-ADMIN-006）",
  "test_data": {
   "admin": {
    "username": "admin_li",
    "role": "系统管理员"
   },
   "userA": {
    "username": "zhangsan",
    "displayName": "张三",
    "role": "普通用户"
   },
   "userB": {
    "username": "lisi",
    "displayName": "李四",
    "role": "普通用户"
   },
   "userC": {
    "username": "wangwu",
    "displayName": "王五",
    "role": "普通用户"
   },
   "task": {
    "taskName": "跨部门协作分析任务",
    "taskId": "TASK-ADMIN-006",
    "taskType": "协作任务",
    "assignedUsers": [],
    "description": "分析各部门数据，输出跨部门协作报告"
   }
  },
  "test_case_steps": [
   {
    "step": "1. 管理员登录系统，进入任务「跨部门协作分析任务」（TASK-ADMIN-006）的分配管理页",
    "result": "任务详情页正常展示，当前「负责人」和「协作者」字段均为空"
   },
   {
    "step": "2. 管理员在批量分配界面，勾选用户A（zhangsan）作为负责人，用户B（lisi）作为协作者，点击「批量保存」",
    "result": "系统提示「批量分配成功」，任务负责人为zhangsan，协作者包含lisi"
   },
   {
    "step": "3. 管理员退出登录，用户A（zhangsan）登录，查看任务列表",
    "result": "用户A的任务列表显示1条新任务「跨部门协作分析任务」，可查看完整详情并可执行编辑操作"
   },
   {
    "step": "4. 用户A退出，用户B（lisi）登录，查看任务列表",
    "result": "用户B的任务列表显示1条新任务「跨部门协作分析任务」，可查看详情但编辑按钮置灰或隐藏（协作者权限）"
   },
   {
    "step": "5. 用户B退出，用户C（wangwu）登录，查看任务列表",
    "result": "用户C的任务列表为空（0条任务），看不到该任务"
   },
   {
    "step": "6. 用户C搜索「跨部门协作」或任务ID「TASK-ADMIN-006」",
    "result": "搜索结果为空，用户C完全无法感知该任务的存在"
   },
   {
    "step": "7. 管理员重新登录，将用户C也添加为协作者并保存",
    "result": "分配成功，任务协作者列表更新为[zhangsan, lisi, wangwu]"
   },
   {
    "step": "8. 用户C再次登录，刷新任务列表",
    "result": "用户C的任务列表现在显示1条任务「跨部门协作分析任务」，确认分配后可见性生效"
   }
  ],
  "remarks": "关联需求 FP-017：数据隔离-权限级隔离——分配即可见"
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 30. ws-PR-1-test_cases_module_03_add

- 来源：`workspace/testcase/PR-1/test_cases_module_03_add.jsonl`　分组：PR-1　用例数：5

```json
[
 {
  "name": "新增地点-填写全部字段成功保存",
  "case_number": "TC-PR1-ADD-001",
  "module": "新增地点",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "用户拥有管理或操作权限",
  "test_case_steps": [
   {
    "step": "进入地点管理页面，点击新增按钮",
    "result": "新增弹窗打开"
   },
   {
    "step": "输入地点名称：广州中山医院采样点",
    "result": "输入正常显示"
   },
   {
    "step": "选择地点类型：采样点",
    "result": "选项选中"
   },
   {
    "step": "输入地点位置：广州市越秀区中山二路58号",
    "result": "输入正常显示"
   },
   {
    "step": "点击保存按钮",
    "result": "保存成功，弹窗关闭；列表刷新出现新记录；地点ID自动生成；名称/类型/位置与输入一致"
   }
  ],
  "test_data": {
   "地点名称": "广州中山医院采样点",
   "地点类型": "采样点",
   "地点位置": "广州市越秀区中山二路58号"
  },
  "remarks": "REQ-变更①+② FP-004",
  "description": "验证填写全部字段新增地点成功保存"
 },
 {
  "name": "新增地点-地点类型未选择时保存失败",
  "case_number": "TC-PR1-ADD-002",
  "module": "新增地点",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "用户拥有管理或操作权限",
  "test_case_steps": [
   {
    "step": "进入地点管理页面，点击新增按钮",
    "result": "新增弹窗打开"
   },
   {
    "step": "输入地点名称：测试采样点",
    "result": "输入正常显示"
   },
   {
    "step": "地点类型保持未选择状态",
    "result": "类型为空"
   },
   {
    "step": "输入地点位置：测试位置",
    "result": "输入正常显示"
   },
   {
    "step": "点击保存按钮",
    "result": "保存失败；提示错误信息：请选择地点类型；弹窗不关闭"
   }
  ],
  "test_data": {
   "地点名称": "测试采样点",
   "地点类型": "未选择",
   "地点位置": "测试位置"
  },
  "remarks": "REQ-变更② FP-004",
  "description": "验证地点类型为必填项，未选择时保存失败"
 },
 {
  "name": "新增地点-地点名称边界值验证",
  "case_number": "TC-PR1-ADD-003",
  "module": "新增地点",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "用户拥有管理或操作权限",
  "test_case_steps": [
   {
    "step": "新增地点，地点名称输入50个字符（边界值max）",
    "result": "可正常输入，保存成功"
   },
   {
    "step": "新增地点，地点名称输入51个字符（max+1）",
    "result": "输入被截断或提示超出最大长度限制，保存被阻止"
   },
   {
    "step": "新增地点，地点名称输入1个字符（min）",
    "result": "保存成功"
   },
   {
    "step": "新增地点，地点名称留空",
    "result": "保存失败，提示请填写地点名称"
   }
  ],
  "test_data": {
   "名称50字符": "a×50",
   "名称51字符": "a×51",
   "名称1字符": "a",
   "名称空": ""
  },
  "remarks": "REQ-变更① FP-004 [假设]名称≤50字符",
  "description": "验证地点名称字段的边界值（min=1/max=50/空值）"
 },
 {
  "name": "新增地点-地点名称含SQL注入字符被处理",
  "case_number": "TC-PR1-ADD-004",
  "module": "新增地点",
  "case_type": "security",
  "priority": "high",
  "preconditions": "用户拥有管理或操作权限",
  "test_case_steps": [
   {
    "step": "新增地点，地点名称输入：'; DROP TABLE location;--",
    "result": "输入被原样保存或按转义处理，不执行任何SQL指令"
   },
   {
    "step": "保存成功后检查数据库",
    "result": "数据库中记录名称完整存储该字符串，无任何表被删除，系统无异常"
   }
  ],
  "test_data": {
   "地点名称": "'; DROP TABLE location;--",
   "地点类型": "采样点",
   "地点位置": "测试位置"
  },
  "remarks": "REQ-变更① FP-004 安全红线-注入",
  "description": "验证地点名称字段SQL注入防护"
 },
 {
  "name": "新增地点-地点位置边界值验证",
  "case_number": "TC-PR1-ADD-005",
  "module": "新增地点",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "用户拥有管理或操作权限",
  "test_case_steps": [
   {
    "step": "新增地点，地点位置输入100个字符",
    "result": "保存成功，位置完整展示"
   },
   {
    "step": "新增地点，地点位置输入101个字符",
    "result": "输入被截断或提示超出最大长度限制"
   },
   {
    "step": "新增地点，地点位置留空",
    "result": "保存成功，位置显示为空（假设位置非必填）"
   }
  ],
  "test_data": {
   "位置100字符": "a×100",
   "位置101字符": "a×101",
   "位置空": ""
  },
  "remarks": "REQ-变更① FP-004 [假设]位置≤100字符可空",
  "description": "验证地点位置字段边界值（max=100/空值）"
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 31. ws-PR-2-pq_cases_v3

- 来源：`workspace/testcase/PR-2/pq_cases_v3.jsonl`　分组：PR-2　用例数：16

```json
[
 {
  "case_number": "TC-PR2-PQ-001",
  "module": "配气模板",
  "case_type": "functional",
  "priority": "critical",
  "name": "创建配气模板-填写全部必填字段成功创建",
  "preconditions": "用户已登录，具有配气模板创建权限，配气模板列表页面已打开，当前系统中无同名的配气模板",
  "test_data": {
   "template_name": "标准氮氧混合模板",
   "original_concentration": "99.99",
   "target_concentration": "20.5",
   "flow_rate": "5.0",
   "planned_volume": "1000"
  },
  "test_case_steps": [
   {
    "step": "1. 点击「创建配气模板」按钮",
    "result": "弹出创建配气模板表单弹窗，包含模板名称、原始浓度、目标气浓度、流速、计划采气量、气体类型等输入字段"
   },
   {
    "step": "2. 填写所有必填字段：模板名称=标准氮氧混合模板，原始浓度=99.99，目标气浓度=20.5，流速=5.0，计划采气量=1000",
    "result": "所有输入框均正常显示输入内容"
   },
   {
    "step": "3. 点击「保存」按钮",
    "result": "页面提示「创建成功」，弹窗关闭，列表中出现名称为「标准氮氧混合模板」的新记录"
   }
  ],
  "remarks": "FP-004 创建配气模板正向流程"
 },
 {
  "case_number": "TC-PR2-PQ-002",
  "module": "配气模板",
  "case_type": "functional",
  "priority": "critical",
  "name": "创建配气模板-模板名称唯一性校验",
  "preconditions": "系统中已存在名称为「标准氮氧混合模板」的配气模板记录",
  "test_data": {
   "template_name": "标准氮氧混合模板",
   "original_concentration": "99.5",
   "target_concentration": "21.0",
   "flow_rate": "3.0",
   "planned_volume": "500"
  },
  "test_case_steps": [
   {
    "step": "1. 点击创建配气模板按钮，输入模板名称=标准氮氧混合模板（与已有模板同名）",
    "result": "输入框正常显示名称"
   },
   {
    "step": "2. 填写其他必填字段为合法数据",
    "result": "各字段均可正常输入"
   },
   {
    "step": "3. 点击「保存」",
    "result": "页面显示错误提示「模板名称已存在，请使用其他名称」，表单未关闭，数据库中未新增记录"
   }
  ],
  "remarks": "FP-004 创建配气模板名称唯一性"
 },
 {
  "case_number": "TC-PR2-PQ-003",
  "module": "配气模板",
  "case_type": "functional",
  "priority": "critical",
  "name": "创建配气模板-保存并继续创建行为",
  "preconditions": "系统中无名为「氧气校准模板」的模板",
  "test_data": {
   "template_name": "氧气校准模板",
   "original_concentration": "99.99",
   "target_concentration": "30.0",
   "flow_rate": "2.5",
   "planned_volume": "800",
   "gas_type": "氧气"
  },
  "test_case_steps": [
   {
    "step": "1. 填写所有字段：模板名称=氧气校准模板，原始浓度=99.99，目标气浓度=30.0，流速=2.5，计划采气量=800，气体类型=氧气",
    "result": "所有输入框正确显示"
   },
   {
    "step": "2. 点击「保存并继续创建」",
    "result": "页面提示「创建成功」，模板名称输入框被清空，其余字段（原始浓度、目标气浓度、流速、计划采气量、气体类型）保留"
   },
   {
    "step": "3. 在模板名称输入框输入新名称「氧气校准模板v2」，再次点击保存并继续",
    "result": "模板名称再次被清空，其余字段仍保留"
   }
  ],
  "remarks": "FP-004 创建配气模板保存并继续"
 },
 {
  "case_number": "TC-PR2-PQ-004",
  "module": "配气模板",
  "case_type": "functional",
  "priority": "critical",
  "name": "创建配气模板-数值字段非法字符拦截",
  "preconditions": "创建表单已打开，模板名称已填入合法值「校验模板」",
  "test_data": {
   "template_name": "校验模板",
   "original_concentration": "abc",
   "target_concentration": "-5",
   "flow_rate": "@#$",
   "planned_volume": "1.2.3"
  },
  "test_case_steps": [
   {
    "step": "1. 在原始浓度输入框输入非数字字符「abc」",
    "result": "输入框拒绝输入或出现错误提示「请输入有效数字」"
   },
   {
    "step": "2. 在目标气浓度输入框输入负号数字「-5」",
    "result": "输入框拒绝负号或提示错误"
   },
   {
    "step": "3. 在流速输入框输入特殊字符「@#$」",
    "result": "输入框拒绝特殊字符或提示错误"
   },
   {
    "step": "4. 在计划采气量输入框输入多小数点数字「1.2.3」",
    "result": "输入框拒绝或提示错误"
   },
   {
    "step": "5. 点击「保存」",
    "result": "表单校验失败，保存未执行，错误字段高亮提示"
   }
  ],
  "remarks": "FP-004 创建配气模板数值字段校验"
 },
 {
  "case_number": "TC-PR2-PQ-005",
  "module": "配气模板",
  "case_type": "functional",
  "priority": "medium",
  "name": "创建配气模板-模板名称50字符边界值",
  "preconditions": "创建表单已打开",
  "test_data": {
   "template_name_50": "ABCDEFGHIJABCDEFGHIJABCDEFGHIJABCDEFGHIJABCDEFGHIJ"
  },
  "test_case_steps": [
   {
    "step": "1. 输入恰好50个字符的名称",
    "result": "输入框正常显示50字符，无截断"
   },
   {
    "step": "2. 尝试输入第51个字符",
    "result": "输入框拒绝第51个字符，仍然为50字符"
   },
   {
    "step": "3. 清空名称后点击保存",
    "result": "提示「模板名称不能为空」"
   },
   {
    "step": "4. 输入1个字符的名称后保存",
    "result": "创建成功"
   }
  ],
  "remarks": "FP-004 创建配气模板名称长度边界"
 },
 {
  "case_number": "TC-PR2-PQ-006",
  "module": "配气模板",
  "case_type": "functional",
  "priority": "medium",
  "name": "创建配气模板-数值字段10字符边界及气体类型非必填",
  "preconditions": "创建表单已打开，模板名称已填入「边界测试模板」",
  "test_data": {
   "original_concentration": "1234567890",
   "target_concentration": "0.00000001",
   "flow_rate": "999.99999",
   "planned_volume": "1000000000"
  },
  "test_case_steps": [
   {
    "step": "1. 在原始浓度输入框输入10位数字1234567890",
    "result": "正常显示，无截断"
   },
   {
    "step": "2. 尝试输入第11位",
    "result": "拒绝或截断"
   },
   {
    "step": "3. 清空气体类型，点击保存",
    "result": "创建成功，数据库中gas_type为null"
   }
  ],
  "remarks": "FP-004 创建配气模板数值边界"
 },
 {
  "case_number": "TC-PR2-PQ-007",
  "module": "配气模板",
  "case_type": "functional",
  "priority": "high",
  "name": "编辑配气模板-修改所有字段保存",
  "preconditions": "系统中存在名为「原始模板」的记录，不存在名为「编辑后模板」的记录",
  "test_data": {
   "template_name": "编辑后模板",
   "original_concentration": "95.5",
   "target_concentration": "25.0",
   "flow_rate": "4.5",
   "planned_volume": "600",
   "gas_type": "氮氧混合气"
  },
  "test_case_steps": [
   {
    "step": "1. 在列表中点击「原始模板」的编辑按钮",
    "result": "弹出编辑弹窗，所有字段预填当前值"
   },
   {
    "step": "2. 修改所有字段后点击保存",
    "result": "页面提示编辑成功，列表刷新，记录名称变为「编辑后模板」，数据库记录更新"
   }
  ],
  "remarks": "FP-005 编辑配气模板正向流程"
 },
 {
  "case_number": "TC-PR2-PQ-008",
  "module": "配气模板",
  "case_type": "functional",
  "priority": "medium",
  "name": "编辑配气模板-数值字段非法字符拦截",
  "preconditions": "编辑弹窗已打开",
  "test_data": {
   "original_concentration": "九十九",
   "target_concentration": "20.A",
   "flow_rate": "五",
   "planned_volume": ""
  },
  "test_case_steps": [
   {
    "step": "1. 将原始浓度改为中文「九十九」",
    "result": "拒绝中文或提示错误"
   },
   {
    "step": "2. 将目标气浓度改为含字母「20.A」",
    "result": "拒绝或提示错误"
   },
   {
    "step": "3. 清空计划采气量",
    "result": "提示必填"
   },
   {
    "step": "4. 点击保存",
    "result": "校验失败，保存未执行"
   }
  ],
  "remarks": "FP-005 编辑配气模板校验同创建"
 },
 {
  "case_number": "TC-PR2-PQ-009",
  "module": "配气模板",
  "case_type": "functional",
  "priority": "medium",
  "name": "编辑配气模板-名称已存在",
  "preconditions": "系统中存在模板A和模板B",
  "test_data": {
   "template_name": "模板B"
  },
  "test_case_steps": [
   {
    "step": "1. 编辑模板A，将其名称改为模板B",
    "result": "输入框显示模板B"
   },
   {
    "step": "2. 点击保存",
    "result": "提示模板名称已存在，保存未执行"
   }
  ],
  "remarks": "FP-005 编辑配气模板名称唯一性"
 },
 {
  "case_number": "TC-PR2-PQ-010",
  "module": "配气模板",
  "case_type": "functional",
  "priority": "high",
  "name": "导出配气模板-JSON格式文件名正确",
  "preconditions": "系统中存在名为「氮气校准模板」的模板",
  "test_data": {
   "template_name": "氮气校准模板",
   "export_format": "json"
  },
  "test_case_steps": [
   {
    "step": "1. 在模板列表中点击「氮气校准模板」的导出按钮",
    "result": "触发文件下载"
   },
   {
    "step": "2. 检查下载文件的文件名和扩展名",
    "result": "文件名为「氮气校准模板.json」"
   },
   {
    "step": "3. 打开文件检查内容是否为合法JSON",
    "result": "文件内容为合法JSON格式"
   },
   {
    "step": "4. 核对JSON字段值与系统数据",
    "result": "字段值template_name=氮气校准模板，其他字段与系统保存数据一致"
   }
  ],
  "remarks": "FP-006 导出配气模板"
 },
 {
  "case_number": "TC-PR2-PQ-011",
  "module": "配气模板",
  "case_type": "functional",
  "priority": "high",
  "name": "导入配气模板-合法JSON导入成功",
  "preconditions": "系统中不存在名为「导入模板」的记录，已准备合法JSON文件",
  "test_data": {
   "template_name": "导入模板",
   "original_concentration": "88.88",
   "target_concentration": "15.0",
   "flow_rate": "2.0",
   "planned_volume": "400",
   "gas_type": "合成空气"
  },
  "test_case_steps": [
   {
    "step": "1. 点击导入按钮，选择合法JSON文件",
    "result": "弹出文件选择对话框"
   },
   {
    "step": "2. 确认上传",
    "result": "提示导入成功，列表中出现新记录，数据库验证数据一致"
   }
  ],
  "remarks": "FP-006 导入配气模板正向"
 },
 {
  "case_number": "TC-PR2-PQ-012",
  "module": "配气模板",
  "case_type": "functional",
  "priority": "high",
  "name": "导入配气模板-字段不完整JSON拦截",
  "preconditions": "已准备缺少必填字段的JSON文件",
  "test_data": {
   "template_name": "残缺模板",
   "missing_fields": "target_concentration, flow_rate, planned_volume"
  },
  "test_case_steps": [
   {
    "step": "1. 导入缺少字段的JSON",
    "result": "提示导入失败，缺少必填字段，系统未新增记录"
   },
   {
    "step": "2. 导入空对象JSON",
    "result": "提示导入失败"
   },
   {
    "step": "3. 导入字段名不匹配的JSON",
    "result": "提示导入失败"
   }
  ],
  "remarks": "FP-006 导入配气模板字段完整性"
 },
 {
  "case_number": "TC-PR2-PQ-013",
  "module": "配气模板",
  "case_type": "functional",
  "priority": "medium",
  "name": "导入配气模板-安全防护校验",
  "preconditions": "已准备包含恶意内容的JSON文件",
  "test_data": {
   "xss_payload": "<script>alert('xss')</script>",
   "sql_payload": "1' OR '1'='1"
  },
  "test_case_steps": [
   {
    "step": "1. 导入包含XSS脚本的JSON",
    "result": "若导入成功，模板名称被HTML转义显示，不会执行脚本"
   },
   {
    "step": "2. 导入包含SQL注入内容的JSON",
    "result": "不会导致SQL注入攻击成功"
   },
   {
    "step": "3. 导入非JSON格式文件",
    "result": "提示仅支持JSON格式"
   }
  ],
  "remarks": "FP-006 导入配气模板安全防护"
 },
 {
  "case_number": "TC-PR2-PQ-014",
  "module": "配气模板",
  "case_type": "functional",
  "priority": "low",
  "name": "模板列表管理-分页每页10条",
  "preconditions": "系统中存在603条配气模板记录",
  "test_data": {
   "total_records": 603,
   "page_size": 10,
   "expected_pages": 61
  },
  "test_case_steps": [
   {
    "step": "1. 打开配气模板列表",
    "result": "显示共603条，默认第1页10条"
   },
   {
    "step": "2. 点击第2页",
    "result": "显示第2页10条，与第1页不重复"
   },
   {
    "step": "3. 点击最后一页",
    "result": "显示3条记录"
   }
  ],
  "remarks": "FP-007 模板列表分页"
 },
 {
  "case_number": "TC-PR2-PQ-015",
  "module": "配气模板",
  "case_type": "functional",
  "priority": "low",
  "name": "模板列表管理-编辑按钮操作",
  "preconditions": "列表中存在多条记录",
  "test_data": {
   "target_record": "任意配气模板",
   "edit_action": "编辑按钮"
  },
  "test_case_steps": [
   {
    "step": "1. 点击记录的编辑按钮",
    "result": "弹出编辑弹窗，字段预填"
   },
   {
    "step": "2. 修改模板名称后保存",
    "result": "列表刷新，数据更新"
   },
   {
    "step": "3. 翻页后关闭编辑弹窗不保存",
    "result": "列表位置不变，数据未变"
   }
  ],
  "remarks": "FP-007 模板列表编辑操作"
 },
 {
  "case_number": "TC-PR2-PQ-016",
  "module": "配气模板",
  "case_type": "functional",
  "priority": "low",
  "name": "模板列表管理-跨页编辑一致性",
  "preconditions": "系统中存在603条记录",
  "test_data": {
   "page_1_count": 10,
   "page_3_count": 10,
   "total_pages": 61
  },
  "test_case_steps": [
   {
    "step": "1. 记录第1页最后一条为T1，第3页第5条为T2",
    "result": "T1和T2的记录信息已获取"
   },
   {
    "step": "2. 编辑T1并保存",
    "result": "T1名称更新"
   },
   {
    "step": "3. 翻到第3页检查T2",
    "result": "T2不受影响"
   }
  ],
  "remarks": "FP-007 模板列表跨页一致性"
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 32. ws-test_cases_compare

- 来源：`workspace/testcase/test_cases_compare.jsonl`　分组：(root)　用例数：12

```json
[
 {
  "case_number": "TC-PR-COMPARE-001",
  "name": "两个样品结果对比——验证物质种类和浓度差异正确展示",
  "module": "METRIX环评云·结果对比",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "1. 环评云系统已登录，具备结果对比权限；2. 项目A下存在样品S-001和样品S-002，均已完成检测并发布结果；3. S-001含物质[PM2.5:35μg/m³, PM10:75μg/m³, SO2:50μg/m³, NO2:40μg/m³]；4. S-002含物质[PM2.5:52μg/m³, PM10:120μg/m³, SO2:30μg/m³, NO2:60μg/m³, CO:4mg/m³]",
  "test_data": {
   "sample1": {
    "id": "S-001",
    "project": "A",
    "substances": {
     "PM2.5": "35μg/m³",
     "PM10": "75μg/m³",
     "SO2": "50μg/m³",
     "NO2": "40μg/m³"
    }
   },
   "sample2": {
    "id": "S-002",
    "project": "A",
    "substances": {
     "PM2.5": "52μg/m³",
     "PM10": "120μg/m³",
     "SO2": "30μg/m³",
     "NO2": "60μg/m³",
     "CO": "4mg/m³"
    }
   },
   "expected_differences": {
    "substance_diff": {
     "S-001独有": [],
     "S-002独有": [
      "CO:4mg/m³"
     ],
     "共有物质": [
      "PM2.5",
      "PM10",
      "SO2",
      "NO2"
     ]
    },
    "concentration_diffs": {
     "PM2.5": {
      "S-001": "35",
      "S-002": "52",
      "差值": "-17μg/m³"
     },
     "PM10": {
      "S-001": "75",
      "S-002": "120",
      "差值": "-45μg/m³"
     },
     "SO2": {
      "S-001": "50",
      "S-002": "30",
      "差值": "+20μg/m³"
     },
     "NO2": {
      "S-001": "40",
      "S-002": "60",
      "差值": "-20μg/m³"
     }
    }
   }
  },
  "remarks": "关联需求 FP-019",
  "test_case_steps": [
   {
    "step": "1. 进入「结果对比」功能页面，选择项目A",
    "result": "页面加载正常，项目A的样品列表展示完整"
   },
   {
    "step": "2. 勾选样品S-001和S-002，点击「开始对比」",
    "result": "对比视图正确加载，展示两个样品的对比表格"
   },
   {
    "step": "3. 查看物质种类列：S-001显示4种物质，S-002显示5种物质（含CO）",
    "result": "S-002独有的CO以高亮/提示方式标出，清晰显示S-002比S-001多出CO物质"
   },
   {
    "step": "4. 查看共有物质PM2.5、PM10、SO2、NO2的浓度值",
    "result": "浓度值按样品分列展示，每个物质两行数据准确对应S-001和S-002的检测值"
   },
   {
    "step": "5. 核对浓度差值（系统自动计算）",
    "result": "PM2.5差值-17μg/m³、PM10差值-45μg/m³、SO2差值+20μg/m³、NO2差值-20μg/m³，计算正确，增减方向标识清晰"
   }
  ]
 },
 {
  "case_number": "TC-PR-COMPARE-002",
  "name": "三个及以上样品同时对比",
  "module": "METRIX环评云·结果对比",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "1. 环评云系统已登录，具备结果对比权限；2. 同一项目下存在样品S-003、S-004、S-005，检测结果均已发布；3. 三个样品均含PM2.5、PM10、SO2、NO2物质",
  "test_data": {
   "samples": [
    {
     "id": "S-003",
     "substances": {
      "PM2.5": "30μg/m³",
      "PM10": "65μg/m³",
      "SO2": "45μg/m³",
      "NO2": "35μg/m³"
     }
    },
    {
     "id": "S-004",
     "substances": {
      "PM2.5": "48μg/m³",
      "PM10": "95μg/m³",
      "SO2": "55μg/m³",
      "NO2": "42μg/m³"
     }
    },
    {
     "id": "S-005",
     "substances": {
      "PM2.5": "22μg/m³",
      "PM10": "50μg/m³",
      "SO2": "38μg/m³",
      "NO2": "28μg/m³"
     }
    }
   ],
   "expected_min_max": {
    "PM2.5": {
     "min": "S-005:22μg/m³",
     "max": "S-004:48μg/m³"
    },
    "PM10": {
     "min": "S-005:50μg/m³",
     "max": "S-004:95μg/m³"
    },
    "SO2": {
     "min": "S-005:38μg/m³",
     "max": "S-004:55μg/m³"
    },
    "NO2": {
     "min": "S-005:28μg/m³",
     "max": "S-004:42μg/m³"
    }
   }
  },
  "remarks": "关联需求 FP-019",
  "test_case_steps": [
   {
    "step": "1. 进入结果对比功能，选择项目下样品S-003、S-004、S-005（至少3个）",
    "result": "三个样品均可正常勾选，无上限拦截"
   },
   {
    "step": "2. 点击「开始对比」",
    "result": "对比表格正确渲染，表头列依次为物质名称|S-003|S-004|S-005，布局清晰不重叠"
   },
   {
    "step": "3. 查看PM2.5各行数据",
    "result": "S-003:30、S-004:48、S-005:22，三值均正确展示，最低值S-005和最高值S-004有视觉标记（如颜色/图标）"
   },
   {
    "step": "4. 逐一核对PM10、SO2、NO2各行",
    "result": "每个物质行三个样品的浓度值均正确对应，无错位或串行"
   },
   {
    "step": "5. 横向滚动/调整列宽验证",
    "result": "三个样品列支持横向滚动查看，列宽可自适应调整，数据不截断"
   }
  ]
 },
 {
  "case_number": "TC-PR-COMPARE-003",
  "name": "结果完全相同的样品对比——正确显示无差异",
  "module": "METRIX环评云·结果对比",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "1. 环评云系统已登录，具备结果对比权限；2. 存在两个样品S-010和S-011，所有检测物质及浓度值完全相同",
  "test_data": {
   "sampleA": {
    "id": "S-010",
    "substances": {
     "PM2.5": "25μg/m³",
     "PM10": "55μg/m³",
     "SO2": "40μg/m³",
     "NO2": "30μg/m³",
     "CO": "2mg/m³"
    }
   },
   "sampleB": {
    "id": "S-011",
    "substances": {
     "PM2.5": "25μg/m³",
     "PM10": "55μg/m³",
     "SO2": "40μg/m³",
     "NO2": "30μg/m³",
     "CO": "2mg/m³"
    }
   }
  },
  "remarks": "关联需求 FP-019",
  "test_case_steps": [
   {
    "step": "1. 选择样品S-010和S-011（检测结果完全一致），点击「开始对比」",
    "result": "对比表格正常加载，展示5种物质的浓度数据"
   },
   {
    "step": "2. 查看页面中各物质行的浓度差值/差异标记",
    "result": "所有5种物质的浓度差值均为0（或显示「无差异」），无任何高亮差异标记"
   },
   {
    "step": "3. 查看页面顶部是否存在差异统计汇总",
    "result": "差异汇总显示「共0项差异」或「结果完全一致」的提示"
   },
   {
    "step": "4. 检查页面是否仍完整呈现对比表格而非空白页",
    "result": "对比表格完整渲染，两个样品各列数据均可见，无UI异常"
   }
  ]
 },
 {
  "case_number": "TC-PR-COMPARE-004",
  "name": "跨项目/跨日期的样品结果对比",
  "module": "METRIX环评云·结果对比",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "1. 环评云系统已登录；2. 项目A下有样品S-020（检测日期2024-06-15），项目B下有样品S-021（检测日期2024-09-20）；3. 两个样品均含PM2.5、PM10、SO2、NO2、CO、O3六种物质",
  "test_data": {
   "sample_cross_project": {
    "S-020": {
     "project": "A",
     "date": "2024-06-15",
     "location": "厂界东",
     "substances": {
      "PM2.5": "40μg/m³",
      "PM10": "85μg/m³",
      "SO2": "55μg/m³",
      "NO2": "45μg/m³",
      "CO": "3mg/m³",
      "O3": "100μg/m³"
     }
    },
    "S-021": {
     "project": "B",
     "date": "2024-09-20",
     "location": "厂界西",
     "substances": {
      "PM2.5": "35μg/m³",
      "PM10": "70μg/m³",
      "SO2": "48μg/m³",
      "NO2": "38μg/m³",
      "CO": "2.5mg/m³",
      "O3": "120μg/m³"
     }
    }
   }
  },
  "remarks": "关联需求 FP-019",
  "test_case_steps": [
   {
    "step": "1. 进入结果对比，分别从项目A选择S-020、从项目B选择S-021（跨项目选择）",
    "result": "支持跨项目勾选样品，两个样品均被添加至对比列表"
   },
   {
    "step": "2. 点击「开始对比」",
    "result": "对比表格正常加载，样品头部显示所属项目名称和检测日期等元信息"
   },
   {
    "step": "3. 查看表格中6种物质的浓度对比",
    "result": "PM2.5、PM10、SO2、NO2、CO、O3的浓度数据分列展示，项目归属和日期标注清晰"
   },
   {
    "step": "4. 核对跨项目样品的差值计算",
    "result": "各项差值计算正确（如PM2.5差值-5μg/m³、O3差值+20μg/m³等），无因跨项目导致的计算错误"
   }
  ]
 },
 {
  "case_number": "TC-PR-COMPARE-005",
  "name": "对比维度验证——物质种类排序正确性",
  "module": "METRIX环评云·结果对比",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "1. 环评云系统已登录；2. 选择两个样品S-030和S-031，含多种类型物质：PM2.5、Pb(铅)、苯并[a]芘、SO2、NO2、CO、O3、TSP、氟化物、Hg(汞)，物质名称含中英文、希腊字母及下标符号",
  "test_data": {
   "samples": {
    "S-030": {
     "substances": {
      "TSP": "150μg/m³",
      "PM2.5": "35μg/m³",
      "SO2": "50μg/m³",
      "NO2": "40μg/m³",
      "CO": "3mg/m³",
      "O3": "110μg/m³",
      "Pb": "0.5μg/m³",
      "氟化物": "0.7μg/m³",
      "苯并[a]芘": "0.001μg/m³",
      "Hg": "0.05μg/m³"
     }
    },
    "S-031": {
     "substances": {
      "TSP": "180μg/m³",
      "PM2.5": "42μg/m³",
      "SO2": "45μg/m³",
      "NO2": "50μg/m³",
      "CO": "4mg/m³",
      "O3": "95μg/m³",
      "Pb": "0.8μg/m³",
      "氟化物": "1.2μg/m³",
      "苯并[a]芘": "0.002μg/m³",
      "Hg": "0.08μg/m³"
     }
    }
   }
  },
  "remarks": "关联需求 FP-019",
  "test_case_steps": [
   {
    "step": "1. 选择S-030和S-031，进入对比视图",
    "result": "10种物质全部在对比表格中列出"
   },
   {
    "step": "2. 检查物质名称的排序规则",
    "result": "物质按系统预设规则排序（如按首字母拼音/物质类别分类排序），而非随机或按添加顺序排列"
   },
   {
    "step": "3. 检查含特殊字符的物质名称（Pb、苯并[a]芘、Hg）的显示",
    "result": "元素符号Pb/Hg正确显示，苯并[a]芘中的方括号和希腊字母下标正确渲染无乱码"
   },
   {
    "step": "4. 对比两行排序结果的一致性",
    "result": "多次对比操作下物质排序保持一致，不因样品选择顺序变化"
   },
   {
    "step": "5. 验证排序是否可按列头交互调整（如按浓度排序）",
    "result": "支持点击列头按浓度值升序/降序排列，排序功能正常无数据错乱"
   }
  ]
 },
 {
  "case_number": "TC-PR-COMPARE-006",
  "name": "对比维度验证——浓度数值精度准确性",
  "module": "METRIX环评云·结果对比",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "1. 环评云系统已登录；2. 选择两个样品S-040（含极低浓度物质）和S-041（含高精度小数物质），检测结果已发布",
  "test_data": {
   "sample_precision": {
    "S-040": {
     "substances": {
      "Pb": "0.001μg/m³",
      "Hg": "0.0005μg/m³",
      "苯并[a]芘": "0.0001μg/m³",
      "二噁英": "0.0000001μg/m³",
      "PM2.5": "15μg/m³"
     }
    },
    "S-041": {
     "substances": {
      "Pb": "0.003μg/m³",
      "Hg": "0.0012μg/m³",
      "苯并[a]芘": "0.0003μg/m³",
      "二噁英": "0.0000003μg/m³",
      "PM2.5": "18μg/m³"
     }
    },
    "expected_diff": {
     "Pb": "0.002μg/m³",
     "Hg": "0.0007μg/m³",
     "苯并[a]芘": "0.0002μg/m³",
     "二噁英": "0.0000002μg/m³",
     "PM2.5": "3μg/m³"
    }
   }
  },
  "remarks": "关联需求 FP-019",
  "test_case_steps": [
   {
    "step": "1. 选择S-040和S-041，进入对比视图",
    "result": "5种物质的对比表格正常加载"
   },
   {
    "step": "2. 核对极小浓度值的显示精度",
    "result": "Pb:0.001/0.003、Hg:0.0005/0.0012、苯并[a]芘:0.0001/0.0003、二噁英:0.0000001/0.0000003均保留原始有效位数，无四舍五入精度丢失"
   },
   {
    "step": "3. 核对系统计算的差值精度",
    "result": "Pb差值0.002、Hg差值0.0007、苯并[a]芘差值0.0002、二噁英差值0.0000002，差值保留与原始数据匹配的有效位数"
   },
   {
    "step": "4. 验证科学计数法数值的显示效果",
    "result": "极小浓度值（如二噁英）可读性良好，支持科学计数法或适当精度格式展示"
   }
  ]
 },
 {
  "case_number": "TC-PR-COMPARE-007",
  "name": "历史对比数据交叉引用",
  "module": "METRIX环评云·结果对比",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "1. 环评云系统已登录；2. 用户曾对样品S-050和S-051执行过结果对比操作并保存了对比记录；3. 再次对S-050和S-051的数据进行了更新（重新检测后发布）",
  "test_data": {
   "historical_compare": {
    "previous": {
     "compare_id": "CMP-20240601",
     "date": "2024-06-01",
     "S-050": {
      "PM2.5": "30μg/m³",
      "SO2": "40μg/m³"
     },
     "S-051": {
      "PM2.5": "45μg/m³",
      "SO2": "55μg/m³"
     }
    },
    "current": {
     "compare_id": "CMP-20240901",
     "date": "2024-09-01",
     "S-050": {
      "PM2.5": "28μg/m³",
      "SO2": "35μg/m³"
     },
     "S-051": {
      "PM2.5": "42μg/m³",
      "SO2": "50μg/m³"
     }
    }
   }
  },
  "remarks": "关联需求 FP-019",
  "test_case_steps": [
   {
    "step": "1. 进入结果对比页面，查看历史对比记录列表",
    "result": "历史对比记录CMP-20240601、CMP-20240901均展示在列表中，含日期和样品信息"
   },
   {
    "step": "2. 点击CMP-20240601查看历史对比详情",
    "result": "正确展示2024-06-01的对比结果：S-050 PM2.5:30、SO2:40；S-051 PM2.5:45、SO2:55"
   },
   {
    "step": "3. 返回列表，点击CMP-20240901查看最新对比",
    "result": "正确展示2024-09-01的对比结果：S-050 PM2.5:28、SO2:35；S-051 PM2.5:42、SO2:50"
   },
   {
    "step": "4. 使用「并排对比」或「趋势对比」功能查看两个时间点的差异变化",
    "result": "系统支持并排或叠加展示历史与当前对比数据，清晰呈现S-050和S-051的浓度变化趋势"
   },
   {
    "step": "5. 验证历史数据与当前数据独立存储不混淆",
    "result": "修改当前样品数据不影响历史对比记录的数据完整性"
   }
  ]
 },
 {
  "case_number": "TC-PR-COMPARE-008",
  "name": "结果对比报告导出",
  "module": "METRIX环评云·结果对比",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "1. 环评云系统已登录；2. 已完成样品S-060和S-061的对比操作，对比结果页面展示正常；3. 系统支持导出为Excel/PDF格式",
  "test_data": {
   "samples_export": {
    "S-060": {
     "project": "C",
     "date": "2024-08-10",
     "substances": {
      "PM2.5": "38μg/m³",
      "PM10": "82μg/m³",
      "SO2": "48μg/m³",
      "NO2": "44μg/m³"
     }
    },
    "S-061": {
     "project": "C",
     "date": "2024-08-11",
     "substances": {
      "PM2.5": "45μg/m³",
      "PM10": "100μg/m³",
      "SO2": "52μg/m³",
      "NO2": "50μg/m³"
     }
    }
   }
  },
  "remarks": "关联需求 FP-019",
  "test_case_steps": [
   {
    "step": "1. 完成S-060与S-061的对比后，点击「导出」按钮",
    "result": "弹出导出选项：支持导出格式（Excel/PDF/CSV）"
   },
   {
    "step": "2. 选择导出为Excel格式",
    "result": "浏览器触发文件下载，文件名含样品编号和对比日期信息"
   },
   {
    "step": "3. 打开下载的Excel文件检查内容",
    "result": "Excel中包含：表头（样品编号、项目、日期）、物质列、浓度值列、差值列；数据完整，S-060的38/82/48/44和S-061的45/100/52/50均正确对应；差值计算正确；格式整洁可读"
   },
   {
    "step": "4. 再次对比，选择导出为PDF格式",
    "result": "PDF报告包含对比标题、样品元信息、对比表格和差异汇总，排版工整无水印遮挡"
   },
   {
    "step": "5. 验证导出文件中单位信息完整性",
    "result": "所有浓度值均带标准单位（μg/m³、mg/m³等），导出的单位与页面显示一致"
   }
  ]
 },
 {
  "case_number": "TC-PR-COMPARE-009",
  "name": "边界场景——空样品集对比（零选择）",
  "module": "METRIX环评云·结果对比",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "1. 环评云系统已登录，具备结果对比权限；2. 项目中存在已发布的样品数据",
  "test_data": {
   "no_sample_selected": {
    "selected_count": 0,
    "min_required": 2,
    "ui_message_expected": "请至少选择2个样品进行对比"
   }
  },
  "remarks": "关联需求 FP-019",
  "test_case_steps": [
   {
    "step": "1. 进入结果对比页面，不勾选任何样品",
    "result": "对比按钮呈灰色禁用状态"
   },
   {
    "step": "2. 直接点击灰色「对比」按钮",
    "result": "按钮无响应或弹出提示「请至少选择2个样品进行对比」"
   },
   {
    "step": "3. 仅勾选1个样品，点击「开始对比」",
    "result": "提示「至少需要选择2个样品」，禁止执行对比"
   },
   {
    "step": "4. 尝试通过URL直接构造对比请求（绕过UI校验）",
    "result": "服务端也进行参数校验，返回错误码和提示信息，不执行空数据集对比，无空指针异常"
   }
  ]
 },
 {
  "case_number": "TC-PR-COMPARE-010",
  "name": "边界场景——含离群值的样品对比",
  "module": "METRIX环评云·结果对比",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "1. 环评云系统已登录；2. 样品S-070为正常样品；3. 样品S-071含多个离群值：极高浓度（PM10:980μg/m³远超标准）、极低浓度（Pb:0.0001μg/m³）、零值（NO2:0μg/m³）",
  "test_data": {
   "normal_sample": {
    "S-070": {
     "substances": {
      "PM10": "80μg/m³",
      "NO2": "35μg/m³",
      "Pb": "0.5μg/m³",
      "SO2": "45μg/m³",
      "CO": "2mg/m³"
     }
    }
   },
   "outlier_sample": {
    "S-071": {
     "substances": {
      "PM10": "980μg/m³",
      "NO2": "0μg/m³",
      "Pb": "0.0001μg/m³",
      "SO2": "9999μg/m³",
      "CO": "15mg/m³"
     }
    }
   }
  },
  "remarks": "关联需求 FP-019",
  "test_case_steps": [
   {
    "step": "1. 选择S-070和S-071，进入对比视图",
    "result": "对比表格正常加载，离群值数据完整展示不截断"
   },
   {
    "step": "2. 查看PM10行：正常值80 vs 离群值980",
    "result": "980μg/m³完整显示；系统对超出常规范围的值有视觉标记（如红色/警告图标）"
   },
   {
    "step": "3. 查看NO2行：正常值35 vs 零值0",
    "result": "零值正确显示为0μg/m³，不显示为空白或null"
   },
   {
    "step": "4. 查看Pb行：正常值0.5 vs 极低值0.0001",
    "result": "极小值0.0001正确显示，精度未丢失"
   },
   {
    "step": "5. 查看SO2行：45 vs 9999",
    "result": "超高值9999正常展示，差值计算结果正确（+9954μg/m³），页面无溢出或排版错乱"
   }
  ]
 },
 {
  "case_number": "TC-PR-COMPARE-011",
  "name": "不同单位体系的样品结果对比",
  "module": "METRIX环评云·结果对比",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "1. 环评云系统已登录；2. 样品S-080使用μg/m³单位体系，样品S-081使用mg/m³单位体系；3. 两个样品检测的物质相同（PM2.5、SO2、NO2、CO）",
  "test_data": {
   "unit_conversion": {
    "S-080": {
     "unit_system": "μg/m³",
     "substances": {
      "PM2.5": "35μg/m³",
      "SO2": "50μg/m³",
      "NO2": "40μg/m³",
      "CO": "3000μg/m³"
     }
    },
    "S-081": {
     "unit_system": "mg/m³",
     "substances": {
      "PM2.5": "0.035mg/m³",
      "SO2": "0.05mg/m³",
      "NO2": "0.04mg/m³",
      "CO": "3mg/m³"
     }
    },
    "expected_note": "35μg/m³ = 0.035mg/m³，系统应展示单位统一提示或自动换算"
   }
  },
  "remarks": "关联需求 FP-019",
  "test_case_steps": [
   {
    "step": "1. 选择S-080（μg/m³）和S-081（mg/m³），点击「开始对比」",
    "result": "对比表格加载，系统检测到单位不一致并给出提示/标注"
   },
   {
    "step": "2. 查看PM2.5行的浓度值",
    "result": "S-080显示35（μg/m³），S-081显示0.035（mg/m³），系统在表头或行标注中注明单位"
   },
   {
    "step": "3. 检查是否有单位换算辅助功能",
    "result": "系统支持一键统一单位为某一标准（如统一为μg/m³并自动换算S-081的值），换算后数值正确"
   },
   {
    "step": "4. 检查差值计算是否考虑单位统一",
    "result": "若单位统一后计算差值，差值正确（如统一后PM2.5差值0）；若保持原单位显示则不计算差值并显示单位不兼容提示"
   }
  ]
 },
 {
  "case_number": "TC-PR-COMPARE-012",
  "name": "对比结果可视化展示——柱状图/趋势图",
  "module": "METRIX环评云·结果对比",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "1. 环评云系统已登录；2. 选择3个及以上样品S-090、S-091、S-092进行对比；3. 三个样品均含PM2.5、PM10、SO2三种物质",
  "test_data": {
   "visualization": {
    "samples": [
     {
      "id": "S-090",
      "substances": {
       "PM2.5": "30μg/m³",
       "PM10": "60μg/m³",
       "SO2": "40μg/m³"
      }
     },
     {
      "id": "S-091",
      "substances": {
       "PM2.5": "50μg/m³",
       "PM10": "110μg/m³",
       "SO2": "65μg/m³"
      }
     },
     {
      "id": "S-092",
      "substances": {
       "PM2.5": "20μg/m³",
       "PM10": "45μg/m³",
       "SO2": "35μg/m³"
      }
     }
    ]
   }
  },
  "remarks": "关联需求 FP-019",
  "test_case_steps": [
   {
    "step": "1. 选择S-090、S-091、S-092，进入对比视图",
    "result": "对比表格正常展示三样品的浓度数据"
   },
   {
    "step": "2. 点击「图表视图」或「可视化」切换按钮",
    "result": "页面切换至图表展示模式，默认展示柱状图"
   },
   {
    "step": "3. 查看柱状图中PM2.5的数据展示",
    "result": "三个柱体分别对应S-090(30)、S-091(50)、S-092(20)，柱高比例与数值成正比，图例清晰"
   },
   {
    "step": "4. 切换至折线图/趋势图模式",
    "result": "折线图正确连线三个样品各物质的值，支持按物质筛选显示/隐藏"
   },
   {
    "step": "5. 图表与表格联动验证",
    "result": "在图表中悬停或点击某数据点，提示框显示对应样品和精确数值，与表格数据一致"
   }
  ]
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 33. ws-PR-1-test_cases_supplement

- 来源：`workspace/testcase/PR-1/test_cases_supplement.jsonl`　分组：PR-1　用例数：4

```json
[
 {
  "name": "新增地点-地点名称含emoji字符保存",
  "case_number": "TC-PR1-SUP-001",
  "module": "新增地点",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "用户拥有管理或操作权限",
  "test_case_steps": [
   {
    "step": "进入地点管理页面，点击新增按钮",
    "result": "新增弹窗打开"
   },
   {
    "step": "输入地点名称：广州🏥采样点（含emoji）",
    "result": "输入正常显示，无乱码"
   },
   {
    "step": "选择地点类型：采样点，输入位置：测试位置",
    "result": "选项与输入正常"
   },
   {
    "step": "点击保存按钮",
    "result": "保存成功，弹窗关闭；列表中新记录名称完整展示含emoji字符，无乱码/截断"
   }
  ],
  "test_data": {
   "地点名称": "广州🏥采样点",
   "地点类型": "采样点",
   "地点位置": "测试位置"
  },
  "remarks": "REQ-变更① FP-004 评审补充-异常覆盖多样性",
  "description": "验证地点名称支持emoji字符输入且保存展示正常"
 },
 {
  "name": "新增地点-地点名称仅空格保存失败",
  "case_number": "TC-PR1-SUP-002",
  "module": "新增地点",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "用户拥有管理或操作权限",
  "test_case_steps": [
   {
    "step": "进入地点管理页面，点击新增按钮",
    "result": "新增弹窗打开"
   },
   {
    "step": "输入地点名称：连续5个空格",
    "result": "输入显示为空白"
   },
   {
    "step": "选择地点类型：采样点，输入位置：测试位置",
    "result": "选项与输入正常"
   },
   {
    "step": "点击保存按钮",
    "result": "保存失败，提示请填写地点名称（去除首尾空格后为空判定为未填写）；弹窗不关闭"
   }
  ],
  "test_data": {
   "地点名称": "     （5个空格）",
   "地点类型": "采样点",
   "地点位置": "测试位置"
  },
  "remarks": "REQ-变更① FP-004 评审补充-异常覆盖多样性",
  "description": "验证地点名称仅输入空格时按空值处理并阻止保存"
 },
 {
  "name": "新增地点-地点名称与现有地点重复保存失败",
  "case_number": "TC-PR1-SUP-003",
  "module": "新增地点",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "系统中已存在地点记录，名称：广州中山医院采样点",
  "test_case_steps": [
   {
    "step": "进入地点管理页面，点击新增按钮",
    "result": "新增弹窗打开"
   },
   {
    "step": "输入地点名称：广州中山医院采样点（与现有记录同名）",
    "result": "输入正常显示"
   },
   {
    "step": "选择地点类型：采样点，输入位置：广州市越秀区中山二路58号",
    "result": "选项与输入正常"
   },
   {
    "step": "点击保存按钮",
    "result": "保存失败，提示地点名称已存在，请勿重复创建；弹窗不关闭；未生成重复记录"
   }
  ],
  "test_data": {
   "地点名称": "广州中山医院采样点（与现有记录同名）",
   "地点类型": "采样点",
   "地点位置": "广州市越秀区中山二路58号"
  },
  "remarks": "REQ-变更① FP-004 评审补充-异常覆盖多样性",
  "description": "验证地点名称重复时保存失败且不产生重复数据"
 },
 {
  "name": "新增地点-地点名称含全角字符保存",
  "case_number": "TC-PR1-SUP-004",
  "module": "新增地点",
  "case_type": "functional",
  "priority": "medium",
  "preconditions": "用户拥有管理或操作权限",
  "test_case_steps": [
   {
    "step": "进入地点管理页面，点击新增按钮",
    "result": "新增弹窗打开"
   },
   {
    "step": "输入地点名称：采样点ＡＢＣ１２３（全角字母数字）",
    "result": "输入正常显示"
   },
   {
    "step": "选择地点类型：检测实验室，输入位置：测试位置",
    "result": "选项与输入正常"
   },
   {
    "step": "点击保存按钮",
    "result": "保存成功，弹窗关闭；列表中新记录名称完整展示全角字符，无乱码"
   }
  ],
  "test_data": {
   "地点名称": "采样点ＡＢＣ１２３",
   "地点类型": "检测实验室",
   "地点位置": "测试位置"
  },
  "remarks": "REQ-变更② FP-004 评审补充-异常覆盖多样性",
  "description": "验证地点名称支持全角字符输入且保存展示正常"
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 34. ws-PR-2-pq_cases

- 来源：`workspace/testcase/PR-2/pq_cases.jsonl`　分组：PR-2　用例数：16

```json
[
 {
  "case_number": "TC-PR2-PQ-001",
  "module": "配气模板",
  "case_type": "functional",
  "priority": "high",
  "name": "创建配气模板-填写全部必填字段成功创建",
  "preconditions": "用户已登录，具有配气模板创建权限，配气模板列表页面已打开，当前系统中无同名的配气模板",
  "test_data": {
   "template_name": "标准氮氧混合模板",
   "original_concentration": "99.99",
   "target_concentration": "20.5",
   "flow_rate": "5.0",
   "planned_volume": "1000",
   "gas_type": ""
  },
  "test_case_steps": [
   {
    "step": "1. 点击「创建配气模板」按钮",
    "result": "弹出创建配气模板表单弹窗，包含模板名称、原始浓度、目标气浓度、流速、计划采气量、气体类型等输入字段"
   },
   {
    "step": "2. 填写所有必填字段：模板名称=标准氮氧混合模板，原始浓度=99.99，目标气浓度=20.5，流速=5.0，计划采气量=1000，气体类型留空",
    "result": "所有输入框均正常显示输入内容"
   },
   {
    "step": "3. 点击「保存」按钮",
    "result": "页面提示「创建成功」，弹窗关闭，列表中出现名称为「标准氮氧混合模板」的新记录"
   }
  ],
  "remarks": "FP-004 创建配气模板正向流程"
 },
 {
  "case_number": "TC-PR2-PQ-002",
  "module": "配气模板",
  "case_type": "functional",
  "priority": "high",
  "name": "创建配气模板-模板名称唯一性校验",
  "preconditions": "系统中已存在名称为「标准氮氧混合模板」的配气模板记录，其他字段数据不重复",
  "test_data": {
   "template_name": "标准氮氧混合模板",
   "original_concentration": "99.5",
   "target_concentration": "21.0",
   "flow_rate": "3.0",
   "planned_volume": "500"
  },
  "test_case_steps": [
   {
    "step": "1. 点击创建配气模板按钮，输入模板名称=标准氮氧混合模板（与已有模板同名）",
    "result": "输入框正常显示名称"
   },
   {
    "step": "2. 填写其他必填字段为合法数据",
    "result": "各字段均可正常输入"
   },
   {
    "step": "3. 点击「保存」",
    "result": "页面显示错误提示「模板名称已存在，请使用其他名称」，表单未关闭，数据库中未新增记录"
   }
  ],
  "remarks": "FP-004 创建配气模板名称唯一性"
 },
 {
  "case_number": "TC-PR2-PQ-003",
  "module": "配气模板",
  "case_type": "functional",
  "priority": "critical",
  "name": "创建配气模板-保存并继续创建行为",
  "preconditions": "系统中无名为「氧气校准模板」的模板",
  "test_data": {
   "template_name": "氧气校准模板",
   "original_concentration": "99.99",
   "target_concentration": "30.0",
   "flow_rate": "2.5",
   "planned_volume": "800",
   "gas_type": "氧气"
  },
  "test_case_steps": [
   {
    "step": "1. 填写所有字段：模板名称=氧气校准模板，原始浓度=99.99，目标气浓度=30.0，流速=2.5，计划采气量=800，气体类型=氧气",
    "result": "所有输入框正确显示"
   },
   {
    "step": "2. 点击「保存并继续创建」",
    "result": "页面提示「创建成功」，模板名称输入框被清空，其余字段（原始浓度、目标气浓度、流速、计划采气量、气体类型）保留"
   },
   {
    "step": "3. 在模板名称输入框输入新名称「氧气校准模板v2」，再次点击保存并继续",
    "result": "模板名称再次被清空，其余字段仍保留"
   }
  ],
  "remarks": "FP-004 创建配气模板保存并继续"
 },
 {
  "case_number": "TC-PR2-PQ-004",
  "module": "配气模板",
  "case_type": "functional",
  "priority": "high",
  "name": "创建配气模板-数值字段非法字符拦截",
  "preconditions": "创建表单已打开，模板名称已填入合法值「校验模板」",
  "test_data": {
   "template_name": "校验模板",
   "original_concentration": "abc",
   "target_concentration": "-5",
   "flow_rate": "@#$",
   "planned_volume": "1.2.3"
  },
  "test_case_steps": [
   {
    "step": "1. 在原始浓度输入框输入非数字字符「abc」",
    "result": "输入框拒绝输入或出现错误提示「请输入有效数字」"
   },
   {
    "step": "2. 在目标气浓度输入框输入负号数字「-5」",
    "result": "输入框拒绝负号或提示错误"
   },
   {
    "step": "3. 在流速输入框输入特殊字符「@#$」",
    "result": "输入框拒绝特殊字符或提示错误"
   },
   {
    "step": "4. 在计划采气量输入框输入多小数点数字「1.2.3」",
    "result": "输入框拒绝或提示错误"
   },
   {
    "step": "5. 点击「保存」",
    "result": "表单校验失败，保存未执行，错误字段高亮提示"
   }
  ],
  "remarks": "FP-004 创建配气模板数值字段校验"
 },
 {
  "case_number": "TC-PR2-PQ-005",
  "module": "配气模板",
  "case_type": "functional",
  "priority": "medium",
  "name": "创建配气模板-模板名称50字符边界值",
  "preconditions": "创建表单已打开",
  "test_data": {
   "template_name_50": "ABCDEFGHIJABCDEFGHIJABCDEFGHIJABCDEFGHIJABCDEFGHIJ",
   "template_name_51": "ABCDEFGHIJABCDEFGHIJABCDEFGHIJABCDEFGHIJABCDEFGHIJX",
   "template_name_1": "A"
  },
  "test_case_steps": [
   {
    "step": "1. 输入恰好50个字符的名称",
    "result": "输入框正常显示50字符，无截断"
   },
   {
    "step": "2. 尝试输入第51个字符",
    "result": "输入框拒绝第51个字符，仍然为50字符"
   },
   {
    "step": "3. 清空名称后点击保存",
    "result": "提示「模板名称不能为空」"
   },
   {
    "step": "4. 输入1个字符的名称后保存",
    "result": "创建成功"
   }
  ],
  "remarks": "FP-004 创建配气模板名称长度边界"
 },
 {
  "case_number": "TC-PR2-PQ-006",
  "module": "配气模板",
  "case_type": "functional",
  "priority": "medium",
  "name": "创建配气模板-数值字段10字符边界及气体类型非必填",
  "preconditions": "创建表单已打开，模板名称已填入「边界测试模板」",
  "test_data": {
   "original_concentration": "1234567890",
   "target_concentration": "0.00000001",
   "flow_rate": "999.99999",
   "planned_volume": "1000000000"
  },
  "test_case_steps": [
   {
    "step": "1. 在原始浓度输入框输入10位数字",
    "result": "正常显示，无截断"
   },
   {
    "step": "2. 尝试输入第11位",
    "result": "拒绝或截断"
   },
   {
    "step": "3. 清空气体类型，点击保存",
    "result": "创建成功，数据库中gas_type为null"
   }
  ],
  "remarks": "FP-004 创建配气模板数值边界"
 },
 {
  "case_number": "TC-PR2-PQ-007",
  "module": "配气模板",
  "case_type": "functional",
  "priority": "high",
  "name": "编辑配气模板-修改所有字段保存",
  "preconditions": "系统中存在名为「原始模板」的记录，不存在名为「编辑后模板」的记录",
  "test_data": {
   "template_name": "编辑后模板",
   "original_concentration": "95.5",
   "target_concentration": "25.0",
   "flow_rate": "4.5",
   "planned_volume": "600",
   "gas_type": "氮氧混合气"
  },
  "test_case_steps": [
   {
    "step": "1. 在列表中点击「原始模板」的编辑按钮",
    "result": "弹出编辑弹窗，所有字段预填当前值"
   },
   {
    "step": "2. 修改所有字段后点击保存",
    "result": "页面提示编辑成功，列表刷新，记录名称变为「编辑后模板」，数据库记录更新"
   }
  ],
  "remarks": "FP-005 编辑配气模板正向流程"
 },
 {
  "case_number": "TC-PR2-PQ-008",
  "module": "配气模板",
  "case_type": "functional",
  "priority": "medium",
  "name": "编辑配气模板-数值字段非法字符拦截",
  "preconditions": "编辑弹窗已打开",
  "test_data": {
   "original_concentration": "九十九",
   "target_concentration": "20.A",
   "flow_rate": "五",
   "planned_volume": ""
  },
  "test_case_steps": [
   {
    "step": "1. 将原始浓度改为中文",
    "result": "拒绝中文或提示错误"
   },
   {
    "step": "2. 将目标气浓度改为含字母",
    "result": "拒绝或提示错误"
   },
   {
    "step": "3. 清空计划采气量",
    "result": "提示必填"
   },
   {
    "step": "4. 点击保存",
    "result": "校验失败，保存未执行"
   }
  ],
  "remarks": "FP-005 编辑配气模板校验同创建"
 },
 {
  "case_number": "TC-PR2-PQ-009",
  "module": "配气模板",
  "case_type": "functional",
  "priority": "medium",
  "name": "编辑配气模板-名称已存在",
  "preconditions": "系统中存在模板A和模板B",
  "test_data": {
   "template_name": "模板B"
  },
  "test_case_steps": [
   {
    "step": "1. 编辑模板A，将其名称改为模板B",
    "result": "输入框显示模板B"
   },
   {
    "step": "2. 点击保存",
    "result": "提示模板名称已存在，保存未执行"
   }
  ],
  "remarks": "FP-005 编辑配气模板名称唯一性"
 },
 {
  "case_number": "TC-PR2-PQ-010",
  "module": "配气模板",
  "case_type": "functional",
  "priority": "high",
  "name": "导出配气模板-JSON格式文件名正确",
  "preconditions": "系统中存在名为「氮气校准模板」的模板",
  "test_data": {
   "template_name": "氮气校准模板"
  },
  "test_case_steps": [
   {
    "step": "1. 在模板列表中点击「氮气校准模板」的导出按钮",
    "result": "触发文件下载"
   },
   {
    "step": "2. 检查下载的文件",
    "result": "文件名为「氮气校准模板.json」，文件内容为合法JSON，包含所有字段且与系统数据一致"
   }
  ],
  "remarks": "FP-006 导出配气模板"
 },
 {
  "case_number": "TC-PR2-PQ-011",
  "module": "配气模板",
  "case_type": "functional",
  "priority": "high",
  "name": "导入配气模板-合法JSON导入成功",
  "preconditions": "系统中不存在名为「导入模板」的记录，已准备合法JSON文件",
  "test_data": {
   "template_name": "导入模板",
   "original_concentration": "88.88",
   "target_concentration": "15.0",
   "flow_rate": "2.0",
   "planned_volume": "400",
   "gas_type": "合成空气"
  },
  "test_case_steps": [
   {
    "step": "1. 点击导入按钮，选择合法JSON文件",
    "result": "弹出文件选择对话框"
   },
   {
    "step": "2. 确认上传",
    "result": "提示导入成功，列表中出现新记录，数据库验证数据一致"
   }
  ],
  "remarks": "FP-006 导入配气模板正向"
 },
 {
  "case_number": "TC-PR2-PQ-012",
  "module": "配气模板",
  "case_type": "functional",
  "priority": "high",
  "name": "导入配气模板-字段不完整JSON拦截",
  "preconditions": "已准备缺少必填字段的JSON文件",
  "test_data": {
   "template_name": "残缺模板",
   "original_concentration": "99.99",
   "missing_fields": "target_concentration, flow_rate, planned_volume"
  },
  "test_case_steps": [
   {
    "step": "1. 导入缺少字段的JSON",
    "result": "提示导入失败，缺少必填字段，系统未新增记录"
   },
   {
    "step": "2. 导入空对象JSON",
    "result": "提示导入失败"
   },
   {
    "step": "3. 导入字段名不匹配的JSON",
    "result": "提示导入失败"
   }
  ],
  "remarks": "FP-006 导入配气模板字段完整性"
 },
 {
  "case_number": "TC-PR2-PQ-013",
  "module": "配气模板",
  "case_type": "functional",
  "priority": "medium",
  "name": "导入配气模板-安全防护校验",
  "preconditions": "已准备包含恶意内容的JSON文件",
  "test_data": {
   "xss_payload": "<script>alert('xss')</script>",
   "sql_payload": "1' OR '1'='1"
  },
  "test_case_steps": [
   {
    "step": "1. 导入包含XSS脚本的JSON",
    "result": "若导入成功，模板名称被HTML转义显示，不会执行脚本"
   },
   {
    "step": "2. 导入包含SQL注入内容的JSON",
    "result": "不会导致SQL注入攻击成功"
   },
   {
    "step": "3. 导入非JSON格式文件",
    "result": "提示仅支持JSON格式"
   }
  ],
  "remarks": "FP-006 导入配气模板安全防护"
 },
 {
  "case_number": "TC-PR2-PQ-014",
  "module": "配气模板",
  "case_type": "functional",
  "priority": "low",
  "name": "模板列表管理-分页每页10条",
  "preconditions": "系统中存在603条配气模板记录",
  "test_data": {
   "total_records": 603,
   "page_size": 10,
   "expected_pages": 61
  },
  "test_case_steps": [
   {
    "step": "1. 打开配气模板列表",
    "result": "显示共603条，默认第1页10条"
   },
   {
    "step": "2. 点击第2页",
    "result": "显示第2页10条，与第1页不重复"
   },
   {
    "step": "3. 点击最后一页",
    "result": "显示3条记录"
   }
  ],
  "remarks": "FP-007 模板列表分页"
 },
 {
  "case_number": "TC-PR2-PQ-015",
  "module": "配气模板",
  "case_type": "functional",
  "priority": "low",
  "name": "模板列表管理-编辑按钮操作",
  "preconditions": "列表中存在多条记录",
  "test_data": {},
  "test_case_steps": [
   {
    "step": "1. 点击记录的编辑按钮",
    "result": "弹出编辑弹窗，字段预填"
   },
   {
    "step": "2. 修改后保存",
    "result": "列表刷新，数据更新"
   },
   {
    "step": "3. 翻页后关闭编辑弹窗不保存",
    "result": "列表位置不变，数据未变"
   }
  ],
  "remarks": "FP-007 模板列表编辑操作"
 },
 {
  "case_number": "TC-PR2-PQ-016",
  "module": "配气模板",
  "case_type": "functional",
  "priority": "low",
  "name": "模板列表管理-跨页编辑一致性",
  "preconditions": "系统中存在603条记录",
  "test_data": {},
  "test_case_steps": [
   {
    "step": "1. 记录第1页最后一条为T1，第3页第5条为T2",
    "result": "记录成功"
   },
   {
    "step": "2. 编辑T1并保存",
    "result": "T1名称更新"
   },
   {
    "step": "3. 翻到第3页检查T2",
    "result": "T2不受影响"
   }
  ],
  "remarks": "FP-007 模板列表跨页一致性"
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 35. ws-user_login_test_cases

- 来源：`workspace/testcase/user_login_test_cases.jsonl`　分组：(root)　用例数：24

```json
[
 {
  "name": "正确手机号+正确密码登录成功",
  "case_number": "TC-TEST-PROJECT-LOGIN-001",
  "module": "用户登录",
  "case_type": "functional",
  "preconditions": "已注册测试账号：手机号 13812345678，密码 Test@1234",
  "remarks": "P0 核心正向流程",
  "test_data": {
   "username": "13812345678",
   "password": "Test@1234"
  },
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "打开登录页面",
    "result": "登录页面正常显示，包含手机号输入框、密码输入框和登录按钮"
   },
   {
    "step": "在手机号输入框中输入 13812345678",
    "result": "输入框正确显示输入的手机号"
   },
   {
    "step": "在密码输入框中输入 Test@1234",
    "result": "密码以掩码形式显示"
   },
   {
    "step": "点击「登录」按钮",
    "result": "登录请求已提交，无重复提交"
   },
   {
    "step": "等待登录结果",
    "result": "页面跳转至系统首页/主界面，顶部栏显示用户已登录状态"
   }
  ]
 },
 {
  "name": "正确用户名+正确密码登录成功",
  "case_number": "TC-TEST-PROJECT-LOGIN-002",
  "module": "用户登录",
  "case_type": "functional",
  "preconditions": "已注册测试账号：用户名 test_qa_01，密码 Test@1234",
  "remarks": "P0 用户名登录正向流程",
  "test_data": {
   "username": "test_qa_01",
   "password": "Test@1234"
  },
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "打开登录页面",
    "result": "登录页面正常显示"
   },
   {
    "step": "切换到用户名登录方式",
    "result": "输入框标签切换为「用户名」"
   },
   {
    "step": "输入用户名 test_qa_01",
    "result": "输入框显示 test_qa_01"
   },
   {
    "step": "输入密码 Test@1234",
    "result": "密码以掩码（•）显示"
   },
   {
    "step": "点击「登录」按钮",
    "result": "登录成功，跳转至系统首页"
   }
  ]
 },
 {
  "name": "密码长度下边界（8位）登录",
  "case_number": "TC-TEST-PROJECT-LOGIN-003",
  "module": "用户登录",
  "case_type": "functional",
  "preconditions": "已注册测试账号：手机号 13912345678，密码 Aa1!5678（8位）",
  "remarks": "P0 边界值验证-密码最小长度",
  "test_data": {
   "username": "13912345678",
   "password": "Aa1!5678"
  },
  "priority": "high",
  "test_case_steps": [
   {
    "step": "打开登录页面",
    "result": "登录页面正常显示，包含手机号和密码输入框"
   },
   {
    "step": "在手机号输入框中输入 13912345678",
    "result": "输入框显示 13912345678"
   },
   {
    "step": "在密码输入框中输入 Aa1!5678（8位）",
    "result": "密码以掩码（•）显示，输入框接受8位字符"
   },
   {
    "step": "点击「登录」按钮",
    "result": "登录成功，页面跳转至系统首页"
   }
  ]
 },
 {
  "name": "密码长度上边界（20位）登录",
  "case_number": "TC-TEST-PROJECT-LOGIN-004",
  "module": "用户登录",
  "case_type": "functional",
  "preconditions": "已注册测试账号：手机号 15012345678，密码 Test@1234abcdEFGH!x（20位）",
  "remarks": "P1 边界值验证-密码最大长度",
  "test_data": {
   "username": "15012345678",
   "password": "Test@1234abcdEFGH!x"
  },
  "priority": "high",
  "test_case_steps": [
   {
    "step": "打开登录页面",
    "result": "登录页面正常显示，包含手机号和密码输入框"
   },
   {
    "step": "在手机号输入框中输入 15012345678",
    "result": "输入框显示 15012345678"
   },
   {
    "step": "在密码输入框中输入 Test@1234abcdEFGH!x（20位）",
    "result": "密码以掩码（•）显示，输入框接受20位字符"
   },
   {
    "step": "点击「登录」按钮",
    "result": "登录成功，页面跳转至系统首页"
   }
  ]
 },
 {
  "name": "记住我功能验证",
  "case_number": "TC-TEST-PROJECT-LOGIN-005",
  "module": "用户登录",
  "case_type": "functional",
  "preconditions": "已注册测试账号：手机号 13812345678，密码 Test@1234",
  "remarks": "P1 记住我功能验证",
  "test_data": {
   "username": "13812345678",
   "password": "Test@1234",
   "remember_me": true
  },
  "priority": "medium",
  "test_case_steps": [
   {
    "step": "打开登录页面",
    "result": "登录页面正常显示"
   },
   {
    "step": "勾选「记住我」复选框",
    "result": "复选框已选中，显示勾选状态"
   },
   {
    "step": "输入正确手机号和密码并登录",
    "result": "登录成功，跳转至系统首页"
   },
   {
    "step": "关闭浏览器，重新打开登录页",
    "result": "手机号输入框自动填充为 13812345678，或直接进入已登录状态"
   }
  ]
 },
 {
  "name": "密码小于最小长度（7位）登录失败",
  "case_number": "TC-TEST-PROJECT-LOGIN-006",
  "module": "用户登录",
  "case_type": "boundary",
  "preconditions": "已注册测试账号：手机号 15212345678，密码 Aa1!567（7位密码用于注册测试）",
  "remarks": "P1 边界值-密码小于8位",
  "test_data": {
   "username": "15212345678",
   "password": "Aa1!567"
  },
  "priority": "high",
  "test_case_steps": [
   {
    "step": "打开登录页面",
    "result": "登录页面正常显示"
   },
   {
    "step": "输入手机号 15212345678",
    "result": "输入框显示 15212345678"
   },
   {
    "step": "输入密码 Aa1!567（7位）",
    "result": "密码以掩码显示"
   },
   {
    "step": "点击「登录」按钮",
    "result": "登录按钮变为不可用/加载状态，提示「密码长度不能少于8位」"
   }
  ]
 },
 {
  "name": "密码大于最大长度（21位）登录失败",
  "case_number": "TC-TEST-PROJECT-LOGIN-007",
  "module": "用户登录",
  "case_type": "boundary",
  "preconditions": "无（前端输入阶段即拦截）",
  "remarks": "P1 边界值-密码超过20位",
  "test_data": {
   "username": "15212345678",
   "password": "Test@1234abcdEFGH!xY"
  },
  "priority": "high",
  "test_case_steps": [
   {
    "step": "打开登录页面",
    "result": "登录页面正常显示"
   },
   {
    "step": "输入手机号 15212345678",
    "result": "输入框显示 15212345678"
   },
   {
    "step": "在密码输入框中尝试输入 Test@1234abcdEFGH!xY（21位）",
    "result": "密码输入框最多接受20位字符，第21位无法输入，或被截断为20位"
   },
   {
    "step": "点击「登录」按钮",
    "result": "如未前端拦截，后端返回错误码提示密码格式错误"
   }
  ]
 },
 {
  "name": "手机号格式错误（10位）登录失败",
  "case_number": "TC-TEST-PROJECT-LOGIN-008",
  "module": "用户登录",
  "case_type": "boundary",
  "preconditions": "无（前端输入阶段即拦截）",
  "remarks": "P1 边界值-手机号小于11位",
  "test_data": {
   "username": "1381234567",
   "password": "Test@1234"
  },
  "priority": "high",
  "test_case_steps": [
   {
    "step": "打开登录页面",
    "result": "登录页面正常显示"
   },
   {
    "step": "输入手机号 1381234567（10位）",
    "result": "输入框显示 1381234567"
   },
   {
    "step": "输入密码 Test@1234",
    "result": "密码以掩码显示"
   },
   {
    "step": "点击「登录」按钮",
    "result": "提示「请输入正确的11位手机号」，登录被阻止"
   }
  ]
 },
 {
  "name": "手机号格式错误（12位）登录失败",
  "case_number": "TC-TEST-PROJECT-LOGIN-009",
  "module": "用户登录",
  "case_type": "boundary",
  "preconditions": "无（前端输入阶段即拦截）",
  "remarks": "P1 边界值-手机号大于11位",
  "test_data": {
   "username": "138123456789",
   "password": "Test@1234"
  },
  "priority": "high",
  "test_case_steps": [
   {
    "step": "打开登录页面",
    "result": "登录页面正常显示"
   },
   {
    "step": "输入手机号 138123456789（12位）",
    "result": "输入框显示 138123456789"
   },
   {
    "step": "输入密码 Test@1234",
    "result": "密码以掩码显示"
   },
   {
    "step": "点击「登录」按钮",
    "result": "提示「请输入正确的11位手机号」，登录被阻止"
   }
  ]
 },
 {
  "name": "手机号含非数字字符登录失败",
  "case_number": "TC-TEST-PROJECT-LOGIN-010",
  "module": "用户登录",
  "case_type": "boundary",
  "preconditions": "无（前端输入阶段即拦截）",
  "remarks": "P2 边界值-手机号含字母",
  "test_data": {
   "username": "138abc56789",
   "password": "Test@1234"
  },
  "priority": "medium",
  "test_case_steps": [
   {
    "step": "打开登录页面",
    "result": "登录页面正常显示"
   },
   {
    "step": "输入手机号 138abc56789",
    "result": "输入框显示输入内容（或自动过滤非数字字符）"
   },
   {
    "step": "输入密码 Test@1234",
    "result": "密码以掩码显示"
   },
   {
    "step": "点击「登录」按钮",
    "result": "提示「手机号格式不正确」，登录被阻止"
   }
  ]
 },
 {
  "name": "密码错误登录失败",
  "case_number": "TC-TEST-PROJECT-LOGIN-011",
  "module": "用户登录",
  "case_type": "functional",
  "preconditions": "已注册测试账号：手机号 13812345678，密码 Test@1234",
  "remarks": "P0 异常-密码错误",
  "test_data": {
   "username": "13812345678",
   "password": "WrongPass1!"
  },
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "打开登录页面",
    "result": "登录页面正常显示"
   },
   {
    "step": "输入手机号 13812345678",
    "result": "输入框显示 13812345678"
   },
   {
    "step": "输入错误密码 WrongPass1!",
    "result": "密码以掩码显示"
   },
   {
    "step": "点击「登录」按钮",
    "result": "页面提示「手机号或密码错误」，不透露具体哪个字段错误，停留在登录页"
   }
  ]
 },
 {
  "name": "手机号未注册登录失败",
  "case_number": "TC-TEST-PROJECT-LOGIN-012",
  "module": "用户登录",
  "case_type": "functional",
  "preconditions": "确保手机号 19900000000 未注册",
  "remarks": "P1 异常-账号不存在",
  "test_data": {
   "username": "19900000000",
   "password": "Test@1234"
  },
  "priority": "high",
  "test_case_steps": [
   {
    "step": "打开登录页面",
    "result": "登录页面正常显示"
   },
   {
    "step": "输入未注册手机号 19900000000",
    "result": "输入框显示 19900000000"
   },
   {
    "step": "输入密码 Test@1234",
    "result": "密码以掩码显示"
   },
   {
    "step": "点击「登录」按钮",
    "result": "页面提示「手机号或密码错误」，不透露账号是否存在"
   }
  ]
 },
 {
  "name": "连续5次密码错误触发账号锁定",
  "case_number": "TC-TEST-PROJECT-LOGIN-013",
  "module": "用户登录",
  "case_type": "security",
  "preconditions": "已注册测试账号：手机号 13612345678，密码 Correct@123",
  "remarks": "P0 安全策略-账户锁定",
  "test_data": {
   "username": "13612345678",
   "password": "WrongPass1!"
  },
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "打开登录页面，输入手机号 13612345678 和错误密码 WrongPass1!，点击登录",
    "result": "第1次：提示「手机号或密码错误」，失败计数+1"
   },
   {
    "step": "重复第1步共4次（累计5次失败）",
    "result": "第5次失败后：提示「账号已被锁定，请30分钟后再试」"
   },
   {
    "step": "使用正确密码 Correct@123 立即尝试登录",
    "result": "登录被拒绝，提示账号仍处于锁定状态"
   },
   {
    "step": "等待30分钟后，使用正确密码 Correct@123 登录",
    "result": "登录成功，账号锁定已自动解除"
   }
  ]
 },
 {
  "name": "SQL注入攻击-登录绕过",
  "case_number": "TC-TEST-PROJECT-LOGIN-014",
  "module": "用户登录",
  "case_type": "security",
  "preconditions": "无",
  "remarks": "P0 安全-SQL注入防御",
  "test_data": {
   "username": "' OR '1'='1",
   "password": "' OR '1'='1"
  },
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "打开登录页面",
    "result": "登录页面正常显示"
   },
   {
    "step": "在手机号输入框输入 ' OR '1'='1",
    "result": "输入框正常显示输入内容"
   },
   {
    "step": "在密码输入框输入 ' OR '1'='1",
    "result": "密码以掩码显示"
   },
   {
    "step": "点击「登录」按钮",
    "result": "登录失败，提示「手机号或密码错误」，未绕过认证系统"
   }
  ]
 },
 {
  "name": "SQL注入攻击-DROP语句",
  "case_number": "TC-TEST-PROJECT-LOGIN-015",
  "module": "用户登录",
  "case_type": "security",
  "preconditions": "无",
  "remarks": "P1 安全-SQL注入破坏性测试",
  "test_data": {
   "username": "'; DROP TABLE users; --",
   "password": "test123"
  },
  "priority": "high",
  "test_case_steps": [
   {
    "step": "打开登录页面",
    "result": "登录页面正常显示"
   },
   {
    "step": "在手机号输入框输入 '; DROP TABLE users; --",
    "result": "输入框显示输入内容"
   },
   {
    "step": "输入密码 test123",
    "result": "密码以掩码显示"
   },
   {
    "step": "点击「登录」按钮",
    "result": "系统正常运行，未发生数据丢失或系统异常"
   },
   {
    "step": "使用正常账号 13812345678/Test@1234 重新登录",
    "result": "登录功能正常，数据库表未被删除"
   }
  ]
 },
 {
  "name": "XSS攻击-脚本注入",
  "case_number": "TC-TEST-PROJECT-LOGIN-016",
  "module": "用户登录",
  "case_type": "security",
  "preconditions": "无",
  "remarks": "P1 安全-XSS防御",
  "test_data": {
   "username": "<script>alert('xss')</script>",
   "password": "<script>alert('xss')</script>"
  },
  "priority": "high",
  "test_case_steps": [
   {
    "step": "打开登录页面",
    "result": "登录页面正常显示"
   },
   {
    "step": "在手机号输入框输入 <script>alert('xss')</script>",
    "result": "输入框显示输入内容"
   },
   {
    "step": "在密码输入框输入 <script>alert('xss')</script>",
    "result": "密码以掩码显示"
   },
   {
    "step": "点击「登录」按钮",
    "result": "未弹出 JavaScript 对话框，脚本未被浏览器执行"
   },
   {
    "step": "检查页面源代码或开发者工具",
    "result": "输入内容已被 HTML 转义处理（如 < 转换为 &lt;），未创建 script 标签"
   }
  ]
 },
 {
  "name": "密码为纯数字登录失败",
  "case_number": "TC-TEST-PROJECT-LOGIN-017",
  "module": "用户登录",
  "case_type": "boundary",
  "preconditions": "无（前端输入阶段即拦截）",
  "remarks": "P2 边界值-密码强度不足",
  "test_data": {
   "username": "13812345678",
   "password": "12345678"
  },
  "priority": "medium",
  "test_case_steps": [
   {
    "step": "打开登录页面",
    "result": "登录页面正常显示"
   },
   {
    "step": "输入手机号 13812345678",
    "result": "输入框显示 13812345678"
   },
   {
    "step": "输入密码 12345678（纯数字、8位）",
    "result": "密码以掩码显示"
   },
   {
    "step": "点击「登录」按钮",
    "result": "提示「密码必须包含字母、数字和特殊字符」，登录被阻止"
   }
  ]
 },
 {
  "name": "密码缺少特殊字符登录失败",
  "case_number": "TC-TEST-PROJECT-LOGIN-018",
  "module": "用户登录",
  "case_type": "boundary",
  "preconditions": "无（前端输入阶段即拦截）",
  "remarks": "P2 边界值-密码缺少特殊字符",
  "test_data": {
   "username": "13812345678",
   "password": "Abcd1234"
  },
  "priority": "medium",
  "test_case_steps": [
   {
    "step": "打开登录页面",
    "result": "登录页面正常显示"
   },
   {
    "step": "输入手机号 13812345678",
    "result": "输入框显示 13812345678"
   },
   {
    "step": "输入密码 Abcd1234（字母+数字，无特殊字符）",
    "result": "密码以掩码显示"
   },
   {
    "step": "点击「登录」按钮",
    "result": "提示「密码必须包含特殊字符」，登录被阻止"
   }
  ]
 },
 {
  "name": "密码显示/隐藏切换",
  "case_number": "TC-TEST-PROJECT-LOGIN-019",
  "module": "用户登录",
  "case_type": "UI",
  "preconditions": "无",
  "remarks": "P2 UI功能-密码可见性切换",
  "test_data": {
   "username": "13812345678",
   "password": "Test@1234"
  },
  "priority": "medium",
  "test_case_steps": [
   {
    "step": "打开登录页面",
    "result": "登录页面正常显示"
   },
   {
    "step": "输入密码 Test@1234",
    "result": "密码以掩码（•）显示"
   },
   {
    "step": "点击密码输入框右侧的「眼睛」图标",
    "result": "密码由掩码切换为明文显示，显示 Test@1234"
   },
   {
    "step": "再次点击「眼睛」图标",
    "result": "密码恢复为掩码显示"
   },
   {
    "step": "切换为明文后，点击登录",
    "result": "登录正常，不影响登录功能"
   }
  ]
 },
 {
  "name": "已登录状态下访问登录页",
  "case_number": "TC-TEST-PROJECT-LOGIN-020",
  "module": "用户登录",
  "case_type": "functional",
  "preconditions": "用户已登录系统（通过正常登录获取有效会话）",
  "remarks": "P1 场景-登录态重入",
  "test_data": {},
  "priority": "high",
  "test_case_steps": [
   {
    "step": "用户已处于登录状态，在浏览器地址栏输入登录页URL并访问",
    "result": "自动跳转至系统首页/仪表盘，不显示登录页"
   },
   {
    "step": "清除浏览器Cookie/清除Token后刷新页面",
    "result": "跳转回登录页面，需要重新登录"
   }
  ]
 },
 {
  "name": "登出后重新登录",
  "case_number": "TC-TEST-PROJECT-LOGIN-021",
  "module": "用户登录",
  "case_type": "functional",
  "preconditions": "已注册测试账号：手机号 13812345678，密码 Test@1234",
  "remarks": "P1 场景-登出再登录",
  "test_data": {
   "username": "13812345678",
   "password": "Test@1234"
  },
  "priority": "high",
  "test_case_steps": [
   {
    "step": "使用正确账号 13812345678 / Test@1234 登录成功",
    "result": "跳转至系统首页"
   },
   {
    "step": "点击「登出」按钮",
    "result": "退出成功，跳转回登录页，会话已销毁"
   },
   {
    "step": "在登录页使用同一账号重新登录",
    "result": "成功登录，跳转至系统首页"
   }
  ]
 },
 {
  "name": "空手机号+空密码提交",
  "case_number": "TC-TEST-PROJECT-LOGIN-022",
  "module": "用户登录",
  "case_type": "functional",
  "preconditions": "无",
  "remarks": "P1 异常-空输入",
  "test_data": {
   "username": "",
   "password": ""
  },
  "priority": "high",
  "test_case_steps": [
   {
    "step": "打开登录页面",
    "result": "登录页面正常显示"
   },
   {
    "step": "不输入任何内容，直接点击「登录」按钮",
    "result": "登录按钮保持禁用状态，或点击后提示「请输入手机号」和「请输入密码」，不发起登录请求"
   }
  ]
 },
 {
  "name": "手机号含前导后置空格登录",
  "case_number": "TC-TEST-PROJECT-LOGIN-023",
  "module": "用户登录",
  "case_type": "boundary",
  "preconditions": "已注册测试账号：手机号 13812345678，密码 Test@1234",
  "remarks": "P2 边界值-输入前后空格处理",
  "test_data": {
   "username": "  13812345678  ",
   "password": "Test@1234"
  },
  "priority": "medium",
  "test_case_steps": [
   {
    "step": "打开登录页面",
    "result": "登录页面正常显示"
   },
   {
    "step": "在手机号输入框输入「空格+13812345678+空格」",
    "result": "输入框显示含空格的内容"
   },
   {
    "step": "输入密码 Test@1234",
    "result": "密码以掩码显示"
   },
   {
    "step": "点击「登录」按钮",
    "result": "登录成功（系统自动trim前后空格），跳转至系统首页"
   }
  ]
 },
 {
  "name": "密码含前导后置空格登录",
  "case_number": "TC-TEST-PROJECT-LOGIN-024",
  "module": "用户登录",
  "case_type": "boundary",
  "preconditions": "已注册测试账号：手机号 13812345678，密码 Test@1234",
  "remarks": "P2 边界值-密码前后空格处理",
  "test_data": {
   "username": "13812345678",
   "password": "  Test@1234  "
  },
  "priority": "medium",
  "test_case_steps": [
   {
    "step": "打开登录页面",
    "result": "登录页面正常显示"
   },
   {
    "step": "输入手机号 13812345678",
    "result": "输入框显示 13812345678"
   },
   {
    "step": "在密码输入框输入「空格+Test@1234+空格」",
    "result": "密码以掩码显示"
   },
   {
    "step": "点击「登录」按钮",
    "result": "根据系统实现：若trim密码空格则登录成功；若不trim则提示密码错误。需确认系统实现方式"
   }
  ]
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 36. ws-PR-1-test_cases_module_06_log

- 来源：`workspace/testcase/PR-1/test_cases_module_06_log.jsonl`　分组：PR-1　用例数：6

```json
[
 {
  "name": "登录成功记录完整日志字段",
  "case_number": "TC-PR1-LOG-001",
  "module": "登录日志与安全提醒",
  "case_type": "functional",
  "preconditions": "账号13812345678存在，后端日志表可查询",
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "使用已知测试IP与设备完成一次登录",
    "result": "登录日志新增一条记录"
   },
   {
    "step": "查询该记录字段",
    "result": "记录包含：登录时间、IP地址、归属地、设备信息、登录结果(成功)五类字段且与测试实际一致"
   }
  ],
  "test_data": {
   "测试IP": "198.51.100.8",
   "设备": "iPhone 15",
   "归属地": "北京市",
   "登录结果": "成功"
  },
  "remarks": "FP-015 需求FR-06"
 },
 {
  "name": "登录失败也记录日志",
  "case_number": "TC-PR1-LOG-002",
  "module": "登录日志与安全提醒",
  "case_type": "functional",
  "preconditions": "账号13812345678存在，可构造失败登录(错误验证码)",
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "使用错误验证码发起一次登录",
    "result": "登录失败，页面提示验证码错误"
   },
   {
    "step": "查询登录日志",
    "result": "日志中新增一条失败记录，登录结果字段为失败，含IP/时间/设备信息"
   }
  ],
  "test_data": {
   "验证码": "错误验证码999999",
   "登录结果": "失败"
  },
  "remarks": "FP-015 需求FR-06"
 },
 {
  "name": "登录日志支持按条件查询",
  "case_number": "TC-PR1-LOG-003",
  "module": "登录日志与安全提醒",
  "case_type": "functional",
  "preconditions": "后端已积累多条登录日志",
  "priority": "medium",
  "test_case_steps": [
   {
    "step": "按手机号13812345678查询日志",
    "result": "返回该账号全部登录记录"
   },
   {
    "step": "按时间范围、登录结果(成功/失败)筛选",
    "result": "筛选结果与条件一致，排序正确"
   }
  ],
  "test_data": {
   "查询条件": "手机号/时间范围/登录结果"
  },
  "remarks": "FP-015 需求FR-06 日志可查询"
 },
 {
  "name": "异地登录成功后发送安全提醒短信",
  "case_number": "TC-PR1-LOG-004",
  "module": "登录日志与安全提醒",
  "case_type": "functional",
  "preconditions": "账号常用地市为北京市，短信平台Mock可捕获下发记录",
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "使用上海市IP(非常用地市)登录该账号",
    "result": "登录成功"
   },
   {
    "step": "检查短信网关",
    "result": "向该手机号发送一条安全提醒短信"
   }
  ],
  "test_data": {
   "常用地市": "北京市",
   "本次登录地市": "上海市",
   "提醒短信": "已发送"
  },
  "remarks": "FP-016 需求FR-06"
 },
 {
  "name": "常用地市登录不触发安全提醒",
  "case_number": "TC-PR1-LOG-005",
  "module": "登录日志与安全提醒",
  "case_type": "functional",
  "preconditions": "账号常用地市为北京市",
  "priority": "high",
  "test_case_steps": [
   {
    "step": "使用北京市IP登录该账号",
    "result": "登录成功，正常进入"
   },
   {
    "step": "检查短信网关",
    "result": "无安全提醒短信下发"
   }
  ],
  "test_data": {
   "常用地市": "北京市",
   "本次登录地市": "北京市",
   "提醒短信": "未发送"
  },
  "remarks": "FP-016 需求FR-06"
 },
 {
  "name": "安全提醒短信内容与发送时机校验",
  "case_number": "TC-PR1-LOG-006",
  "module": "登录日志与安全提醒",
  "case_type": "functional",
  "preconditions": "异地登录场景可复现，短信平台Mock可捕获内容",
  "priority": "medium",
  "test_case_steps": [
   {
    "step": "异地登录成功后捕获提醒短信",
    "result": "短信在登录成功后的合理时间窗口内(如1分钟内)下发"
   },
   {
    "step": "检查短信内容",
    "result": "短信包含：登录时间、登录地点、账号脱敏信息及异常提示话术，不含完整验证码或敏感凭据"
   }
  ],
  "test_data": {
   "短信发送窗口": "登录成功后≤1分钟",
   "短信要素": "时间/地点/账号脱敏/异常提示"
  },
  "remarks": "FP-016 需求FR-06"
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 37. ws-td_cases

- 来源：`workspace/testcase/td_cases.jsonl`　分组：(root)　用例数：26

```json
[
 {
  "case_number": "TC-TD-LOC-001",
  "module": "TD管管理-新增表单",
  "name": "新增TD管时，当前所在地点字段默认显示正确值",
  "priority": "P0",
  "description": "验证新增TD管表单中当前所在地点字段的默认值",
  "preconditions": "用户已登录并拥有TD管管理权限；地点管理中存在精智未来（广州）采购仓储部（ID: SP0000094）",
  "test_data": {
   "TD管号": "TD-TEST-001",
   "生产厂商": "精智未来(广州)科技有限公司",
   "采购时间": "2025/07/02",
   "当前所在地点": "精智未来（广州）采购仓储部",
   "归属方": "精智未来（广州）采购仓储部"
  },
  "steps": "1. 进入资产管理→TD管管理→点击新增按钮\n2. 查看当前所在地点字段的默认值",
  "expected_results": "当前所在地点字段默认显示为精智未来（广州）采购仓储部",
  "remarks": "REQ-01, REQ-03"
 },
 {
  "case_number": "TC-TD-LOC-002",
  "module": "TD管管理-新增表单",
  "name": "新增TD管时，手动修改当前所在地点",
  "priority": "P0",
  "description": "验证新增TD管时可手动修改当前所在地点",
  "preconditions": "地点管理中至少存在2个地点（含默认地点）",
  "test_data": {
   "TD管号": "TD-TEST-002",
   "当前所在地点": "广州实验室（手动选择）"
  },
  "steps": "1. 进入新增TD管表单\n2. 修改当前所在地点为另一个地点（如广州实验室）\n3. 填写其他必填字段，提交保存",
  "expected_results": "1. 当前所在地点可下拉选择并修改\n2. 提交成功后，该TD管的当前所在地点显示为广州实验室",
  "remarks": "REQ-01"
 },
 {
  "case_number": "TC-TD-LOC-003",
  "module": "TD管管理-新增表单",
  "name": "新增TD管时，当前所在地点字段为空校验",
  "priority": "P1",
  "description": "验证当前所在地点字段为空时系统提示",
  "preconditions": "无",
  "test_data": {
   "TD管号": "TD-TEST-003",
   "当前所在地点": ""
  },
  "steps": "1. 进入新增TD管表单\n2. 将当前所在地点字段清空\n3. 点击提交",
  "expected_results": "系统提示当前所在地点不能为空，提交被阻止",
  "remarks": "REQ-01"
 },
 {
  "case_number": "TC-TD-LOC-004",
  "module": "TD管管理-导入",
  "name": "批量导入TD管时，当前所在地点校验通过",
  "priority": "P0",
  "description": "验证批量导入时当前所在地点正确则校验通过",
  "preconditions": "准备导入模板文件",
  "test_data": {
   "TD管号": "TD-TEST-004",
   "生产厂商": "精智未来",
   "采购时间": "2025/07/02",
   "当前所在地点": "精智未来（广州）采购仓储部",
   "归属方": "精智未来（广州）采购仓储部"
  },
  "steps": "1. 进入TD管管理→点击上文件→选择导入模板\n2. 上传包含正确当前所在地点的数据文件\n3. 点击校验数据",
  "expected_results": "校验通过，无错误提示，数据预览正常显示",
  "remarks": "REQ-04"
 },
 {
  "case_number": "TC-TD-LOC-005",
  "module": "TD管管理-导入",
  "name": "批量导入TD管时，当前所在地点校验不通过",
  "priority": "P0",
  "description": "验证批量导入时当前所在地点错误则校验不通过",
  "preconditions": "准备导入模板文件",
  "test_data": {
   "TD管号": "TD-TEST-005",
   "当前所在地点": "无效地点名称（地点管理中不存在的地点）"
  },
  "steps": "1. 上传包含错误当前所在地点的数据文件\n2. 点击校验数据",
  "expected_results": "校验不通过，系统提示当前所在地点不正确或类似错误信息",
  "remarks": "REQ-04"
 },
 {
  "case_number": "TC-TD-LOC-006",
  "module": "TD管管理-导入",
  "name": "批量导入TD管时，当前所在地点字段为空",
  "priority": "P1",
  "description": "验证批量导入时当前所在地点为空则校验不通过",
  "preconditions": "准备导入模板文件",
  "test_data": {
   "TD管号": "TD-TEST-006",
   "当前所在地点": ""
  },
  "steps": "1. 上传当前所在地点为空的导入文件\n2. 点击校验数据",
  "expected_results": "校验不通过，系统提示当前所在地点不能为空",
  "remarks": "REQ-04"
 },
 {
  "case_number": "TC-TD-OWNER-001",
  "module": "TD管管理-新增表单",
  "name": "新增TD管时，归属方可从地点管理中选择",
  "priority": "P0",
  "description": "验证归属方下拉选项来自地点管理",
  "preconditions": "地点管理中至少存在3个地点",
  "test_data": {
   "TD管号": "TD-TEST-007",
   "归属方": "广州实验室（从地点管理选择）"
  },
  "steps": "1. 进入新增TD管表单\n2. 点击归属方下拉选择框\n3. 从列表中选择广州实验室\n4. 填写其他字段，提交保存",
  "expected_results": "1. 归属方下拉选项来自地点管理中的地点列表\n2. 提交成功后，该TD管的归属方显示为广州实验室",
  "remarks": "REQ-02"
 },
 {
  "case_number": "TC-TD-OWNER-002",
  "module": "TD管管理-新增表单",
  "name": "新增TD管时，归属方可修改",
  "priority": "P0",
  "description": "验证归属方字段支持修改",
  "preconditions": "地点管理中至少存在2个地点",
  "test_data": {
   "TD管号": "TD-TEST-008",
   "归属方": "先选地点A后改为地点B"
  },
  "steps": "1. 进入新增TD管表单\n2. 先选择归属方为地点A\n3. 再修改归属方为地点B\n4. 提交保存",
  "expected_results": "归属方可正常修改，提交后该TD管的归属方为地点B",
  "remarks": "REQ-02"
 },
 {
  "case_number": "TC-TD-OWNER-003",
  "module": "TD管管理-新增表单",
  "name": "新增TD管时，归属方不选择（空值）",
  "priority": "P1",
  "description": "验证归属方为空时能否正常提交",
  "preconditions": "无",
  "test_data": {
   "TD管号": "TD-TEST-009",
   "归属方": ""
  },
  "steps": "1. 进入新增TD管表单\n2. 归属方字段不选择任何值\n3. 填写其他必填字段，提交保存",
  "expected_results": "归属方为空时，提交成功，该TD管的归属方显示为空",
  "remarks": "REQ-02"
 },
 {
  "case_number": "TC-TD-OWNER-004",
  "module": "TD管管理-编辑",
  "name": "编辑TD管时，归属方可修改",
  "priority": "P1",
  "description": "验证编辑TD管时归属方字段可修改",
  "preconditions": "已存在一个TD管（TD-TEST-007），归属方为广州实验室",
  "test_data": {
   "TD管号": "TD-TEST-007",
   "归属方改为": "精智未来（广州）采购仓储部"
  },
  "steps": "1. 进入TD管列表，点击TD-TEST-007的编辑按钮\n2. 修改归属方为精智未来（广州）采购仓储部\n3. 保存",
  "expected_results": "编辑保存成功，该TD管的归属方更新为精智未来（广州）采购仓储部",
  "remarks": "REQ-02"
 },
 {
  "case_number": "TC-TD-LOG-001",
  "module": "TD管管理-物流流转单",
  "name": "新增TD管时，勾选同时创建待签收物流单",
  "priority": "P0",
  "description": "验证新增TD管时勾选创建物流单，各字段默认值正确",
  "preconditions": "地点管理中至少存在1个寄送地点",
  "test_data": {
   "TD管号": "TD-TEST-010",
   "勾选创建物流单": "是",
   "寄送地点": "广州实验室"
  },
  "steps": "1. 进入新增TD管表单，填写TD管信息\n2. 勾选同时创建待签收物流单\n3. 手动选择寄送地点=广州实验室\n4. 点击创建流转单",
  "expected_results": "1. 物流流转单创建成功\n2. 流转单中：寄送方式=自带，快递编号=空，运单图片=空，寄送方=当前操作用户，寄送地点=广州实验室，寄送时间=提交时间，物品=TD管（空），运输条件=常温，清单=TD-TEST-010，添加图片=空",
  "remarks": "REQ-05 ~ REQ-05j"
 },
 {
  "case_number": "TC-TD-LOG-002",
  "module": "TD管管理-物流流转单",
  "name": "新增TD管时，不勾选创建物流单",
  "priority": "P0",
  "description": "验证不勾选创建物流单时仅新增TD管",
  "preconditions": "无",
  "test_data": {
   "TD管号": "TD-TEST-011",
   "勾选创建物流单": "否"
  },
  "steps": "1. 进入新增TD管表单，填写TD管信息\n2. 不勾选同时创建待签收物流单\n3. 点击完成提交",
  "expected_results": "TD管新增成功，不创建物流流转单",
  "remarks": "REQ-05"
 },
 {
  "case_number": "TC-TD-LOG-003",
  "module": "TD管管理-物流流转单",
  "name": "新增多个TD管时，勾选创建物流单，清单包含所有新增TD管",
  "priority": "P1",
  "description": "验证批量新增TD管时物流单清单包含全部TD管",
  "preconditions": "地点管理中至少存在1个寄送地点",
  "test_data": {
   "TD管号": "TD-TEST-012, TD-TEST-013",
   "勾选创建物流单": "是",
   "寄送地点": "广州实验室"
  },
  "steps": "1. 批量新增2个TD管（TD-TEST-012, TD-TEST-013）\n2. 勾选同时创建待签收物流单\n3. 选择寄送地点，点击创建流转单",
  "expected_results": "1. 物流流转单创建成功\n2. 流转单的清单字段包含TD-TEST-012和TD-TEST-013两个TD管",
  "remarks": "REQ-05i"
 },
 {
  "case_number": "TC-TD-LOG-004",
  "module": "TD管管理-物流流转单",
  "name": "创建物流单时，寄送地点未选择",
  "priority": "P1",
  "description": "验证寄送地点未选择时系统提示",
  "preconditions": "无",
  "test_data": {
   "TD管号": "TD-TEST-014",
   "勾选创建物流单": "是",
   "寄送地点": ""
  },
  "steps": "1. 新增TD管，勾选同时创建待签收物流单\n2. 不选择寄送地点\n3. 点击创建流转单",
  "expected_results": "系统提示请选择寄送地点，流转单创建被阻止",
  "remarks": "REQ-05e"
 },
 {
  "case_number": "TC-TD-POS-001",
  "module": "TD管管理-标气运输",
  "name": "标气运输签收后，绑定的TD管位置跟随变更",
  "priority": "P1",
  "description": "验证标气运输签收后TD管当前所在地点自动变更",
  "preconditions": "存在一个标气批次，绑定了TD管（TD-TEST-015），当前所在地点为精智未来（广州）采购仓储部",
  "test_data": {
   "标气批次号": "BG-TEST-001",
   "绑定TD管": "TD-TEST-015",
   "物流单寄送地点": "广州实验室"
  },
  "steps": "1. 创建标气运输物流单，寄送地点=广州实验室\n2. 物流单签收\n3. 查看TD管TD-TEST-015的详情",
  "expected_results": "1. 签收后，TD-TEST-015的当前所在地点变更为广州实验室\n2. TD-TEST-015的使用记录中体现位置变更记录",
  "remarks": "REQ-06"
 },
 {
  "case_number": "TC-TD-POS-002",
  "module": "TD管管理-标气运输",
  "name": "标气运输签收后，使用记录中体现位置变更",
  "priority": "P1",
  "description": "验证位置变更在使用记录中正确记录",
  "preconditions": "TC-TD-POS-001执行成功",
  "test_data": {
   "TD管号": "TD-TEST-015"
  },
  "steps": "1. 进入TD管TD-TEST-015的详情页\n2. 查看使用记录选项卡",
  "expected_results": "使用记录中包含一条位置变更记录：操作类型为位置变更或类似描述，记录从精智未来（广州）采购仓储部变更为广州实验室",
  "remarks": "REQ-06"
 },
 {
  "case_number": "TC-TD-STATUS-001",
  "module": "TD管管理-状态变更",
  "name": "将空闲状态的TD管手动变更为已售出",
  "priority": "P0",
  "description": "验证空闲状态可手动变更为已售出",
  "preconditions": "存在一个状态为空闲的TD管（TD-TEST-016）",
  "test_data": {
   "TD管号": "TD-TEST-016",
   "原状态": "空闲",
   "目标状态": "已售出"
  },
  "steps": "1. 进入TD管详情页\n2. 点击状态字段的编辑按钮\n3. 选择已售出\n4. 保存",
  "expected_results": "TD管状态变更为已售出，页面显示更新",
  "remarks": "REQ-07"
 },
 {
  "case_number": "TC-TD-STATUS-002",
  "module": "TD管管理-状态变更",
  "name": "将占用中状态的TD管手动变更为待查册",
  "priority": "P0",
  "description": "验证占用中状态可手动变更为待查册",
  "preconditions": "存在一个状态为占用中的TD管（TD-TEST-017）",
  "test_data": {
   "TD管号": "TD-TEST-017",
   "原状态": "占用中",
   "目标状态": "待查册"
  },
  "steps": "1. 进入TD管详情页\n2. 点击状态字段的编辑按钮\n3. 选择待查册\n4. 保存",
  "expected_results": "TD管状态变更为待查册，页面显示更新",
  "remarks": "REQ-07"
 },
 {
  "case_number": "TC-TD-STATUS-003",
  "module": "TD管管理-状态变更",
  "name": "将已售出状态的TD管变更为待查册",
  "priority": "P1",
  "description": "验证已售出状态可手动变更为待查册",
  "preconditions": "存在一个状态为已售出的TD管（TD-TEST-018）",
  "test_data": {
   "TD管号": "TD-TEST-018",
   "原状态": "已售出",
   "目标状态": "待查册"
  },
  "steps": "1. 进入TD管详情页\n2. 修改状态为待查册\n3. 保存",
  "expected_results": "TD管状态变更为待查册",
  "remarks": "REQ-07"
 },
 {
  "case_number": "TC-TD-STATUS-004",
  "module": "TD管管理-列表筛选",
  "name": "按已售出状态筛选TD管列表",
  "priority": "P0",
  "description": "验证可按已售出状态筛选",
  "preconditions": "至少存在1个状态为已售出的TD管",
  "test_data": {
   "筛选条件": "状态=已售出"
  },
  "steps": "1. 进入TD管列表页\n2. 在状态筛选条件中选择已售出\n3. 点击筛选",
  "expected_results": "列表仅显示状态为已售出的TD管，筛选结果正确",
  "remarks": "REQ-07a"
 },
 {
  "case_number": "TC-TD-STATUS-005",
  "module": "TD管管理-列表筛选",
  "name": "按待查册状态筛选TD管列表",
  "priority": "P0",
  "description": "验证可按待查册状态筛选",
  "preconditions": "至少存在1个状态为待查册的TD管",
  "test_data": {
   "筛选条件": "状态=待查册"
  },
  "steps": "1. 进入TD管列表页\n2. 在状态筛选条件中选择待查册\n3. 点击筛选",
  "expected_results": "列表仅显示状态为待查册的TD管，筛选结果正确",
  "remarks": "REQ-07a"
 },
 {
  "case_number": "TC-TD-STATUS-006",
  "module": "TD管管理-统计",
  "name": "TD管统计中包含已售出和待查册状态",
  "priority": "P1",
  "description": "验证统计页面包含新增状态",
  "preconditions": "存在已售出和待查册状态的TD管",
  "test_data": {},
  "steps": "1. 进入TD管统计页面\n2. 查看状态分布统计",
  "expected_results": "统计图表/列表中包含已售出和待查册两个状态的统计数据，数量与实际数据一致",
  "remarks": "REQ-07a"
 },
 {
  "case_number": "TC-TD-EXPORT-001",
  "module": "TD管管理-列表导出",
  "name": "导出TD管列表（不带条件）",
  "priority": "P1",
  "description": "验证列表导出功能正常",
  "preconditions": "TD管列表中至少存在5条数据",
  "test_data": {
   "筛选条件": "无"
  },
  "steps": "1. 进入TD管列表页\n2. 不设置任何筛选条件\n3. 点击批量导出按钮",
  "expected_results": "1. 系统导出Excel文件\n2. 导出内容包含所有TD管数据（TD管号、状态、使用次数、老化次数、最近老化批次、最近老化时间、归属方、当前所在地点等字段）\n3. 导出数据与列表展示数据一致",
  "remarks": "REQ-08"
 },
 {
  "case_number": "TC-TD-LIST-001",
  "module": "TD管管理-列表展示",
  "name": "TD管列表展示归属方字段",
  "priority": "P1",
  "description": "验证列表页展示归属方字段",
  "preconditions": "存在设置了归属方的TD管",
  "test_data": {
   "TD管号": "TD-TEST-007",
   "归属方": "广州实验室"
  },
  "steps": "1. 进入TD管列表页\n2. 查看列表表头字段\n3. 查看TD-TEST-007所在行的归属方列",
  "expected_results": "1. 列表表头包含归属方列\n2. TD-TEST-007的归属方显示为广州实验室\n3. 归属方字段内容与TD管详情中的归属方一致",
  "remarks": "REQ-09"
 },
 {
  "case_number": "TC-TD-SEC-001",
  "module": "TD管管理-安全测试",
  "name": "当前所在地点字段防止XSS注入",
  "priority": "P2",
  "description": "验证XSS脚本注入防护",
  "preconditions": "无",
  "test_data": {
   "TD管号": "TD-TEST-099",
   "当前所在地点": "<script>alert('xss')</script>"
  },
  "steps": "1. 尝试在新增TD管表单的当前所在地点字段输入XSS脚本\n2. 提交保存\n3. 查看列表页和详情页的展示",
  "expected_results": "脚本代码被转义或过滤，不会在页面上执行，以纯文本形式显示",
  "remarks": "REQ-01"
 },
 {
  "case_number": "TC-TD-SEC-002",
  "module": "TD管管理-边界测试",
  "name": "当前所在地点字段超长文本边界测试",
  "priority": "P2",
  "description": "验证超长文本输入的处理",
  "preconditions": "无",
  "test_data": {
   "TD管号": "TD-TEST-100",
   "当前所在地点": "A×500（500个字符的超长文本）"
  },
  "steps": "1. 尝试在新增TD管表单的当前所在地点字段输入超长文本\n2. 提交保存",
  "expected_results": "系统对输入长度进行限制，或提示当前所在地点长度超出限制，提交被阻止",
  "remarks": "REQ-01"
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 38. ws-PR-1-test_cases_module_04_logout

- 来源：`workspace/testcase/PR-1/test_cases_module_04_logout.jsonl`　分组：PR-1　用例数：5

```json
[
 {
  "name": "Web端主动登出后返回登录页",
  "case_number": "TC-PR1-LOGOUT-001",
  "module": "登出",
  "case_type": "functional",
  "preconditions": "Web端已登录，位于受保护页面",
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "点击页面右上角\"登出\"按钮",
    "result": "页面跳转至登录页，地址栏为登录页URL"
   },
   {
    "step": "尝试直接访问登出前的受保护页面URL",
    "result": "被重定向回登录页，无法访问原页面"
   }
  ],
  "test_data": {
   "操作": "Web端主动登出",
   "受保护页面": "/api/v1/orders 对应页面"
  },
  "remarks": "FP-011 需求FR-04"
 },
 {
  "name": "登出后本地token被清除",
  "case_number": "TC-PR1-LOGOUT-002",
  "module": "登出",
  "case_type": "functional",
  "preconditions": "Web端已登录，本地存储中含token",
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "登出前通过浏览器开发者工具记录Cookie/localStorage中的token",
    "result": "存在有效token记录"
   },
   {
    "step": "执行登出操作",
    "result": "Cookie与localStorage中token字段被删除，不存在残留"
   },
   {
    "step": "刷新页面",
    "result": "页面无token，停留登录页"
   }
  ],
  "test_data": {
   "存储位置": "Cookie+localStorage",
   "登出前token": "存在",
   "登出后token": "不存在"
  },
  "remarks": "FP-011 需求FR-04"
 },
 {
  "name": "登出后服务端token立即失效",
  "case_number": "TC-PR1-LOGOUT-003",
  "module": "登出",
  "case_type": "security",
  "preconditions": "已登录用户，抓包获取登出前token",
  "priority": "critical",
  "test_case_steps": [
   {
    "step": "执行登出操作",
    "result": "登出接口返回成功，服务端记录token失效"
   },
   {
    "step": "用登出前的token调用受保护接口",
    "result": "返回401 Unauthorized，服务端token已立即失效"
   }
  ],
  "test_data": {
   "旧token": "登出前抓包获取",
   "受保护接口": "/api/v1/orders",
   "预期状态码": "401"
  },
  "remarks": "FP-011 安全 需求FR-04"
 },
 {
  "name": "登出后本地敏感数据被清除",
  "case_number": "TC-PR1-LOGOUT-004",
  "module": "登出",
  "case_type": "functional",
  "preconditions": "登录期间已产生缓存数据(如用户信息、订单缓存、浏览记录)",
  "priority": "high",
  "test_case_steps": [
   {
    "step": "登录后产生并检查本地缓存的用户敏感数据(用户资料、订单、token)",
    "result": "本地存在上述敏感数据"
   },
   {
    "step": "执行登出操作",
    "result": "本地缓存的用户资料、订单缓存、token等敏感数据全部清除"
   },
   {
    "step": "通过调试工具检查存储",
    "result": "存储中无该用户任何个人数据残留"
   }
  ],
  "test_data": {
   "缓存类型": "用户信息/订单缓存/token",
   "登出后残留": "无"
  },
  "remarks": "FP-011 需求FR-04"
 },
 {
  "name": "App端登出后返回登录页且登录态清除",
  "case_number": "TC-PR1-LOGOUT-005",
  "module": "登出",
  "case_type": "functional",
  "preconditions": "App已登录",
  "priority": "high",
  "test_case_steps": [
   {
    "step": "在App设置页点击\"退出登录\"",
    "result": "页面跳转至登录页"
   },
   {
    "step": "杀掉App进程并重新启动",
    "result": "启动后仍停留在登录页，未自动登录"
   },
   {
    "step": "检查App沙盒存储",
    "result": "token及用户敏感数据已清除"
   }
  ],
  "test_data": {
   "端": "iOS/Android",
   "操作": "App内退出登录"
  },
  "remarks": "FP-011 需求FR-04"
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 39. ws-PR-2-pt_cases

- 来源：`workspace/testcase/PR-2/pt_cases.jsonl`　分组：PR-2　用例数：17

```json
[
 {
  "case_number": "TC-PR2-PT-001",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "high",
  "name": "新增配气任务-批次自动生成格式验证",
  "preconditions": "用户已登录标气制备软件，具有配气任务创建权限",
  "test_data": {
   "expected_format": "年月日+3位序号",
   "test_date": "20260728",
   "test_seq": "001"
  },
  "test_case_steps": [
   {
    "step": "1. 点击新增配气任务按钮",
    "result": "弹出新增配气任务窗口，任务批次字段自动填充为当前日期+3位序号（如20260728001）"
   },
   {
    "step": "2. 不修改任务批次，填写模板信息",
    "result": "批次显示格式为8位年月日+3位数字序号"
   },
   {
    "step": "3. 连续创建2个新配气任务，观察批次号变化",
    "result": "第2个任务的批次号顺序号递增1（如001→002）"
   }
  ],
  "remarks": "FP-008 批次自动生成"
 },
 {
  "case_number": "TC-PR2-PT-002",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "high",
  "name": "新增配气任务-批次号允许修改",
  "preconditions": "新增配气任务窗口已打开，批次已自动填充",
  "test_data": {
   "original_batch": "20260728001",
   "modified_batch": "20260728999"
  },
  "test_case_steps": [
   {
    "step": "1. 将自动生成的批次号「20260728001」修改为「20260728999」",
    "result": "批次号输入框可编辑，显示修改后的值"
   },
   {
    "step": "2. 继续填写模板等其他信息",
    "result": "所有字段可正常填写"
   },
   {
    "step": "3. 保存任务",
    "result": "任务创建成功，列表中显示批次号为20260728999"
   }
  ],
  "remarks": "FP-008 批次允许修改"
 },
 {
  "case_number": "TC-PR2-PT-003",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "high",
  "name": "新增配气任务-同天超过999批次边界处理",
  "preconditions": "系统当天已创建了998个配气任务（最后一个批次如20260728998）",
  "test_data": {
   "test_date": "20260728",
   "last_seq": "998",
   "new_seq_999": "999",
   "overflow_seq": "1000"
  },
  "test_case_steps": [
   {
    "step": "1. 创建第999个任务，观察批次号",
    "result": "批次号自动生成为20260728999"
   },
   {
    "step": "2. 再创建一个任务（第1000个）",
    "result": "系统提示「当天任务批次已达上限」或批次号自动变成20260728001（重置）或提示仅允许修改"
   }
  ],
  "remarks": "FP-008 批次999边界"
 },
 {
  "case_number": "TC-PR2-PT-004",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "high",
  "name": "配气模板选择-单选联动显示详情",
  "preconditions": "系统中存在至少2个配气模板（如模板A和模板B）",
  "test_data": {
   "template_A": "模板A",
   "template_B": "模板B"
  },
  "test_case_steps": [
   {
    "step": "1. 在新增配气任务窗口中，点击配气模板下拉框",
    "result": "下拉列表显示所有可用的配气模板名称"
   },
   {
    "step": "2. 选择模板A",
    "result": "气体详情区域自动显示模板A的原始浓度、目标气浓度、流速、计划采气量、气体类型"
   },
   {
    "step": "3. 切换为模板B",
    "result": "气体详情区域更新为模板B的数据"
   },
   {
    "step": "4. 尝试同时选择两个模板",
    "result": "配气模板为单选，无法同时选中两个"
   }
  ],
  "remarks": "FP-009 模板单选联动"
 },
 {
  "case_number": "TC-PR2-PT-005",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "high",
  "name": "TD管号管理-同批次不可重复校验",
  "preconditions": "已创建配气任务批次，TD管号输入框可用",
  "test_data": {
   "td_tube_1": "123456",
   "td_tube_2": "123456"
  },
  "test_case_steps": [
   {
    "step": "1. 在制备序号1输入TD管号123456，点击开始配气",
    "result": "TD管号123456被接受，配气开始"
   },
   {
    "step": "2. 配气完成后点击继续添加，在制备序号2输入相同的TD管号123456",
    "result": "系统提示「该TD管号在同批次中已存在，请使用其他编号」"
   }
  ],
  "remarks": "FP-011 TD管号同批次不可重复"
 },
 {
  "case_number": "TC-PR2-PT-006",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "high",
  "name": "TD管号管理-6位数字格式校验",
  "preconditions": "新增配气任务窗口已打开",
  "test_data": {
   "valid_6digit": "123456",
   "short_input": "12345",
   "letter_input": "12A456",
   "empty_input": ""
  },
  "test_case_steps": [
   {
    "step": "1. 输入5位数字12345",
    "result": "提示TD管号必须为6位数字"
   },
   {
    "step": "2. 输入6位数字123456",
    "result": "输入成功"
   },
   {
    "step": "3. 输入含字母12A456",
    "result": "拒绝字母输入或提示格式错误"
   },
   {
    "step": "4. TD管号留空",
    "result": "非必填字段，可以跳过"
   }
  ],
  "remarks": "FP-011 TD管号6位数字校验"
 },
 {
  "case_number": "TC-PR2-PT-007",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "high",
  "name": "开始配气-TD管号锁定不可修改",
  "preconditions": "新增配气任务窗口已打开，已输入TD管号123456",
  "test_data": {
   "td_tube": "123456"
  },
  "test_case_steps": [
   {
    "step": "1. 在配气准备阶段输入TD管号123456",
    "result": "TD管号输入框可用"
   },
   {
    "step": "2. 点击开始配气",
    "result": "开始配气后，TD管号输入框变为只读/禁用状态"
   },
   {
    "step": "3. 尝试修改TD管号",
    "result": "无法修改TD管号"
   }
  ],
  "remarks": "FP-012 开始配气后TD管号锁定"
 },
 {
  "case_number": "TC-PR2-PT-008",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "high",
  "name": "开始配气-实时显示流速和已采气量",
  "preconditions": "配气任务已创建，点击开始配气",
  "test_data": {
   "td_tube": "123456"
  },
  "test_case_steps": [
   {
    "step": "1. 点击开始配气",
    "result": "页面进入配气中状态，显示当前流速（单位mL/min）和已采气量（单位mL）"
   },
   {
    "step": "2. 观察流速和已采气量数值变化",
    "result": "流速在合理范围内波动，已采气量随时间递增"
   },
   {
    "step": "3. 记录3个时间点的流速和采气量",
    "result": "3个时间点的数据均有所不同，采气量持续增加"
   }
  ],
  "remarks": "FP-012 实时显示"
 },
 {
  "case_number": "TC-PR2-PT-009",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "high",
  "name": "开始配气-不允许关闭页面提示",
  "preconditions": "配气正在进行中",
  "test_data": {
   "td_tube": "123456"
  },
  "test_case_steps": [
   {
    "step": "1. 在配气进行中时，点击浏览器关闭按钮或页面上的返回链接",
    "result": "页面弹出确认提示「配气进行中，关闭页面将导致配气中断，是否确认关闭？」或「配气进行中，请等待配气完成再关闭页面」"
   },
   {
    "step": "2. 选择取消/否",
    "result": "页面保持打开状态，配气继续"
   }
  ],
  "remarks": "FP-012 不允许关闭页面"
 },
 {
  "case_number": "TC-PR2-PT-010",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "medium",
  "name": "制备序号自动生成-按顺序递增",
  "preconditions": "批次已创建，正在进行配气操作",
  "test_data": {
   "first_seq": "1",
   "second_seq": "2"
  },
  "test_case_steps": [
   {
    "step": "1. 观察第一个TD管的制备序号",
    "result": "制备序号显示为1"
   },
   {
    "step": "2. 配气完成后点击继续添加",
    "result": "第二个TD管的制备序号自动变为2"
   },
   {
    "step": "3. 继续添加至第5个",
    "result": "制备序号依次为1,2,3,4,5，未发生跳号或重复"
   }
  ],
  "remarks": "FP-010 制备序号递增"
 },
 {
  "case_number": "TC-PR2-PT-011",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "medium",
  "name": "配气成功-记录加入配气列表",
  "preconditions": "配气正常运行至结束",
  "test_data": {
   "td_tube": "123456"
  },
  "test_case_steps": [
   {
    "step": "1. 等待配气完成",
    "result": "配气状态显示为成功，配气结束时间显示"
   },
   {
    "step": "2. 查看配气列表",
    "result": "该TD管的记录出现在配气列表中，状态标记为「成功」，显示配气时间和实际采气量"
   }
  ],
  "remarks": "FP-013 配气成功"
 },
 {
  "case_number": "TC-PR2-PT-012",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "medium",
  "name": "配气失败-记录加入列表并显示原因",
  "preconditions": "配气过程中出现异常",
  "test_data": {
   "td_tube": "654321",
   "failure_reason": "流量偏差超阈值"
  },
  "test_case_steps": [
   {
    "step": "1. 模拟配气失败（如流量偏差超阈值）",
    "result": "页面提示「配气失败」，显示失败原因"
   },
   {
    "step": "2. 查看配气列表",
    "result": "该TD管记录出现在列表中，状态标记为「失败」，失败原因字段显示具体的失败原因"
   }
  ],
  "remarks": "FP-014 配气失败"
 },
 {
  "case_number": "TC-PR2-PT-013",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "medium",
  "name": "配气失败-支持继续添加",
  "preconditions": "配气失败后页面停留在失败状态",
  "test_data": {
   "td_tube_1": "654321",
   "td_tube_2": "654322"
  },
  "test_case_steps": [
   {
    "step": "1. 配气失败后，页面展示失败信息",
    "result": "显示失败原因和「继续添加」按钮"
   },
   {
    "step": "2. 点击继续添加",
    "result": "新增一个制备序号，可以输入新的TD管号"
   },
   {
    "step": "3. 输入新的TD管号654322并开始配气",
    "result": "新的一轮配气开始"
   }
  ],
  "remarks": "FP-014 继续添加"
 },
 {
  "case_number": "TC-PR2-PT-014",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "medium",
  "name": "配气详情-内容完整性",
  "preconditions": "已创建配气任务且有配气记录",
  "test_data": {
   "task_batch": "20260728001"
  },
  "test_case_steps": [
   {
    "step": "1. 进入配气任务列表，点击查看详情",
    "result": "显示任务详情窗口，包含任务批次、配气模板名称、气体详情（原始浓度、目标浓度、流速、采气量、气体类型）"
   },
   {
    "step": "2. 查看配气列表区域",
    "result": "配气列表显示所有TD管的制备序号、TD管号、配气时间、实际采气量、配气结束时间、状态、失败原因"
   }
  ],
  "remarks": "FP-015 详情完整性"
 },
 {
  "case_number": "TC-PR2-PT-015",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "medium",
  "name": "配气详情-导出PDF报告",
  "preconditions": "查看配气详情窗口已打开",
  "test_data": {
   "task_batch": "20260728001"
  },
  "test_case_steps": [
   {
    "step": "1. 在配气详情窗口中点击导出报告",
    "result": "触发PDF文件下载"
   },
   {
    "step": "2. 打开下载的PDF文件",
    "result": "PDF内容与详情窗口中显示的信息一致，包含任务批次、模板信息、所有TD管的配气记录"
   }
  ],
  "remarks": "FP-015 导出PDF"
 },
 {
  "case_number": "TC-PR2-PT-016",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "medium",
  "name": "配气任务列表-按创建时间倒序",
  "preconditions": "系统中存在多个不同日期的配气任务",
  "test_data": {
   "task_1_time": "20260728",
   "task_2_time": "20260727"
  },
  "test_case_steps": [
   {
    "step": "1. 打开任务管理页面",
    "result": "默认展示批次维度的配气任务列表"
   },
   {
    "step": "2. 观察列表排序",
    "result": "列表按批次创建时间倒序排列，最新的任务排在最前面"
   },
   {
    "step": "3. 核对相邻两条记录的创建时间",
    "result": "上一条记录的创建时间不早于下一条记录"
   }
  ],
  "remarks": "FP-016 任务列表排序"
 },
 {
  "case_number": "TC-PR2-PT-017",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "medium",
  "name": "配气任务列表-已采管数统计",
  "preconditions": "某批次有5根TD管，3根成功2根失败",
  "test_data": {
   "total_tubes": 5,
   "success": 3,
   "failure": 2
  },
  "test_case_steps": [
   {
    "step": "1. 在任务列表中查看该批次",
    "result": "已采管数字段显示为5（成功3+失败2）"
   },
   {
    "step": "2. 点击详情验证",
    "result": "配气列表中正确显示3条成功和2条失败的记录"
   }
  ],
  "remarks": "FP-016 已采管数统计"
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 40. ws-test_cases_flow

- 来源：`workspace/testcase/test_cases_flow.jsonl`　分组：(root)　用例数：10

```json
[
 {
  "case_number": "TC-PR-FLOW-001",
  "name": "新建检测任务后默认进入「待接收」状态",
  "module": "METRIX呼析云·任务状态流转",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "1. 用户已登录METRIX呼析云系统且具有任务创建权限\n2. 系统处于正常运行状态",
  "test_data": {
   "task_name": "病理切片检测-20240115-001",
   "sample_type": "病理组织切片",
   "sample_count": 5,
   "patient_id": "P20240115001",
   "department": "病理科",
   "requester": "张医生",
   "expected_initial_status": "待接收"
  },
  "test_case_steps": [
   {
    "step": "1. 进入「任务管理」页面，点击「新建任务」按钮",
    "result": "弹出新建任务表单窗口"
   },
   {
    "step": "2. 填写任务信息：任务名称「病理切片检测-20240115-001」、样本类型「病理组织切片」、样本数量「5」、患者ID「P20240115001」、申请科室「病理科」",
    "result": "所有必填字段填写完整，表单验证通过"
   },
   {
    "step": "3. 点击「提交」按钮创建任务",
    "result": "系统提示「任务创建成功」，任务列表中出现新记录"
   },
   {
    "step": "4. 在任务列表中查看新建任务的状态字段",
    "result": "任务状态显示为「待接收」，且状态标签底色为灰色/待处理色，与需求规格一致"
   }
  ],
  "remarks": "关联需求 FP-014"
 },
 {
  "case_number": "TC-PR-FLOW-002",
  "name": "「待接收」状态下执行样本接收操作后状态变更为「待检测」",
  "module": "METRIX呼析云·任务状态流转",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "1. 系统中存在一条状态为「待接收」的检测任务（TC-PR-FLOW-001执行后遗留）\n2. 当前用户具有样本接收操作权限",
  "test_data": {
   "task_id": "TASK-20240115-001",
   "current_status": "待接收",
   "sample_list": [
    {
     "sample_id": "SMP-001",
     "sample_name": "病理切片-A1",
     "sample_status": "已接收"
    },
    {
     "sample_id": "SMP-002",
     "sample_name": "病理切片-B2",
     "sample_status": "已接收"
    }
   ],
   "receiver": "李技师",
   "receive_time": "2024-01-15 10:30:00",
   "expected_new_status": "待检测"
  },
  "test_case_steps": [
   {
    "step": "1. 在任务列表中找到状态为「待接收」的任务，点击「样本接收」按钮",
    "result": "弹出样本接收确认对话框，显示待接收样本清单及数量"
   },
   {
    "step": "2. 核对样本信息无误后，在接收对话框中点击「确认接收」",
    "result": "系统提示「样本接收成功」，任务状态标签更新为「待检测」"
   },
   {
    "step": "3. 刷新任务列表页面，查看该任务的最新状态",
    "result": "任务状态持久化为「待检测」，状态标签底色变为蓝色/检测中色，操作按钮区域布局同步更新"
   },
   {
    "step": "4. 点击该任务进入详情页，查看状态变更记录",
    "result": "状态变更日志中新增一条记录：「待接收 → 待检测」，操作人为「李技师」，时间戳与接收时间一致"
   }
  ],
  "remarks": "关联需求 FP-014"
 },
 {
  "case_number": "TC-PR-FLOW-003",
  "name": "「待接收」状态下取消任务后状态变更为「已取消」",
  "module": "METRIX呼析云·任务状态流转",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "1. 系统中存在一条状态为「待接收」的检测任务\n2. 当前用户具有任务取消权限",
  "test_data": {
   "task_id": "TASK-20240115-002",
   "current_status": "待接收",
   "task_name": "血液样本检测-20240115-002",
   "cancel_reason": "患者取消检测申请",
   "expected_new_status": "已取消",
   "expected_cancel_time": "系统当前时间"
  },
  "test_case_steps": [
   {
    "step": "1. 在任务列表中找到待接收状态的任务，点击「取消任务」按钮",
    "result": "弹出取消确认对话框，包含取消原因输入框"
   },
   {
    "step": "2. 在取消原因输入框中填写「患者取消检测申请」，点击「确定取消」",
    "result": "系统提示「任务已取消」，任务状态更新为「已取消」，状态标签底色变为红色/已取消色"
   },
   {
    "step": "3. 刷新页面后在任务列表中确认状态",
    "result": "任务状态持久化为「已取消」，该任务不再出现在待办任务列表中，仅可在「已取消」过滤条件下查看"
   },
   {
    "step": "4. 进入任务详情页查看状态变更日志",
    "result": "状态变更日志记录：「待接收 → 已取消」，取消原因：「患者取消检测申请」，包含操作时间戳"
   }
  ],
  "remarks": "关联需求 FP-014"
 },
 {
  "case_number": "TC-PR-FLOW-004",
  "name": "「待接收」状态下可编辑任务基本信息",
  "module": "METRIX呼析云·任务状态流转",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "1. 系统中存在一条状态为「待接收」的检测任务\n2. 当前用户具有任务编辑权限",
  "test_data": {
   "task_id": "TASK-20240115-003",
   "original_task_name": "常规检测-20240115-003",
   "original_sample_count": 3,
   "edit_task_name": "常规检测加急-20240115-003",
   "edit_sample_count": 5,
   "edit_notes": "患者要求加急处理",
   "current_status": "待接收"
  },
  "test_case_steps": [
   {
    "step": "1. 在任务列表中找到待接收状态的任务，点击「编辑」按钮",
    "result": "进入任务编辑页面，表单中预填充了当前任务的所有字段值"
   },
   {
    "step": "2. 修改任务名称为「常规检测加急-20240115-003」，样本数量从3改为5，备注添加「患者要求加急处理」",
    "result": "编辑表单中的所有字段均可正常修改，无只读限制"
   },
   {
    "step": "3. 点击「保存」按钮提交修改",
    "result": "系统提示「任务更新成功」"
   },
   {
    "step": "4. 在任务列表中刷新查看该任务",
    "result": "任务名称已更新为「常规检测加急-20240115-003」，样本数量显示为5，备注内容正确显示"
   },
   {
    "step": "5. 确认任务状态在编辑后未发生变更",
    "result": "任务状态仍然为「待接收」，编辑操作不影响状态流转"
   }
  ],
  "remarks": "关联需求 FP-014"
 },
 {
  "case_number": "TC-PR-FLOW-005",
  "name": "「待接收」状态下操作按钮权限验证（可取消/可接收/可编辑）",
  "module": "METRIX呼析云·任务状态流转",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "1. 系统中存在一条状态为「待接收」的检测任务\n2. 当前用户同时具有任务取消、样本接收、任务编辑权限",
  "test_data": {
   "task_id": "TASK-20240115-004",
   "current_status": "待接收",
   "expected_available_buttons": [
    "样本接收",
    "取消任务",
    "编辑"
   ],
   "expected_disabled_buttons": [
    "开始检测",
    "复核结果",
    "生成报告"
   ]
  },
  "test_case_steps": [
   {
    "step": "1. 进入任务列表，定位状态为「待接收」的任务所在行",
    "result": "任务行显示操作按钮区域"
   },
   {
    "step": "2. 检查该任务可用的操作按钮列表",
    "result": "操作区域中可见「样本接收」「取消任务」「编辑」三个按钮，均为可点击状态（非灰色禁用）"
   },
   {
    "step": "3. 检查该任务不可用的操作按钮列表",
    "result": "操作区域中「开始检测」「复核结果」「生成报告」等后续操作按钮不可见或被灰色禁用"
   },
   {
    "step": "4. 依次点击「样本接收」「取消任务」「编辑」三个按钮，验证功能可用",
    "result": "「样本接收」弹出样本接收对话框；「取消任务」弹出取消确认对话框；「编辑」跳转编辑页面，三个操作均正常触发"
   },
   {
    "step": "5. 使用无取消权限的账号登录，重新查看该任务的操作按钮",
    "result": "「取消任务」按钮不可见或灰色禁用，权限控制生效"
   }
  ],
  "remarks": "关联需求 FP-015"
 },
 {
  "case_number": "TC-PR-FLOW-006",
  "name": "「待检测」状态下操作按钮权限验证（仅可取消）",
  "module": "METRIX呼析云·任务状态流转",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "1. 系统中存在一条状态为「待检测」的检测任务（已通过样本接收流转至此状态）\n2. 当前用户具有所有操作按钮的权限",
  "test_data": {
   "task_id": "TASK-20240115-005",
   "current_status": "待检测",
   "received_at": "2024-01-15 10:30:00",
   "expected_available_buttons": [
    "取消任务"
   ],
   "expected_disabled_buttons": [
    "样本接收",
    "编辑",
    "开始检测",
    "复核结果",
    "生成报告"
   ]
  },
  "test_case_steps": [
   {
    "step": "1. 进入任务列表，定位状态为「待检测」的任务所在行",
    "result": "任务行显示操作按钮区域，状态标签为蓝色「待检测」"
   },
   {
    "step": "2. 检查操作按钮列表",
    "result": "操作区域中仅「取消任务」按钮可见且可点击；「样本接收」「编辑」按钮不可见"
   },
   {
    "step": "3. 点击「取消任务」按钮",
    "result": "弹出取消确认对话框，输入原因后确认取消，任务状态变更为「已取消」"
   },
   {
    "step": "4. 以不同权限账号登录（无取消权限但有编辑权限），查看该任务",
    "result": "「取消任务」按钮不可见或灰色禁用，且「编辑」按钮同样不可见，符合权限控制规范"
   }
  ],
  "remarks": "关联需求 FP-015"
 },
 {
  "case_number": "TC-PR-FLOW-007",
  "name": "状态变更后操作按钮动态切换验证（待接收→待检测）",
  "module": "METRIX呼析云·任务状态流转",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "1. 系统中存在一条状态为「待接收」的检测任务\n2. 当前用户具有样本接收权限",
  "test_data": {
   "task_id": "TASK-20240115-006",
   "before_status": "待接收",
   "after_status": "待检测",
   "before_buttons": {
    "sample_receive": "可用",
    "cancel": "可用",
    "edit": "可用",
    "start_test": "不可用"
   },
   "after_buttons": {
    "sample_receive": "不可见",
    "cancel": "可用",
    "edit": "不可见",
    "start_test": "不可用"
   }
  },
  "test_case_steps": [
   {
    "step": "1. 定位待接收状态任务，截图保存当前操作按钮布局作为基线",
    "result": "操作区域包含「样本接收」「取消任务」「编辑」三个可用按钮，无其他状态相关按钮"
   },
   {
    "step": "2. 执行样本接收操作，使任务状态从「待接收」变更为「待检测」",
    "result": "系统提示「样本接收成功」，状态标签从灰色「待接收」变为蓝色「待检测」"
   },
   {
    "step": "3. 状态变更后立即观察操作按钮区域的变化",
    "result": "「样本接收」按钮消失；「编辑」按钮消失；仅「取消任务」按钮保留可用"
   },
   {
    "step": "4. 在不刷新页面的情况下（前端响应式更新），确认按钮状态",
    "result": "操作按钮已随状态变更动态更新，无需刷新页面即可看到变化，符合前端响应式设计要求"
   },
   {
    "step": "5. 刷新页面后再次确认",
    "result": "刷新后按钮布局与第3步一致，证明变更已持久化保存"
   }
  ],
  "remarks": "关联需求 FP-015"
 },
 {
  "case_number": "TC-PR-FLOW-008",
  "name": "「待接收」→「待检测」→「已取消」完整流转链路验证",
  "module": "METRIX呼析云·任务状态流转",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "1. 系统中存在一条状态为「待接收」的检测任务\n2. 当前用户具有样本接收和取消任务的权限",
  "test_data": {
   "task_id": "TASK-20240115-007",
   "task_name": "流转链路测试-20240115-007",
   "initial_status": "待接收",
   "intermediate_status": "待检测",
   "final_status": "已取消",
   "receive_operator": "王技师",
   "cancel_operator": "王技师",
   "cancel_reason": "样本不合格，退回重采"
  },
  "test_case_steps": [
   {
    "step": "1. 确认任务初始状态为「待接收」",
    "result": "任务状态标签为灰色「待接收」，操作按钮包含「样本接收」「取消任务」「编辑」"
   },
   {
    "step": "2. 执行样本接收操作",
    "result": "状态从「待接收」变更为「待检测」，操作按钮仅剩「取消任务」"
   },
   {
    "step": "3. 在「待检测」状态下执行取消操作，填写取消原因「样本不合格，退回重采」",
    "result": "状态从「待检测」变更为「已取消」，操作按钮全部消失或置为只读状态"
   },
   {
    "step": "4. 查看完整状态变更日志",
    "result": "变更日志按时间顺序显示三条记录：①「新建 → 待接收」②「待接收 → 待检测」③「待检测 → 已取消」，每条记录含操作人和时间戳"
   }
  ],
  "remarks": "关联需求 FP-015"
 },
 {
  "case_number": "TC-PR-FLOW-009",
  "name": "「待接收」状态下批量取消/接收操作权限验证",
  "module": "METRIX呼析云·任务状态流转",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "1. 系统中存在至少3条状态为「待接收」的检测任务\n2. 当前用户具有批量操作权限",
  "test_data": {
   "task_ids": [
    "TASK-20240115-008",
    "TASK-20240115-009",
    "TASK-20240115-010"
   ],
   "batch_operation": "批量接收",
   "current_status": "待接收",
   "expected_after_batch_receive_status": "待检测",
   "expected_after_batch_cancel_status": "已取消"
  },
  "test_case_steps": [
   {
    "step": "1. 在任务列表中勾选3条「待接收」状态的任务",
    "result": "勾选框全部选中，页面顶部出现批量操作工具栏，包含「批量接收」「批量取消」按钮"
   },
   {
    "step": "2. 点击「批量接收」按钮",
    "result": "弹出批量接收确认对话框，显示待接收任务数量和样本汇总信息"
   },
   {
    "step": "3. 确认批量接收",
    "result": "系统提示「批量接收成功，共接收3条任务」，3条任务状态全部变更为「待检测」"
   },
   {
    "step": "4. 重新创建3条待接收任务，勾选后点击「批量取消」",
    "result": "弹出批量取消对话框，填写统一取消原因后确认，3条任务状态全部变更为「已取消」"
   },
   {
    "step": "5. 逐一检查6条任务的最后状态",
    "result": "前3条任务状态为「待检测」，后3条任务状态为「已取消」，批量操作结果一致性100%"
   }
  ],
  "remarks": "关联需求 FP-015"
 },
 {
  "case_number": "TC-PR-FLOW-010",
  "name": "「待检测」状态下取消后任务关闭状态持久化验证",
  "module": "METRIX呼析云·任务状态流转",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "1. 系统中存在一条状态为「待检测」的检测任务\n2. 当前用户具有取消任务权限\n3. 该任务已关联样本数据",
  "test_data": {
   "task_id": "TASK-20240115-011",
   "current_status": "待检测",
   "cancel_reason": "样本溶血，无法检测",
   "associated_samples": [
    "SMP-010",
    "SMP-011"
   ],
   "expected_close_status": "已取消",
   "expected_archive_flag": true
  },
  "test_case_steps": [
   {
    "step": "1. 进入待检测任务详情页，记录关联的样本信息",
    "result": "页面显示2个关联样本：SMP-010、SMP-011，状态均为「已接收待检测」"
   },
   {
    "step": "2. 在任务详情页点击「取消任务」，填写原因「样本溶血，无法检测」",
    "result": "状态变更为「已取消」，页面顶部显示红色状态标签"
   },
   {
    "step": "3. 关闭详情页后重新搜索该任务",
    "result": "该任务仅在「已取消」过滤条件或「全部任务」中可见，不在「待办任务」中出现"
   },
   {
    "step": "4. 重新打开任务详情页，验证关联样本状态",
    "result": "关联样本SMP-010、SMP-011状态更新为「已退回」或「检测取消」，与任务取消状态一致"
   },
   {
    "step": "5. 登出后重新登录系统，再次查看该任务",
    "result": "任务状态仍为「已取消」，样本状态仍为「已退回」，取消操作已持久化保存，不因会话重置而改变"
   },
   {
    "step": "6. 验证该任务无法执行任何后续正向操作",
    "result": "所有操作按钮置灰或隐藏，已取消的任务不可再接收、不可编辑、不可开始检测"
   }
  ],
  "remarks": "关联需求 FP-015"
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 41. ws-PR-1-test_cases_module_01

- 来源：`workspace/testcase/PR-1/test_cases_module_01.jsonl`　分组：PR-1　用例数：3

```json
[
 {
  "case_number": "TC-PR1-LOGIN-001",
  "name": "正确凭据登录成功",
  "module": "登录",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "系统已部署且登录页可正常访问；测试账号 testuser@test.local 已注册且账号状态为正常",
  "test_data": {
   "用户名": "testuser@test.local",
   "密码": "Test@123456",
   "期望登录状态": "成功"
  },
  "test_case_steps": [
   {
    "step": "打开登录页面，在用户名字段输入 testuser@test.local",
    "result": "输入框回显完整用户名 testuser@test.local，无截断或乱码"
   },
   {
    "step": "在密码字段输入 Test@123456",
    "result": "密码以掩码形式显示，输入字符数为 12 位"
   },
   {
    "step": "点击登录按钮",
    "result": "页面跳转至系统首页，右上角显示当前登录用户名 testuser@test.local"
   },
   {
    "step": "通过浏览器开发者工具查看接口 POST /api/auth/login 响应",
    "result": "接口返回 HTTP 200 且 code=0，响应体含长度大于 32 位的 token 字段"
   }
  ],
  "remarks": "REQ-LOGIN-001 登录功能"
 },
 {
  "case_number": "TC-PR1-LOGIN-002",
  "name": "密码错误登录失败",
  "module": "登录",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "测试账号 testuser@test.local 已注册且账号状态为正常；已知该账号正确密码为 Test@123456",
  "test_data": {
   "用户名": "testuser@test.local",
   "密码": "Wrong@9999",
   "期望登录状态": "失败"
  },
  "test_case_steps": [
   {
    "step": "打开登录页面，在用户名字段输入 testuser@test.local",
    "result": "输入框回显完整用户名"
   },
   {
    "step": "在密码字段输入错误密码 Wrong@9999",
    "result": "密码以掩码形式显示"
   },
   {
    "step": "点击登录按钮",
    "result": "页面停留在登录页不跳转，页面显示错误提示“用户名或密码错误”"
   },
   {
    "step": "通过浏览器开发者工具查看接口 POST /api/auth/login 响应",
    "result": "接口返回 HTTP 200 且 code=4001，message 为“用户名或密码错误”，响应中不包含 token 字段"
   }
  ],
  "remarks": "REQ-LOGIN-001 登录功能"
 },
 {
  "case_number": "TC-PR1-LOGIN-003",
  "name": "SQL注入用户名登录被拦截",
  "module": "登录",
  "case_type": "security",
  "priority": "high",
  "preconditions": "登录页可正常访问；系统对用户输入采用参数化查询且具备输入校验防护",
  "test_data": {
   "用户名": "' OR '1'='1",
   "密码": "anything123",
   "攻击载荷类型": "SQL注入"
  },
  "test_case_steps": [
   {
    "step": "打开登录页面，在用户名字段输入 ' OR '1'='1",
    "result": "输入框接受该字符串回显，无页面报错"
   },
   {
    "step": "在密码字段输入 anything123",
    "result": "密码以掩码形式显示"
   },
   {
    "step": "点击登录按钮",
    "result": "页面提示“用户名或密码错误”，停留在登录页不跳转"
   },
   {
    "step": "通过浏览器开发者工具查看接口 POST /api/auth/login 响应",
    "result": "接口返回 HTTP 200 且 code=4001（或 400），响应中不包含任何用户数据记录"
   },
   {
    "step": "查看服务端应用日志",
    "result": "日志中无 SQL 语法异常堆栈，系统进程不崩溃"
   }
  ],
  "remarks": "REQ-LOGIN-001 登录功能 安全用例"
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 42. ws-PR-2-gp_cases

- 来源：`workspace/testcase/PR-2/gp_cases.jsonl`　分组：PR-2　用例数：17

```json
[
 {
  "case_number": "TC-PR2-GP-001",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "critical",
  "name": "新增配气任务-批次自动生成格式验证",
  "preconditions": "用户已登录标气制备软件，具有配气任务创建权限",
  "test_data": {
   "expected_format": "年月日+3位序号",
   "test_date": "20260728",
   "test_seq": "001"
  },
  "test_case_steps": [
   {
    "step": "1. 点击新增配气任务按钮",
    "result": "弹出新增配气任务窗口，任务批次字段自动填充为当前日期+3位序号（如20260728001）"
   },
   {
    "step": "2. 不修改任务批次，填写模板信息",
    "result": "批次显示格式为8位年月日+3位数字序号"
   },
   {
    "step": "3. 连续创建2个新配气任务，观察批次号变化",
    "result": "第2个任务的批次号顺序号递增1（如001→002）"
   }
  ],
  "remarks": "FP-008 批次自动生成"
 },
 {
  "case_number": "TC-PR2-GP-002",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "critical",
  "name": "新增配气任务-批次号允许修改",
  "preconditions": "新增配气任务窗口已打开，批次已自动填充",
  "test_data": {
   "original_batch": "20260728001",
   "modified_batch": "20260728999"
  },
  "test_case_steps": [
   {
    "step": "1. 将自动生成的批次号「20260728001」修改为「20260728999」",
    "result": "批次号输入框可编辑，显示修改后的值"
   },
   {
    "step": "2. 继续填写模板等其他信息",
    "result": "所有字段可正常填写"
   },
   {
    "step": "3. 保存任务",
    "result": "任务创建成功，列表中显示批次号为20260728999"
   }
  ],
  "remarks": "FP-008 批次允许修改"
 },
 {
  "case_number": "TC-PR2-GP-003",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "critical",
  "name": "新增配气任务-同天超过999批次边界处理",
  "preconditions": "系统当天已创建了998个配气任务（最后一个批次如20260728998）",
  "test_data": {
   "test_date": "20260728",
   "last_seq": "998",
   "new_seq_999": "999",
   "overflow_seq": "1000"
  },
  "test_case_steps": [
   {
    "step": "1. 创建第999个任务，观察批次号",
    "result": "批次号自动生成为20260728999"
   },
   {
    "step": "2. 再创建一个任务（第1000个）",
    "result": "系统提示「当天任务批次已达上限」或批次号自动重置"
   }
  ],
  "remarks": "FP-008 批次999边界"
 },
 {
  "case_number": "TC-PR2-GP-004",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "critical",
  "name": "配气模板选择-单选联动显示详情",
  "preconditions": "系统中存在至少2个配气模板（如模板A和模板B）",
  "test_data": {
   "template_A": "模板A",
   "template_B": "模板B"
  },
  "test_case_steps": [
   {
    "step": "1. 在新增配气任务窗口中，点击配气模板下拉框",
    "result": "下拉列表显示所有可用的配气模板名称"
   },
   {
    "step": "2. 选择模板A",
    "result": "气体详情区域自动显示模板A的原始浓度、目标气浓度、流速、计划采气量、气体类型"
   },
   {
    "step": "3. 切换为模板B",
    "result": "气体详情区域更新为模板B的数据"
   },
   {
    "step": "4. 尝试同时选择两个模板",
    "result": "配气模板为单选，无法同时选中两个"
   }
  ],
  "remarks": "FP-009 模板单选联动"
 },
 {
  "case_number": "TC-PR2-GP-005",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "critical",
  "name": "TD管号管理-同批次不可重复校验",
  "preconditions": "已创建配气任务批次，TD管号输入框可用",
  "test_data": {
   "td_tube_1": "123456",
   "td_tube_2": "123456"
  },
  "test_case_steps": [
   {
    "step": "1. 在制备序号1输入TD管号123456，点击开始配气",
    "result": "TD管号123456被接受，配气开始"
   },
   {
    "step": "2. 配气完成后点击继续添加，在制备序号2输入相同的TD管号123456",
    "result": "系统提示「该TD管号在同批次中已存在，请使用其他编号」"
   }
  ],
  "remarks": "FP-011 TD管号同批次不可重复"
 },
 {
  "case_number": "TC-PR2-GP-006",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "critical",
  "name": "TD管号管理-6位数字格式校验",
  "preconditions": "新增配气任务窗口已打开",
  "test_data": {
   "valid_6digit": "123456",
   "short_input": "12345",
   "letter_input": "12A456"
  },
  "test_case_steps": [
   {
    "step": "1. 输入5位数字12345",
    "result": "提示TD管号必须为6位数字"
   },
   {
    "step": "2. 输入6位数字123456",
    "result": "输入成功"
   },
   {
    "step": "3. 输入含字母12A456",
    "result": "拒绝字母输入或提示格式错误"
   },
   {
    "step": "4. TD管号留空",
    "result": "非必填字段，可以跳过"
   }
  ],
  "remarks": "FP-011 TD管号6位数字校验"
 },
 {
  "case_number": "TC-PR2-GP-007",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "critical",
  "name": "开始配气-TD管号锁定不可修改",
  "preconditions": "新增配气任务窗口已打开，已输入TD管号123456",
  "test_data": {
   "td_tube": "123456"
  },
  "test_case_steps": [
   {
    "step": "1. 在配气准备阶段输入TD管号123456",
    "result": "TD管号输入框可用"
   },
   {
    "step": "2. 点击开始配气",
    "result": "开始配气后，TD管号输入框变为只读/禁用状态"
   },
   {
    "step": "3. 尝试修改TD管号",
    "result": "无法修改TD管号"
   }
  ],
  "remarks": "FP-012 开始配气后TD管号锁定"
 },
 {
  "case_number": "TC-PR2-GP-008",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "critical",
  "name": "开始配气-实时显示流速和已采气量",
  "preconditions": "配气任务已创建，点击开始配气",
  "test_data": {
   "td_tube": "123456"
  },
  "test_case_steps": [
   {
    "step": "1. 点击开始配气",
    "result": "页面进入配气中状态，显示当前流速（单位mL/min）和已采气量（单位mL）"
   },
   {
    "step": "2. 观察流速和已采气量数值变化",
    "result": "流速在合理范围内波动，已采气量随时间递增"
   },
   {
    "step": "3. 记录3个时间点的流速和采气量",
    "result": "3个时间点的数据均有所不同，采气量持续增加"
   }
  ],
  "remarks": "FP-012 实时显示"
 },
 {
  "case_number": "TC-PR2-GP-009",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "critical",
  "name": "开始配气-不允许关闭页面提示",
  "preconditions": "配气正在进行中",
  "test_data": {
   "td_tube": "123456"
  },
  "test_case_steps": [
   {
    "step": "1. 在配气进行中时，点击浏览器关闭按钮或页面上的返回链接",
    "result": "页面弹出确认提示「配气进行中，关闭页面将导致配气中断，是否确认关闭？」"
   },
   {
    "step": "2. 选择取消/否",
    "result": "页面保持打开状态，配气继续"
   }
  ],
  "remarks": "FP-012 不允许关闭页面"
 },
 {
  "case_number": "TC-PR2-GP-010",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "medium",
  "name": "制备序号自动生成-按顺序递增",
  "preconditions": "批次已创建，正在进行配气操作",
  "test_data": {
   "first_seq": "1",
   "second_seq": "2"
  },
  "test_case_steps": [
   {
    "step": "1. 观察第一个TD管的制备序号",
    "result": "制备序号显示为1"
   },
   {
    "step": "2. 配气完成后点击继续添加",
    "result": "第二个TD管的制备序号自动变为2"
   },
   {
    "step": "3. 继续添加至第5个",
    "result": "制备序号依次为1,2,3,4,5，未发生跳号或重复"
   }
  ],
  "remarks": "FP-010 制备序号递增"
 },
 {
  "case_number": "TC-PR2-GP-011",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "medium",
  "name": "配气成功-记录加入配气列表",
  "preconditions": "配气正常运行至结束",
  "test_data": {
   "td_tube": "123456"
  },
  "test_case_steps": [
   {
    "step": "1. 等待配气完成",
    "result": "配气状态显示为成功，配气结束时间显示"
   },
   {
    "step": "2. 查看配气列表",
    "result": "该TD管的记录出现在配气列表中，状态标记为「成功」，显示配气时间和实际采气量"
   }
  ],
  "remarks": "FP-013 配气成功"
 },
 {
  "case_number": "TC-PR2-GP-012",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "medium",
  "name": "配气失败-记录加入列表并显示原因",
  "preconditions": "配气过程中出现异常",
  "test_data": {
   "td_tube": "654321",
   "failure_reason": "流量偏差超阈值"
  },
  "test_case_steps": [
   {
    "step": "1. 模拟配气失败（如流量偏差超阈值）",
    "result": "页面提示「配气失败」，显示失败原因"
   },
   {
    "step": "2. 查看配气列表",
    "result": "该TD管记录出现在列表中，状态标记为「失败」，失败原因字段显示具体的失败原因"
   }
  ],
  "remarks": "FP-014 配气失败"
 },
 {
  "case_number": "TC-PR2-GP-013",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "medium",
  "name": "配气失败-支持继续添加",
  "preconditions": "配气失败后页面停留在失败状态",
  "test_data": {
   "td_tube_1": "654321",
   "td_tube_2": "654322"
  },
  "test_case_steps": [
   {
    "step": "1. 配气失败后，页面展示失败信息",
    "result": "显示失败原因和「继续添加」按钮"
   },
   {
    "step": "2. 点击继续添加",
    "result": "新增一个制备序号，可以输入新的TD管号"
   },
   {
    "step": "3. 输入新的TD管号654322并开始配气",
    "result": "新的一轮配气开始"
   }
  ],
  "remarks": "FP-014 继续添加"
 },
 {
  "case_number": "TC-PR2-GP-014",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "medium",
  "name": "配气详情-内容完整性",
  "preconditions": "已创建配气任务且有配气记录",
  "test_data": {
   "task_batch": "20260728001"
  },
  "test_case_steps": [
   {
    "step": "1. 进入配气任务列表，点击查看详情",
    "result": "显示任务详情窗口，包含任务批次、配气模板名称、气体详情"
   },
   {
    "step": "2. 查看配气列表区域",
    "result": "配气列表显示所有TD管的制备序号、TD管号、配气时间、实际采气量、配气结束时间、状态、失败原因"
   }
  ],
  "remarks": "FP-015 详情完整性"
 },
 {
  "case_number": "TC-PR2-GP-015",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "medium",
  "name": "配气详情-导出PDF报告",
  "preconditions": "查看配气详情窗口已打开",
  "test_data": {
   "task_batch": "20260728001"
  },
  "test_case_steps": [
   {
    "step": "1. 在配气详情窗口中点击导出报告",
    "result": "触发PDF文件下载"
   },
   {
    "step": "2. 打开下载的PDF文件",
    "result": "PDF内容与详情窗口中显示的信息一致"
   }
  ],
  "remarks": "FP-015 导出PDF"
 },
 {
  "case_number": "TC-PR2-GP-016",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "medium",
  "name": "配气任务列表-按创建时间倒序",
  "preconditions": "系统中存在多个不同日期的配气任务",
  "test_data": {
   "task_1_time": "20260728",
   "task_2_time": "20260727"
  },
  "test_case_steps": [
   {
    "step": "1. 打开任务管理页面",
    "result": "默认展示批次维度的配气任务列表"
   },
   {
    "step": "2. 观察列表排序",
    "result": "列表按批次创建时间倒序排列，最新的任务排在最前面"
   },
   {
    "step": "3. 核对相邻两条记录的创建时间",
    "result": "上一条记录的创建时间不早于下一条记录"
   }
  ],
  "remarks": "FP-016 任务列表排序"
 },
 {
  "case_number": "TC-PR2-GP-017",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "medium",
  "name": "配气任务列表-已采管数统计",
  "preconditions": "某批次有5根TD管，3根成功2根失败",
  "test_data": {
   "total_tubes": 5,
   "success": 3,
   "failure": 2
  },
  "test_case_steps": [
   {
    "step": "1. 在任务列表中查看该批次",
    "result": "已采管数字段显示为5（成功3+失败2）"
   },
   {
    "step": "2. 点击详情验证",
    "result": "配气列表中正确显示3条成功和2条失败的记录"
   }
  ],
  "remarks": "FP-016 已采管数统计"
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 43. ws-标气管理_测试用例

- 来源：`workspace/testcase/标气管理_测试用例.jsonl`　分组：(root)　用例数：26

```json
[
 {
  "name": "标气列表-正常展示所有字段",
  "case_number": "TC-BQ-LIST-001",
  "module": "标气列表展示",
  "priority": "critical",
  "test_data": {
   "状态": "正常",
   "标气ID": "SGP2026061701008010",
   "气体类型": "SG17A-2ppb",
   "配气方式": "苏玛罐-TD管配气",
   "存储容器": "TD管",
   "制备序号": "12",
   "容器ID": "328818"
  },
  "test_case_steps": [
   {
    "step": "登录管理后台，进入 资产管理 > 标气管理",
    "result": "页面正常加载，左侧菜单高亮显示'标气管理'"
   },
   {
    "step": "观察标气列表表格",
    "result": "列表展示以下字段列：状态、标气ID、气体类型、配气方式、存储容器、制备序号、容器ID，每行数据完整可读"
   },
   {
    "step": "核对列表数据与数据库中标气记录一致",
    "result": "列表数据与数据库记录完全一致，无遗漏或错误"
   }
  ]
 },
 {
  "name": "标气列表-分页展示",
  "case_number": "TC-BQ-LIST-002",
  "module": "标气列表展示",
  "priority": "high",
  "test_data": {
   "每页条数": "默认20条",
   "总记录数": ">20条"
  },
  "test_case_steps": [
   {
    "step": "进入标气管理列表页，确认列表数据超过一页",
    "result": "列表底部显示分页组件（页码、上一页/下一页按钮）"
   },
   {
    "step": "点击第2页",
    "result": "列表刷新显示第2页数据，当前页码高亮为2"
   },
   {
    "step": "点击上一页返回第1页",
    "result": "列表回到第1页数据，当前页码高亮为1"
   },
   {
    "step": "切换每页显示条数（如50条/页）",
    "result": "列表按新条数重新加载，分页组件同步更新"
   }
  ]
 },
 {
  "name": "标气列表-列表为空",
  "case_number": "TC-BQ-LIST-003",
  "module": "标气列表展示",
  "priority": "high",
  "test_data": {
   "标气列表": "空"
  },
  "test_case_steps": [
   {
    "step": "在无标气数据的环境下进入标气管理",
    "result": "列表展示空状态提示，如'暂无数据'或空表格"
   },
   {
    "step": "检查分页组件",
    "result": "分页组件显示总数为0，无页码显示"
   }
  ]
 },
 {
  "name": "标气列表-字段排序验证",
  "case_number": "TC-BQ-LIST-004",
  "module": "标气列表展示",
  "priority": "medium",
  "test_data": {
   "排序字段": "标气ID",
   "排序方式": "升序/降序"
  },
  "test_case_steps": [
   {
    "step": "点击'标气ID'列表头",
    "result": "列表按标气ID升序排列，表头显示升序标记"
   },
   {
    "step": "再次点击'标气ID'列表头",
    "result": "列表按标气ID降序排列，表头显示降序标记"
   },
   {
    "step": "点击'状态'列表头",
    "result": "列表按状态排序"
   }
  ]
 },
 {
  "name": "标气列表-长列表数据加载性能",
  "case_number": "TC-BQ-LIST-005",
  "module": "标气列表展示",
  "priority": "medium",
  "test_data": {
   "标气数量": "1000条"
  },
  "test_case_steps": [
   {
    "step": "预置1000条标气数据，进入标气管理列表",
    "result": "列表在3秒内完成加载并展示数据"
   },
   {
    "step": "快速翻页至末页",
    "result": "每页切换响应时间不超过2秒"
   }
  ]
 },
 {
  "name": "标气详情-查看基本信息",
  "case_number": "TC-BQ-DETAIL-001",
  "module": "标气详情查看",
  "priority": "high",
  "test_data": {
   "标气ID": "SGP2026061701008010",
   "气体类型": "SG17A-2ppb",
   "配气方式": "苏玛罐-TD管配气",
   "存储容器": "TD管",
   "容器ID": "328818",
   "批次": "2026061701008",
   "生产日期": "2026/06/18",
   "配气人": "谢雪妹"
  },
  "test_case_steps": [
   {
    "step": "在标气管理列表中点击一条标气记录",
    "result": "弹出标气详情弹窗，标题显示标气ID"
   },
   {
    "step": "查看'基本信息'Tab页",
    "result": "展示以下字段及对应值：气体类型、配气方式、存储容器、容器ID、批次、生产日期、存储位置、配气人、采样流速、采样耗时、备注"
   },
   {
    "step": "核对各字段值与数据库记录一致",
    "result": "所有字段值正确展示，无缺失或错误"
   }
  ]
 },
 {
  "name": "标气详情-查看使用记录",
  "case_number": "TC-BQ-DETAIL-002",
  "module": "标气详情查看",
  "priority": "high",
  "test_data": {
   "标气ID": "SGP2026061701008010",
   "使用记录": "已绑定任务"
  },
  "test_case_steps": [
   {
    "step": "在标气详情弹窗中点击'使用记录'Tab",
    "result": "切换到使用记录页面，展示该标气的使用记录列表"
   },
   {
    "step": "查看使用记录内容",
    "result": "使用记录包含：绑定任务ID、任务类型、绑定时间等字段"
   }
  ]
 },
 {
  "name": "标气详情-无使用记录",
  "case_number": "TC-BQ-DETAIL-003",
  "module": "标气详情查看",
  "priority": "medium",
  "test_data": {
   "标气ID": "SGP2026061701008001",
   "使用记录": "无"
  },
  "test_case_steps": [
   {
    "step": "选择一条未绑定任务的标气，打开详情弹窗",
    "result": "弹窗正常展示基本信息"
   },
   {
    "step": "点击'使用记录'Tab",
    "result": "使用记录页面展示空状态提示，如'暂无使用记录'"
   }
  ]
 },
 {
  "name": "标气详情-弹窗关闭",
  "case_number": "TC-BQ-DETAIL-004",
  "module": "标气详情查看",
  "priority": "medium",
  "test_data": {
   "标气ID": "SGP2026061701008010"
  },
  "test_case_steps": [
   {
    "step": "打开标气详情弹窗",
    "result": "弹窗正常展示"
   },
   {
    "step": "点击弹窗右上角'X'关闭按钮",
    "result": "弹窗关闭，返回标气管理列表页"
   },
   {
    "step": "再次点击同一标气记录",
    "result": "弹窗重新打开，数据正常展示"
   }
  ]
 },
 {
  "name": "标气详情-作废选项状态",
  "case_number": "TC-BQ-DETAIL-005",
  "module": "标气详情查看",
  "priority": "medium",
  "test_data": {
   "标气ID": "SGP2026061701008010",
   "作废选项": "红色叉号标记"
  },
  "test_case_steps": [
   {
    "step": "打开标气详情弹窗，观察'作废'选项",
    "result": "作废选项上显示红色叉号标记"
   },
   {
    "step": "尝试点击作废选项",
    "result": "根据业务规则，确认作废操作是否可执行（需澄清）"
   }
  ]
 },
 {
  "name": "标气状态-绑定任务后自动变更为已用",
  "case_number": "TC-BQ-STATUS-001",
  "module": "状态自动变更",
  "priority": "critical",
  "test_data": {
   "标气ID": "SGP2026061701008001",
   "初始状态": "正常",
   "绑定任务": "实验任务TASK-001"
  },
  "test_case_steps": [
   {
    "step": "确认标气SGP2026061701008001当前状态为'正常'",
    "result": "状态显示为'正常'"
   },
   {
    "step": "将该标气绑定到任务TASK-001",
    "result": "绑定操作成功"
   },
   {
    "step": "返回标气管理列表，查看该标气的状态",
    "result": "标气状态自动变更为'已用'"
   },
   {
    "step": "打开该标气详情弹窗，查看使用记录",
    "result": "使用记录Tab中新增一条记录，记录绑定任务TASK-001的信息"
   }
  ]
 },
 {
  "name": "标气状态-绑定任务后增加使用记录",
  "case_number": "TC-BQ-STATUS-002",
  "module": "状态自动变更",
  "priority": "high",
  "test_data": {
   "标气ID": "SGP2026061701008002",
   "绑定任务": "任务TASK-002"
  },
  "test_case_steps": [
   {
    "step": "将标气SGP2026061701008002绑定到任务TASK-002",
    "result": "绑定成功"
   },
   {
    "step": "打开标气详情弹窗，切换到'使用记录'Tab",
    "result": "使用记录列表展示新增记录，包含任务ID、操作时间、操作人等信息"
   },
   {
    "step": "核对使用记录内容与绑定操作一致",
    "result": "使用记录中的任务ID、操作时间与绑定操作匹配"
   }
  ]
 },
 {
  "name": "标气状态-已用标气再次绑定任务",
  "case_number": "TC-BQ-STATUS-003",
  "module": "状态自动变更",
  "priority": "high",
  "test_data": {
   "标气ID": "SGP2026061701008001",
   "当前状态": "已用",
   "再次绑定任务": "任务TASK-003"
  },
  "test_case_steps": [
   {
    "step": "选择一条状态为'已用'的标气",
    "result": "标气状态显示为'已用'"
   },
   {
    "step": "尝试将该标气绑定到新任务",
    "result": "系统提示该标气已使用，是否继续绑定（根据业务规则确认）"
   },
   {
    "step": "确认绑定",
    "result": "绑定成功或失败（根据业务规则）"
   }
  ]
 },
 {
  "name": "标气状态-手动更改为正常",
  "case_number": "TC-BQ-STATUS-004",
  "module": "状态手动变更",
  "priority": "critical",
  "test_data": {
   "标气ID": "SGP2026061701008001",
   "初始状态": "已用",
   "目标状态": "正常"
  },
  "test_case_steps": [
   {
    "step": "选择一条状态为'已用'的标气",
    "result": "标气状态显示为'已用'"
   },
   {
    "step": "点击状态下拉框，选择'正常'",
    "result": "状态下拉框可选'正常'、'已用'、'作废'三个选项"
   },
   {
    "step": "确认更改",
    "result": "标气状态变更为'正常'，系统不做校验仅记录操作日志"
   },
   {
    "step": "查看操作日志",
    "result": "操作日志记录状态变更：已用→正常，记录操作人和操作时间"
   }
  ]
 },
 {
  "name": "标气状态-手动更改为已用",
  "case_number": "TC-BQ-STATUS-005",
  "module": "状态手动变更",
  "priority": "critical",
  "test_data": {
   "标气ID": "SGP2026061701008003",
   "初始状态": "正常",
   "目标状态": "已用"
  },
  "test_case_steps": [
   {
    "step": "选择一条状态为'正常'的标气",
    "result": "标气状态显示为'正常'"
   },
   {
    "step": "手动将状态改为'已用'",
    "result": "状态变更为'已用'，不做校验"
   },
   {
    "step": "查看操作日志",
    "result": "操作日志记录状态变更：正常→已用"
   }
  ]
 },
 {
  "name": "标气状态-手动更改为作废",
  "case_number": "TC-BQ-STATUS-006",
  "module": "状态手动变更",
  "priority": "critical",
  "test_data": {
   "标气ID": "SGP2026061701008004",
   "初始状态": "正常",
   "目标状态": "作废"
  },
  "test_case_steps": [
   {
    "step": "选择一条状态为'正常'的标气",
    "result": "标气状态显示为'正常'"
   },
   {
    "step": "手动将状态改为'作废'",
    "result": "状态变更为'作废'，不做校验"
   },
   {
    "step": "查看操作日志",
    "result": "操作日志记录状态变更：正常→作废"
   }
  ]
 },
 {
  "name": "标气状态-作废改回正常",
  "case_number": "TC-BQ-STATUS-007",
  "module": "状态手动变更",
  "priority": "high",
  "test_data": {
   "标气ID": "SGP2026061701008005",
   "初始状态": "作废",
   "目标状态": "正常"
  },
  "test_case_steps": [
   {
    "step": "选择一条状态为'作废'的标气",
    "result": "标气状态显示为'作废'"
   },
   {
    "step": "手动将状态从'作废'改为'正常'",
    "result": "状态变更为'正常'，系统不做校验"
   },
   {
    "step": "验证该标气可正常使用",
    "result": "标气可正常用于绑定任务等操作"
   }
  ]
 },
 {
  "name": "标气状态-已用改回正常后绑定任务",
  "case_number": "TC-BQ-STATUS-008",
  "module": "状态手动变更",
  "priority": "high",
  "test_data": {
   "标气ID": "SGP2026061701008006",
   "初始状态": "已用",
   "手动改为": "正常",
   "绑定任务": "任务TASK-004"
  },
  "test_case_steps": [
   {
    "step": "将状态为'已用'的标气手动改为'正常'",
    "result": "状态变更为'正常'"
   },
   {
    "step": "将该标气绑定到新任务TASK-004",
    "result": "绑定成功，状态自动变更为'已用'"
   }
  ]
 },
 {
  "name": "标气编辑-修改基本信息",
  "case_number": "TC-BQ-EDIT-001",
  "module": "标气编辑",
  "priority": "high",
  "test_data": {
   "标气ID": "SGP2026061701008010",
   "修改字段": "存储位置",
   "修改值": "A区-3号柜",
   "备注": "测试编辑功能"
  },
  "test_case_steps": [
   {
    "step": "打开标气详情弹窗，点击'编辑'按钮",
    "result": "弹窗进入编辑模式，各字段变为可编辑状态"
   },
   {
    "step": "修改存储位置为'A区-3号柜'，备注填写'测试编辑功能'",
    "result": "输入框正常响应，字符数限制正常"
   },
   {
    "step": "点击保存",
    "result": "保存成功，弹窗关闭"
   },
   {
    "step": "重新打开该标气详情",
    "result": "存储位置显示为'A区-3号柜'，备注显示'测试编辑功能'"
   }
  ]
 },
 {
  "name": "标气编辑-修改气体类型",
  "case_number": "TC-BQ-EDIT-002",
  "module": "标气编辑",
  "priority": "high",
  "test_data": {
   "标气ID": "SGP2026061701008010",
   "修改字段": "气体类型",
   "新值": "SG17A-5ppb"
  },
  "test_case_steps": [
   {
    "step": "打开标气编辑弹窗",
    "result": "编辑弹窗正常展示"
   },
   {
    "step": "修改气体类型为'SG17A-5ppb'",
    "result": "气体类型下拉框可选，选择后显示新值"
   },
   {
    "step": "保存修改",
    "result": "保存成功"
   },
   {
    "step": "在列表中查看该标气",
    "result": "列表中气体类型字段更新为'SG17A-5ppb'"
   }
  ]
 },
 {
  "name": "标气编辑-取消编辑",
  "case_number": "TC-BQ-EDIT-003",
  "module": "标气编辑",
  "priority": "medium",
  "test_data": {
   "标气ID": "SGP2026061701008010",
   "修改字段": "存储位置",
   "修改值": "B区-1号柜"
  },
  "test_case_steps": [
   {
    "step": "打开标气编辑弹窗，修改存储位置为'B区-1号柜'",
    "result": "输入框显示新值"
   },
   {
    "step": "点击'取消'按钮",
    "result": "编辑弹窗关闭，不保存修改"
   },
   {
    "step": "重新打开标气详情",
    "result": "存储位置仍为原值，未变更为'B区-1号柜'"
   }
  ]
 },
 {
  "name": "标气编辑-采样流速边界值",
  "case_number": "TC-BQ-EDIT-004",
  "module": "标气编辑",
  "priority": "high",
  "test_data": {
   "标气ID": "SGP2026061701008010",
   "采样流速": "0",
   "备注": "边界值测试"
  },
  "test_case_steps": [
   {
    "step": "打开标气编辑，将采样流速设为0",
    "result": "输入成功（根据规则：采样流速不小于0）"
   },
   {
    "step": "将采样流速设为9999.99",
    "result": "输入成功（根据规则：范围0-10000，支持两位小数）"
   },
   {
    "step": "将采样流速设为10000",
    "result": "输入成功（边界值）"
   },
   {
    "step": "将采样流速设为-1",
    "result": "输入失败，系统提示'采样流速不能小于0'"
   },
   {
    "step": "将采样流速设为10001",
    "result": "输入失败，系统提示'采样流速不能超过10000'"
   }
  ]
 },
 {
  "name": "标气编辑-采样耗时边界值",
  "case_number": "TC-BQ-EDIT-005",
  "module": "标气编辑",
  "priority": "high",
  "test_data": {
   "标气ID": "SGP2026061701008010",
   "采样耗时": "0",
   "备注": "边界值测试"
  },
  "test_case_steps": [
   {
    "step": "打开标气编辑，将采样耗时设为0",
    "result": "输入成功"
   },
   {
    "step": "将采样耗时设为99.99",
    "result": "输入成功（边界值）"
   },
   {
    "step": "将采样耗时设为100",
    "result": "输入失败，系统提示'采样耗时不能超过99.99'"
   },
   {
    "step": "将采样耗时设为-1",
    "result": "输入失败，系统提示'采样耗时不能小于0'"
   }
  ]
 },
 {
  "name": "标气编辑-备注长度限制",
  "case_number": "TC-BQ-EDIT-006",
  "module": "标气编辑",
  "priority": "medium",
  "test_data": {
   "标气ID": "SGP2026061701008010",
   "备注": "50个字符的文本"
  },
  "test_case_steps": [
   {
    "step": "打开标气编辑，在备注字段输入50个字符",
    "result": "输入成功"
   },
   {
    "step": "尝试输入第51个字符",
    "result": "无法输入，系统限制50个字符"
   }
  ]
 },
 {
  "name": "标气编辑-SQL注入安全测试",
  "case_number": "TC-BQ-SEC-001",
  "module": "标气编辑",
  "priority": "high",
  "test_data": {
   "标气ID": "SGP2026061701008010",
   "存储位置": "' OR 1=1 --",
   "备注": "<script>alert('XSS')</script>"
  },
  "test_case_steps": [
   {
    "step": "打开标气编辑，在存储位置输入' OR 1=1 --",
    "result": "输入成功"
   },
   {
    "step": "保存修改",
    "result": "保存成功，系统未出现SQL异常"
   },
   {
    "step": "在备注字段输入<script>alert('XSS')</script>",
    "result": "输入成功"
   },
   {
    "step": "保存后重新打开详情",
    "result": "备注内容被转义展示，未执行脚本"
   }
  ]
 },
 {
  "name": "标气编辑-越权操作测试",
  "case_number": "TC-BQ-SEC-002",
  "module": "标气编辑",
  "priority": "high",
  "test_data": {
   "标气ID": "SGP2026061701008010",
   "操作角色": "无编辑权限用户"
  },
  "test_case_steps": [
   {
    "step": "使用无编辑权限的账号登录管理后台",
    "result": "登录成功"
   },
   {
    "step": "进入标气管理，尝试编辑标气",
    "result": "编辑按钮不可见或点击后提示无权限"
   }
  ]
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 44. ws-PR-1-test_cases_module_04_edit

- 来源：`workspace/testcase/PR-1/test_cases_module_04_edit.jsonl`　分组：PR-1　用例数：4

```json
[
 {
  "name": "编辑地点-修改地点类型为检测实验室后保存",
  "case_number": "TC-PR1-EDIT-001",
  "module": "编辑地点",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "系统中存在至少1条地点记录",
  "test_case_steps": [
   {
    "step": "进入地点管理列表页，点击某条记录的编辑按钮",
    "result": "编辑弹窗打开，字段回显原值"
   },
   {
    "step": "将地点类型从原类型修改为：检测实验室",
    "result": "选项选中"
   },
   {
    "step": "点击保存按钮",
    "result": "保存成功，弹窗关闭；列表中该记录的地点类型已更新为检测实验室"
   }
  ],
  "test_data": {
   "地点类型": "原类型→检测实验室",
   "其他字段": "保持不变"
  },
  "remarks": "REQ-变更② FP-005",
  "description": "验证编辑地点可修改地点类型并保存生效"
 },
 {
  "name": "编辑地点-地点ID字段不可编辑只读",
  "case_number": "TC-PR1-EDIT-002",
  "module": "编辑地点",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "系统中存在至少1条地点记录",
  "test_case_steps": [
   {
    "step": "进入地点管理列表页，点击某条记录的编辑按钮",
    "result": "编辑弹窗打开"
   },
   {
    "step": "观察地点ID字段的展示状态",
    "result": "地点ID字段为只读状态（灰化/禁用），无法点击或修改"
   }
  ],
  "test_data": {
   "操作类型": "编辑弹窗地点ID字段状态核对",
   "期望状态": "只读/禁用"
  },
  "remarks": "REQ-变更① FP-005",
  "description": "验证地点ID字段在编辑时不可编辑"
 },
 {
  "name": "编辑地点-修改地点名称后保存成功",
  "case_number": "TC-PR1-EDIT-003",
  "module": "编辑地点",
  "case_type": "functional",
  "priority": "critical",
  "preconditions": "系统中存在至少1条地点记录",
  "test_case_steps": [
   {
    "step": "进入地点管理列表页，点击某条记录的编辑按钮",
    "result": "编辑弹窗打开"
   },
   {
    "step": "将地点名称修改为：广州市第一人民医院采样点",
    "result": "输入正常显示"
   },
   {
    "step": "点击保存按钮",
    "result": "保存成功，弹窗关闭；列表中该记录名称已更新为广州市第一人民医院采样点"
   }
  ],
  "test_data": {
   "地点名称": "广州市第一人民医院采样点"
  },
  "remarks": "REQ-变更① FP-005",
  "description": "验证编辑地点可修改地点名称并保存生效"
 },
 {
  "name": "编辑地点-清空必填地点名称保存失败",
  "case_number": "TC-PR1-EDIT-004",
  "module": "编辑地点",
  "case_type": "functional",
  "priority": "high",
  "preconditions": "系统中存在至少1条地点记录",
  "test_case_steps": [
   {
    "step": "进入地点管理列表页，点击某条记录的编辑按钮",
    "result": "编辑弹窗打开"
   },
   {
    "step": "清空地点名称字段",
    "result": "名称字段为空"
   },
   {
    "step": "点击保存按钮",
    "result": "保存失败，提示请填写地点名称；弹窗不关闭；原记录数据未被修改"
   }
  ],
  "test_data": {
   "地点名称": "清空为空"
  },
  "remarks": "REQ-变更① FP-005",
  "description": "验证编辑时清空必填的地点名称保存失败"
 }
]
```

> 判定：assertability=_ coverage=_ note=

## 45. ws-PR-2-pt_cases_v2

- 来源：`workspace/testcase/PR-2/pt_cases_v2.jsonl`　分组：PR-2　用例数：17

```json
[
 {
  "case_number": "TC-PR2-PT-001",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "critical",
  "name": "新增配气任务-批次自动生成格式验证",
  "preconditions": "用户已登录标气制备软件，具有配气任务创建权限",
  "test_data": {
   "expected_format": "年月日+3位序号",
   "test_date": "20260728",
   "test_seq": "001"
  },
  "test_case_steps": [
   {
    "step": "1. 点击新增配气任务按钮",
    "result": "弹出新增配气任务窗口，任务批次字段自动填充为当前日期+3位序号（如20260728001）"
   },
   {
    "step": "2. 不修改任务批次，填写模板信息",
    "result": "批次显示格式为8位年月日+3位数字序号"
   },
   {
    "step": "3. 连续创建2个新配气任务，观察批次号变化",
    "result": "第2个任务的批次号顺序号递增1（如001→002）"
   }
  ],
  "remarks": "FP-008 批次自动生成"
 },
 {
  "case_number": "TC-PR2-PT-002",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "critical",
  "name": "新增配气任务-批次号允许修改",
  "preconditions": "新增配气任务窗口已打开，批次已自动填充",
  "test_data": {
   "original_batch": "20260728001",
   "modified_batch": "20260728999"
  },
  "test_case_steps": [
   {
    "step": "1. 将自动生成的批次号「20260728001」修改为「20260728999」",
    "result": "批次号输入框可编辑，显示修改后的值"
   },
   {
    "step": "2. 继续填写模板等其他信息",
    "result": "所有字段可正常填写"
   },
   {
    "step": "3. 保存任务",
    "result": "任务创建成功，列表中显示批次号为20260728999"
   }
  ],
  "remarks": "FP-008 批次允许修改"
 },
 {
  "case_number": "TC-PR2-PT-003",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "critical",
  "name": "新增配气任务-同天超过999批次边界处理",
  "preconditions": "系统当天已创建了998个配气任务（最后一个批次如20260728998）",
  "test_data": {
   "test_date": "20260728",
   "last_seq": "998",
   "new_seq_999": "999",
   "overflow_seq": "1000"
  },
  "test_case_steps": [
   {
    "step": "1. 创建第999个任务，观察批次号",
    "result": "批次号自动生成为20260728999"
   },
   {
    "step": "2. 再创建一个任务（第1000个）",
    "result": "系统提示「当天任务批次已达上限」或批次号自动重置"
   }
  ],
  "remarks": "FP-008 批次999边界"
 },
 {
  "case_number": "TC-PR2-PT-004",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "critical",
  "name": "配气模板选择-单选联动显示详情",
  "preconditions": "系统中存在至少2个配气模板（如模板A和模板B）",
  "test_data": {
   "template_A": "模板A",
   "template_B": "模板B"
  },
  "test_case_steps": [
   {
    "step": "1. 在新增配气任务窗口中，点击配气模板下拉框",
    "result": "下拉列表显示所有可用的配气模板名称"
   },
   {
    "step": "2. 选择模板A",
    "result": "气体详情区域自动显示模板A的原始浓度、目标气浓度、流速、计划采气量、气体类型"
   },
   {
    "step": "3. 切换为模板B",
    "result": "气体详情区域更新为模板B的数据"
   },
   {
    "step": "4. 尝试同时选择两个模板",
    "result": "配气模板为单选，无法同时选中两个"
   }
  ],
  "remarks": "FP-009 模板单选联动"
 },
 {
  "case_number": "TC-PR2-PT-005",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "critical",
  "name": "TD管号管理-同批次不可重复校验",
  "preconditions": "已创建配气任务批次，TD管号输入框可用",
  "test_data": {
   "td_tube_1": "123456",
   "td_tube_2": "123456"
  },
  "test_case_steps": [
   {
    "step": "1. 在制备序号1输入TD管号123456，点击开始配气",
    "result": "TD管号123456被接受，配气开始"
   },
   {
    "step": "2. 配气完成后点击继续添加，在制备序号2输入相同的TD管号123456",
    "result": "系统提示「该TD管号在同批次中已存在，请使用其他编号」"
   }
  ],
  "remarks": "FP-011 TD管号同批次不可重复"
 },
 {
  "case_number": "TC-PR2-PT-006",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "critical",
  "name": "TD管号管理-6位数字格式校验",
  "preconditions": "新增配气任务窗口已打开",
  "test_data": {
   "valid_6digit": "123456",
   "short_input": "12345",
   "letter_input": "12A456"
  },
  "test_case_steps": [
   {
    "step": "1. 输入5位数字12345",
    "result": "提示TD管号必须为6位数字"
   },
   {
    "step": "2. 输入6位数字123456",
    "result": "输入成功"
   },
   {
    "step": "3. 输入含字母12A456",
    "result": "拒绝字母输入或提示格式错误"
   },
   {
    "step": "4. TD管号留空",
    "result": "非必填字段，可以跳过"
   }
  ],
  "remarks": "FP-011 TD管号6位数字校验"
 },
 {
  "case_number": "TC-PR2-PT-007",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "critical",
  "name": "开始配气-TD管号锁定不可修改",
  "preconditions": "新增配气任务窗口已打开，已输入TD管号123456",
  "test_data": {
   "td_tube": "123456"
  },
  "test_case_steps": [
   {
    "step": "1. 在配气准备阶段输入TD管号123456",
    "result": "TD管号输入框可用"
   },
   {
    "step": "2. 点击开始配气",
    "result": "开始配气后，TD管号输入框变为只读/禁用状态"
   },
   {
    "step": "3. 尝试修改TD管号",
    "result": "无法修改TD管号"
   }
  ],
  "remarks": "FP-012 开始配气后TD管号锁定"
 },
 {
  "case_number": "TC-PR2-PT-008",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "critical",
  "name": "开始配气-实时显示流速和已采气量",
  "preconditions": "配气任务已创建，点击开始配气",
  "test_data": {
   "td_tube": "123456"
  },
  "test_case_steps": [
   {
    "step": "1. 点击开始配气",
    "result": "页面进入配气中状态，显示当前流速（单位mL/min）和已采气量（单位mL）"
   },
   {
    "step": "2. 观察流速和已采气量数值变化",
    "result": "流速在合理范围内波动，已采气量随时间递增"
   },
   {
    "step": "3. 记录3个时间点的流速和采气量",
    "result": "3个时间点的数据均有所不同，采气量持续增加"
   }
  ],
  "remarks": "FP-012 实时显示"
 },
 {
  "case_number": "TC-PR2-PT-009",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "critical",
  "name": "开始配气-不允许关闭页面提示",
  "preconditions": "配气正在进行中",
  "test_data": {
   "td_tube": "123456"
  },
  "test_case_steps": [
   {
    "step": "1. 在配气进行中时，点击浏览器关闭按钮或页面上的返回链接",
    "result": "页面弹出确认提示「配气进行中，关闭页面将导致配气中断，是否确认关闭？」"
   },
   {
    "step": "2. 选择取消/否",
    "result": "页面保持打开状态，配气继续"
   }
  ],
  "remarks": "FP-012 不允许关闭页面"
 },
 {
  "case_number": "TC-PR2-PT-010",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "medium",
  "name": "制备序号自动生成-按顺序递增",
  "preconditions": "批次已创建，正在进行配气操作",
  "test_data": {
   "first_seq": "1",
   "second_seq": "2"
  },
  "test_case_steps": [
   {
    "step": "1. 观察第一个TD管的制备序号",
    "result": "制备序号显示为1"
   },
   {
    "step": "2. 配气完成后点击继续添加",
    "result": "第二个TD管的制备序号自动变为2"
   },
   {
    "step": "3. 继续添加至第5个",
    "result": "制备序号依次为1,2,3,4,5，未发生跳号或重复"
   }
  ],
  "remarks": "FP-010 制备序号递增"
 },
 {
  "case_number": "TC-PR2-PT-011",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "medium",
  "name": "配气成功-记录加入配气列表",
  "preconditions": "配气正常运行至结束",
  "test_data": {
   "td_tube": "123456"
  },
  "test_case_steps": [
   {
    "step": "1. 等待配气完成",
    "result": "配气状态显示为成功，配气结束时间显示"
   },
   {
    "step": "2. 查看配气列表",
    "result": "该TD管的记录出现在配气列表中，状态标记为「成功」，显示配气时间和实际采气量"
   }
  ],
  "remarks": "FP-013 配气成功"
 },
 {
  "case_number": "TC-PR2-PT-012",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "medium",
  "name": "配气失败-记录加入列表并显示原因",
  "preconditions": "配气过程中出现异常",
  "test_data": {
   "td_tube": "654321",
   "failure_reason": "流量偏差超阈值"
  },
  "test_case_steps": [
   {
    "step": "1. 模拟配气失败（如流量偏差超阈值）",
    "result": "页面提示「配气失败」，显示失败原因"
   },
   {
    "step": "2. 查看配气列表",
    "result": "该TD管记录出现在列表中，状态标记为「失败」，失败原因字段显示具体的失败原因"
   }
  ],
  "remarks": "FP-014 配气失败"
 },
 {
  "case_number": "TC-PR2-PT-013",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "medium",
  "name": "配气失败-支持继续添加",
  "preconditions": "配气失败后页面停留在失败状态",
  "test_data": {
   "td_tube_1": "654321",
   "td_tube_2": "654322"
  },
  "test_case_steps": [
   {
    "step": "1. 配气失败后，页面展示失败信息",
    "result": "显示失败原因和「继续添加」按钮"
   },
   {
    "step": "2. 点击继续添加",
    "result": "新增一个制备序号，可以输入新的TD管号"
   },
   {
    "step": "3. 输入新的TD管号654322并开始配气",
    "result": "新的一轮配气开始"
   }
  ],
  "remarks": "FP-014 继续添加"
 },
 {
  "case_number": "TC-PR2-PT-014",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "medium",
  "name": "配气详情-内容完整性",
  "preconditions": "已创建配气任务且有配气记录",
  "test_data": {
   "task_batch": "20260728001"
  },
  "test_case_steps": [
   {
    "step": "1. 进入配气任务列表，点击查看详情",
    "result": "显示任务详情窗口，包含任务批次、配气模板名称、气体详情"
   },
   {
    "step": "2. 查看配气列表区域",
    "result": "配气列表显示所有TD管的制备序号、TD管号、配气时间、实际采气量、配气结束时间、状态、失败原因"
   }
  ],
  "remarks": "FP-015 详情完整性"
 },
 {
  "case_number": "TC-PR2-PT-015",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "medium",
  "name": "配气详情-导出PDF报告",
  "preconditions": "查看配气详情窗口已打开",
  "test_data": {
   "task_batch": "20260728001"
  },
  "test_case_steps": [
   {
    "step": "1. 在配气详情窗口中点击导出报告",
    "result": "触发PDF文件下载"
   },
   {
    "step": "2. 打开下载的PDF文件",
    "result": "PDF内容与详情窗口中显示的信息一致"
   }
  ],
  "remarks": "FP-015 导出PDF"
 },
 {
  "case_number": "TC-PR2-PT-016",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "medium",
  "name": "配气任务列表-按创建时间倒序",
  "preconditions": "系统中存在多个不同日期的配气任务",
  "test_data": {
   "task_1_time": "20260728",
   "task_2_time": "20260727"
  },
  "test_case_steps": [
   {
    "step": "1. 打开任务管理页面",
    "result": "默认展示批次维度的配气任务列表"
   },
   {
    "step": "2. 观察列表排序",
    "result": "列表按批次创建时间倒序排列，最新的任务排在最前面"
   },
   {
    "step": "3. 核对相邻两条记录的创建时间",
    "result": "上一条记录的创建时间不早于下一条记录"
   }
  ],
  "remarks": "FP-016 任务列表排序"
 },
 {
  "case_number": "TC-PR2-PT-017",
  "module": "配气任务",
  "case_type": "functional",
  "priority": "medium",
  "name": "配气任务列表-已采管数统计",
  "preconditions": "某批次有5根TD管，3根成功2根失败",
  "test_data": {
   "total_tubes": 5,
   "success": 3,
   "failure": 2
  },
  "test_case_steps": [
   {
    "step": "1. 在任务列表中查看该批次",
    "result": "已采管数字段显示为5（成功3+失败2）"
   },
   {
    "step": "2. 点击详情验证",
    "result": "配气列表中正确显示3条成功和2条失败的记录"
   }
  ],
  "remarks": "FP-016 已采管数统计"
 }
]
```

> 判定：assertability=_ coverage=_ note=
