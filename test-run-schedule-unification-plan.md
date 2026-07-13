# 测试运行与调度管理合并改造方案

> 版本：v2.0（已根据代码评审修正）  
> 日期：2026-07-12  
> 范围：前端导航、数据模型、后端 API、执行引擎、测试策略

---

## 1. 背景与目标

### 1.1 现状问题

当前“测试运行”与“调度管理”在项目导航中作为两个独立入口存在，但两者本质上都是围绕 `TestRun` 这一执行实例展开的：

- **测试运行**：对应一次具体执行（`TestRun`，`trigger_type` 可为 `manual` / `scheduled` / `api`）。
- **调度管理**：对应一条触发规则（`TestRunSchedule`），其 `test_run_template` 会在触发时生成新的 `TestRun` 实例。

这种“两张皮”设计带来以下问题：

1. **认知割裂**：用户创建调度后，不清楚生成的执行记录在哪里查看。
2. **入口分散**：需要在两个页面间来回跳转，操作路径长。
3. **展示层未统一**：`trigger_type` 已在模型中存在，但前端未将其作为一级筛选维度。
4. **调度触发路径不规范**：`scheduler_service` 直接操作 ORM 创建 `TestRun`，绕过 `TestRunService`，存在业务逻辑遗漏和行为不一致风险。

### 1.2 改造目标

将“测试运行”升级为**测试执行中心**，使手动执行、定时执行、API 触发三种方式共享同一套执行记录、结果展示和筛选能力；调度规则退化为执行中心内的一种“规则配置视图”，不再独占一级导航入口；同时收敛调度触发路径，强制通过 `TestRunService` 创建执行实例。

---

## 2. 现状分析

### 2.1 前端现状

| 页面 | 路由 | 核心职责 |
|------|------|----------|
| 测试运行列表 | `/projects/{projectId}/test-runs` | 展示 `TestRun` 列表，支持搜索、状态过滤、手动执行、创建 |
| 测试运行详情 | `/projects/{projectId}/test-runs/{runId}` | 展示单次执行详情、脚本作业、报告、日志、重试 |
| 定时调度 | `/projects/{projectId}/test-runs/schedules` | 管理 `TestRunSchedule`，配置触发器和测试运行模板 |

当前“测试运行列表”右上角有一个“调度管理”按钮跳转到调度页；调度页有一个“返回测试运行”按钮返回列表。两个页面表单中均包含脚本选择器、执行环境、执行模式等重复配置。

### 2.2 后端现状

- `TestRun` 模型已包含 `trigger_type` 字段，用于区分手动/定时/API 触发。
- `TestRun` 模型已包含 `scheduled_by` 字段（外键指向 `test_run_schedules.id`，`ondelete=SET NULL`，已建索引），用于记录定时执行的来源调度。
- `TestRunSchedule` 模型包含 `test_run_template`（JSON），用于定义定时生成的 `TestRun` 结构。
- 手动执行入口为 `POST /test-runs/{id}/execute`。
- 调度相关 API 为 `/test-runs/schedules/*`。
- **`scheduler_service._execute_scheduled_run()` 直接创建 `TestRun` 和 `TestRunScriptJob` 对象，未调用 `TestRunService.create()`，也未复用脚本作业创建逻辑。**

### 2.3 执行引擎现状

- 手动执行通过 `TestRunService.execute_test_run()` 触发。
- 调度触发逻辑位于 `scheduler_service`，直接操作模型生成 `TestRun` 并执行。
- API 触发能力已预留字段，但可能与手动/调度执行路径不一致。

---

## 3. 总体方案

### 3.1 核心设计原则

1. **单一事实源**：`TestRun` 是所有执行方式的统一产出和展示单元。
2. **规则与实例分离**：`TestRunSchedule` 只负责“何时、按什么模板生成实例”；执行、结果、报告统一由 `TestRun` 承载。
3. **触发方式显性化**：将 `trigger_type` 提升为前端一级筛选维度。
4. **执行创建路径统一**：所有 `TestRun` 实例的创建必须经过 `TestRunService.create()`，禁止调度服务直接操作 ORM。
5. **最小侵入**：保留现有 API 路由做兼容或重定向，逐步迁移前端页面。

### 3.2 改造后结构

```
测试执行中心 （原“测试运行”入口升级）
├── 全部执行        —— TestRun 全量列表
├── 手动执行        —— trigger_type = manual
├── 定时执行        —— trigger_type = scheduled
├── API 触发        —— trigger_type = api
└── 调度规则        —— TestRunSchedule 管理（原 schedules 页）
```

---

## 4. 数据模型变更

### 4.1 现状说明

`TestRun` 已存在 `scheduled_by` 字段（`UUID`，外键指向 `test_run_schedules.id`，`ondelete=SET NULL`，已建索引），并在调度触发时被正确赋值（`scheduler_service.py:165`）。

### 4.2 字段命名决策（本轮保持 `scheduled_by`）

**最终决策：本轮改造不重命名字段。**

`scheduled_by` 语义上确实不如 `schedule_id` 直观，但当前阶段执行“调度收敛到 Service”是核心且高风险的改造，同时引入 DB 字段重命名会带来不必要的并发风险：

- 重命名涉及外键约束、索引、模型、schema、service/repo、前端类型等多处同步。
- 任一处遗漏可能导致编译失败或运行时静默错误，debug 成本远超字段理解收益。
- 与 APScheduler 回调路径的核心改造并行执行，会扩大回滚范围、模糊问题定位。

**P0 方案（本轮）**：
- DB 字段保持 `scheduled_by` 不变。
- 在 Pydantic Schema 层使用 alias 对外暴露 `schedule_id`：

```python
class TestRunInfo(BaseModel):
    ...
    schedule_id: Optional[UUID] = Field(
        default=None,
        alias="scheduled_by",
        description="来源调度 ID",
    )
    schedule_name: Optional[str] = Field(default=None, description="来源调度名称")
```

前端和 API 响应看到的是 `schedule_id`，后端和 DB 仍然是 `scheduled_by`，双方各得其所。

**P1 方案（稳定后）**：
- 执行中心上线运行 2 周、调度收敛 bug 周期过去后，单独发一个 PR 只做 rename。
- 该 PR 范围单一、回滚清晰、风险隔离。

### 4.3 Schema 层改造

### 4.4 反向关系（可选）

当前仅有外键，无显式 SQLAlchemy `relationship`。若后续需要在 schedule 详情中直接访问 `test_runs`，可补充：

```python
# TestRunSchedule 模型
# test_runs: Mapped[list["TestRun"]] = relationship("TestRun", back_populates="schedule")
```

但本次改造建议先通过 repository 查询实现，避免不必要的关系加载开销。

---

## 5. 后端 API 变更

### 5.1 TestRunList 查询参数新增过滤

在 `list_test_runs` 中新增：

```python
trigger_type: Optional[str] = Query(
    default=None,
    description="触发方式过滤，逗号分隔多值 (manual, scheduled, api)",
)
scheduled_by: Optional[str] = Query(
    default=None,
    description="按来源调度 ID 过滤",
)
```

### 5.2 服务层改造

#### TestRunService 调整

1. **`create()` 方法**：
   - 当 `trigger_type` 为 `scheduled` 时，要求传入 `scheduled_by` 并写入模型。
   - 保持手动/API 触发时 `trigger_type` 正确赋值。
   - 脚本作业创建逻辑已存在，确保所有触发方式共用同一套创建逻辑。

2. **`get_list()` 方法**：
   - 新增 `trigger_types` 和 `scheduled_by` 过滤参数。
   - 返回的 `TestRunListInfo` 通过 Pydantic alias 对外包含 `schedule_id` / `schedule_name`。
   - `schedule_name` 通过 join `test_run_schedules` 表获取，避免 N+1。

3. **`_to_info()` / `_to_list_info()` 方法**：
   - 从 `test_run.scheduled_by` 读取并映射为 `schedule_id`。
   - `schedule_name` 通过 eager load 的 schedule 对象读取。

#### 调度触发逻辑收敛（⚠️ 核心改造）

禁止 `scheduler_service._execute_scheduled_run()` 直接操作 ORM。改造后：

```python
async with async_session_factory() as session:
    service = TestRunService(session)
    # 统一通过 Service 创建 TestRun 和脚本作业
    test_run = await service.create(
        project_identifier,
        TestRunCreate(
            name=template.get("name", f"定时执行 - {schedule.name}"),
            description=template.get("description", schedule.description),
            execution_mode=template.get("execution_mode", "sequential"),
            max_concurrency=template.get("max_concurrency", 5),
            environment_id=template.get("environment_id"),
            scripts=template.get("scripts", []),
            trigger_type=TriggerType.SCHEDULED,
            scheduled_by=str(schedule.id),
        )
    )
    # 统一通过 Service 执行
    await service.execute_test_run(project_identifier, test_run.identifier)
    # 更新调度 last_run_at
    schedule.last_run_at = datetime.utcnow()
    await session.commit()
```

关键要求：
- `scheduler_service` 不再直接 `session.add(TestRun)` 或 `session.add_all(TestRunScriptJob)`。
- `TestRunService.create()` 必须完整处理 scheduled 分支的字段赋值、脚本作业创建、计数更新。
- 增加代码 review/lint 约束：调度服务文件内禁止直接导入 `TestRun` 模型进行创建。

### 5.3 新增/调整 API 端点

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/test-runs?trigger_type=scheduled&scheduled_by=xxx` | 按触发方式和调度过滤 |
| POST | `/test-runs/schedules/{id}/trigger` | 立即手动触发一次调度，生成 TestRun 并执行 |
| GET | `/test-runs/schedules/{id}/runs` | 获取某调度产生的执行历史（分页） |

### 5.4 兼容性

- 保留 `/test-runs/schedules` 所有现有接口，避免外部调用方 break。
- 原 `/test-runs/schedules` 前端路由做前端级重定向（Next.js `redirect('/test-runs?tab=schedules')`），而非 HTTP 302。

---

## 6. 前端交互改造

### 6.1 导航入口合并

将项目侧边栏/导航中的“测试运行”升级为“测试执行”，移除独立的“调度管理”入口。

推荐页面结构：

```
/projects/{projectId}/test-runs
├── Tabs: 全部 | 手动 | 定时 | API | 调度规则
├── 列表区：展示当前 Tab 对应的 TestRun
└── 操作区：新建执行 / 新建定时规则
```

### 6.2 测试运行列表页改造

基于现有 `ui/app/projects/[projectId]/test-runs/page.tsx` 调整：

1. **增加触发方式 Tab 栏**：
   - 全部 / 手动 / 定时 / API
   - 选中“定时”时，列表仅展示 `trigger_type === "scheduled"` 的执行。

2. **Tab 状态与 URL 同步**：
   - Tab 选中状态使用 URL 查询参数 `?tab=scheduled`。
   - 不同 Tab 的筛选条件、分页状态需要独立缓存（React Query/SWR cache key 区分 Tab）。
   - 切换 Tab 时不丢失其他 Tab 的页码和搜索条件。

3. **增加触发方式筛选器**：
   - 在现有“运行状态”筛选旁增加“触发方式”下拉（可选，与 Tab 功能部分重叠，可视设计而定）。

4. **列表项展示来源调度**：
   - 当 `trigger_type === "scheduled"` 时，显示：`来自调度：{schedule_name}`，点击跳转到对应调度规则。
   - `schedule_name` 为空时显示“已删除的调度”兜底文案。

5. **操作区改造**：
   - 将“调度管理”按钮改为“新建定时规则”，点击后在当前页弹窗/抽屉创建。
   - 保留“新建测试运行”按钮。

6. **搜索扩展**：
   - 搜索框支持按调度名称反查（后端通过 join `test_run_schedules` 表实现）。

### 6.3 调度规则视图改造

将现有 `ui/app/projects/[projectId]/test-runs/schedules/page.tsx` 作为执行中心的一个 Tab 嵌入，或改造为抽屉/弹窗：

1. **列表项增强**：
   - 展示模板摘要：脚本数、执行模式、环境。
   - 展示“下次执行 / 上次执行”。
   - 展示“最近执行状态”小徽章（成功/失败/执行中）。
   - **N+1 问题处理**：后端 `get_schedules` 需要预加载每个 schedule 的最近一次 TestRun 状态，或在响应中新增 `last_run_status` / `last_run_at` 字段。

2. **新增操作**：
   - **立即触发**：调用 `POST /test-runs/schedules/{id}/trigger`，生成一次执行。
   - **执行历史**：调用 `GET /test-runs/schedules/{id}/runs`，展示该调度产生的 TestRun 列表。

3. **编辑体验**：
   - 编辑调度时，若仅修改触发时间，不应影响已生成的执行记录。
   - 修改模板后，下次触发生效，历史记录不变。

### 6.4 测试运行详情页改造

基于 `ui/app/projects/[projectId]/test-runs/[runId]/page.tsx`：

1. **顶部元数据增加来源**：
   - 若 `trigger_type === "scheduled"`，显示来源调度名称及跳转链接。
   - 若 `trigger_type === "api"`，显示 API 调用标识/来源。

2. **操作按钮差异化**：
   - 手动 run：执行/取消执行。
   - 定时 run：不显示“执行”按钮，改为显示“查看调度规则”。
   - API run：不显示“执行”按钮（或视需求允许重新触发）。
   - 该部分条件渲染分支较多，需单独测试三种 trigger_type 的展示状态。

### 6.5 路由规划

| 路由 | 用途 | 备注 |
|------|------|------|
| `/projects/{projectId}/test-runs` | 执行中心首页，默认展示“全部” Tab | 现有路由 |
| `/projects/{projectId}/test-runs?tab=scheduled` | 展示定时执行记录 | 新增查询参数 |
| `/projects/{projectId}/test-runs?tab=schedules` | 展示调度规则列表 | 替代原 schedules 页 |
| `/projects/{projectId}/test-runs/schedules` | 保留并前端重定向到新 Tab | 兼容旧书签 |
| `/projects/{projectId}/test-runs/{runId}` | 执行详情 | 现有路由 |

---

## 7. 执行引擎改造

### 7.1 统一执行入口

所有执行方式最终都调用 `TestRunService.execute_test_run()`：

```
手动触发  → POST /test-runs/{id}/execute
定时触发  → scheduler_service 调用 create + execute_test_run
API 触发  → 外部接口调用 create + execute_test_run
```

### 7.2 调度生成逻辑规范（⚠️ 核心）

调度触发时生成的 `TestRun` 必须满足：

- `trigger_type = TriggerType.SCHEDULED`
- `scheduled_by = schedule.id`
- `name` 优先使用模板中的 `name`，可追加时间戳避免重名（如 `每日回归测试 - 2026-07-12 09:00`）。
- `execution_mode`、`environment_id`、`scripts` 等从模板展开。
- 脚本作业创建逻辑与手动创建完全一致，统一走 `TestRunService.create()`。

### 7.3 幂等与并发控制

对于高频/短周期调度，增加幂等保护：

- 同一 `schedule_id` 在 1 分钟内不允许生成多个 `TestRun`（可配置）。
- 调度触发时检查是否存在该 schedule 生成的 `run_state == "in_progress"` 的 run，若存在则跳过本次触发。
- “立即触发”按钮也需要同样的幂等保护，避免用户连续点击生成多个实例。

---

## 8. 测试策略

### 8.1 功能测试

| 场景 | 验证点 |
|------|--------|
| 创建手动执行 | 创建后 `trigger_type=manual`，可执行，结果正确 |
| 创建调度规则 | 规则保存正确，下次执行时间计算正确 |
| 调度触发执行 | 生成 `trigger_type=scheduled` 的 TestRun，`scheduled_by` 正确 |
| 立即触发调度 | 手动触发一次调度，生成 TestRun 并执行 |
| 列表按触发方式筛选 | 全部/手动/定时/API 四个 Tab 数据正确 |
| 调度执行历史 | 进入调度规则可查看该规则产生的所有执行记录 |
| 编辑调度模板 | 编辑后下次触发生效，历史记录不受影响 |
| 删除调度规则 | 已生成的 TestRun 不被级联删除（`ondelete=SET NULL`） |

### 8.2 数据一致性测试（新增）

- 调度触发创建的 `TestRun` 与手动创建的 `TestRun`，在执行引擎中的流转路径完全一致。
- 调度产生的 `TestRun` 在 `scheduled_by` 填写正确的前提下，列表查询/详情展示正常。
- 调度产生的 `TestRun` 脚本作业数量、顺序、执行模式与模板一致。

### 8.3 并发/幂等测试（新增）

| 场景 | 验证点 |
|------|--------|
| 1 分钟窗口内同调度被多次触发 | 只生成 1 个 TestRun |
| 调度触发时上一轮仍在执行 | 跳过本次触发 |
| 手动点击“立即触发”和定时触发同时发生 | 数据隔离，不重复生成 |
| 用户连续点击“立即触发”按钮 | 只生成 1 个 TestRun |

### 8.4 边界测试

| 场景 | 验证点 |
|------|--------|
| 调度模板中环境被删除 | 执行失败，错误信息明确 |
| 调度模板中脚本被删除 | 执行失败或跳过，错误信息明确 |
| 调度禁用时 | 不生成新的 TestRun |
| `scheduled_by` 指向的调度规则被删除 | 历史 TestRun 详情页正常展示，schedule_name 兜底显示“已删除的调度” |
| 短周期高频调度 | 幂等保护生效，不重复生成 |
| 手动与调度同时执行 | 数据隔离，结果不互相覆盖 |

### 8.5 回归测试

- 原有手动执行全流程（创建、编辑、执行、查看报告、重试、关闭、删除）。
- 原有测试运行列表搜索、分页、状态筛选。
- 原有脚本作业日志、报告预览、历史趋势、性能基准。

### 8.6 E2E 测试链路

**正向链路**：
创建 cron 调度 → 立即触发 → 验证执行中心出现新的定时执行记录 → 进入详情查看结果 → 返回调度规则查看执行历史。

**负向链路**：
创建调度 → 禁用调度 → 等触发时间过去 → 验证没有新 TestRun 产生。

**灰度兼容链路**：
旧 `/test-runs/schedules` 页面和新执行中心“调度规则”Tab 同时运行时，数据源一致、操作互不干扰。

### 8.7 自动化测试建议

1. **API 集成测试**：
   - 覆盖 `/test-runs?trigger_type=xxx` 过滤。
   - 覆盖 `/test-runs/schedules/{id}/trigger` 和 `/test-runs/schedules/{id}/runs`。
   - 覆盖 `TestRunService.create()` 在 `trigger_type=scheduled` 时写入 `scheduled_by`。
   - 覆盖调度触发收敛后脚本作业创建正确。

2. **前端组件测试**：
   - 执行中心 Tab 切换及 URL 同步。
   - 列表项中“来自调度”链接渲染及兜底文案。
   - 调度规则“立即触发”按钮状态变化及幂等。
   - 详情页三种 `trigger_type` 的操作按钮条件渲染。

3. **端到端测试**：
   - 完整覆盖 8.6 中的三条链路。

---

## 9. 实施计划

| 阶段 | 任务 | 预计工时 | 依赖 |
|------|------|----------|------|
| 第一阶段 | Schema 层 alias：对外暴露 `schedule_id`，DB 保持 `scheduled_by` 不变 | 0.1 天 | 无 |
| 第一阶段 | 后端服务改造：`create/get_list` 支持 `scheduled_by` 关联和 `trigger_type` 过滤 | 1 天 | 模型确定 |
| 第一阶段 | 调度触发逻辑收敛：禁止 `scheduler_service` 直接操作 ORM，统一走 `TestRunService` | 1.5 天 | 服务改造 |
| 第二阶段 | 后端新增 API：`/schedules/{id}/trigger`（含幂等）、`/schedules/{id}/runs` | 1 天 | 服务改造 |
| 第二阶段 | 前端执行中心页面：Tab 结构、URL 同步、状态隔离、筛选、来源调度展示 | 3 天 | 新增 API |
| 第二阶段 | 前端调度规则嵌入/抽屉改造：立即触发、执行历史、N+1 优化后的列表 | 1 天 | 新增 API |
| 第三阶段 | 前端详情页改造：来源信息、三种 trigger_type 的条件渲染 | 1 天 | 后端返回 schedule 信息 |
| 第三阶段 | 旧 `/test-runs/schedules` 路由前端重定向 | 0.5 天 | 新页面稳定 |
| 第四阶段 | 补充集成测试和端到端测试 | 2.5 天 | 功能开发完成 |
| 第四阶段 | 灰度发布与线上观察 | 1 天 | 测试通过 |

**总计：约 11.5 人日**

---

## 10. 风险与应对

| 风险 | 影响 | 应对措施 |
|------|------|----------|
| 调度触发收敛到 Service 导致定时任务失效 | **极高** | 分阶段改造：先保留原逻辑并行，新增统一路径后通过集成测试验证，再下线原逻辑；上线后 24h 内重点监控 APScheduler 回调日志 |
| Schema alias 与 DB 字段不一致导致前后端混淆 | 低 | 文档明确约定：DB/ORM 用 `scheduled_by`，API/前端用 `schedule_id`；代码 review 时重点检查 |
| 前端 Tab 状态管理复杂度超预期 | 中 | 使用 URL 作为单一状态源；不同 Tab 使用独立 cache key；分页状态存入 URL |
| schedule 列表 N+1 查询性能问题 | 中 | 后端 `get_schedules` 预加载最近一次 TestRun，响应中新增 `last_run_status` 字段 |
| 前端改造范围大 | 中 | 弹窗/抽屉方式复用现有 schedules 页，降低改造量；分 Tab 逐步交付 |
| 用户不习惯新入口 | 低 | 保留旧路由前端重定向；页面顶部增加提示说明 |
| 历史数据无来源调度 | 低 | 仅对改造后新生成的执行做关联，历史数据保持现状 |

---

## 11. 验收标准

1. 项目导航中只保留一个“测试执行”入口（或保留“测试运行”名称但承载新结构）。
2. 执行中心包含“全部/手动/定时/API/调度规则”五个 Tab，数据正确。
3. 定时执行记录在列表中显示来源调度名称，点击进入调度规则；调度已删除时显示兜底文案。
4. 调度规则支持“立即触发”和“查看执行历史”，且立即触发有幂等保护。
5. `scheduler_service` 不再直接 `session.add(TestRun)` 或 `session.add_all(TestRunScriptJob)`。
6. 所有新产生的定时执行 `TestRun` 都携带正确的 `scheduled_by`（API/前端以 `schedule_id` alias 展示）。
7. 原有手动执行、脚本作业、报告、日志功能无回归。
8. 新增/改造的接口通过集成测试覆盖，新增 E2E 覆盖完整链路。

---

## 12. 附录：关键文件清单

### 后端

- `backend/app/models/test_run.py` — `TestRun` / `TestRunSchedule` 模型
- `backend/app/schemas/test_run.py` — Schema 定义
- `backend/app/api/v2/test_runs.py` — API 路由
- `backend/app/services/test_run_service.py` — 业务逻辑
- `backend/app/services/scheduler_service.py` — 调度触发逻辑（核心改造点）
- `backend/alembic/versions/` — 数据库迁移

### 前端

- `ui/app/projects/[projectId]/test-runs/page.tsx` — 测试运行列表
- `ui/app/projects/[projectId]/test-runs/[runId]/page.tsx` — 测试运行详情
- `ui/app/projects/[projectId]/test-runs/schedules/page.tsx` — 定时调度页
- `ui/lib/api/testRuns.ts` — API 调用封装
- `ui/lib/api/types.ts` — TypeScript 类型

---

## 13. 版本变更记录

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| v1.0 | 2026-07-12 | 初稿 |
| v2.0 | 2026-07-12 | 修正数据模型：复用已有 `scheduled_by` 字段，通过 Pydantic alias 对外暴露 `schedule_id`；强调调度触发绕过 Service 是核心风险；增加前端 Tab 状态管理、N+1 查询、详情页条件渲染分析；补充数据一致性、并发幂等、已删除调度兜底测试；更新工时估算为 11.5 人日；修正 SPA 重定向方案 |

---

*文档结束*
