# maib services 边界审计

> 更新日期：2026-11-19
> 审计来源：`tests/test_maib_services_boundary.py`  
> 当前结果：56 处外部 services 调用，11 个未解决不纯事项；已解决原清单中的 31 项。

## 边界判定标准

services 外部可以使用：

- 标量、容器、`datetime` 等通用值；
- `utils` 领域对象，包括为查询或展示附加的 `_xxx` 字段；
- 必要的聚合结果类，例如 `B50Data`；
- services 公开领域异常和明确的公开结果对象。

services 外部不应：

- 导入或引用 services ORM 模型；
- 调用返回或接收 ORM 的 services API；
- 获取 `get_session` 或调用 `execute_func`；
- 向 services 公开 API 传入 `session`；
- 依赖 ORM relationship 的加载状态。

### 类别

| 代码 | 含义 |
|---|---|
| ORM API | 公开 API 返回或接收 services ORM |
| ORM 引用 | services 外部直接引用 ORM 类 |
| ORM 导入 | services 外部从 `services.models` 导入 ORM |
| 内部 API | services 外部调用 `get_session` / `execute_func` |
| Session 越界 | services 外部组织事务并向公开 API 传入 `session` |

## 审计汇总

| 类别 | 数量 |
|---|---:|
| ORM API | 10 |
| ORM 引用 | 0 |
| ORM 导入 | 1 |
| 内部 API | 0 |
| Session 越界 | 0 |
| **未解决合计** | **11** |
| 已解决 | 31 |

## 逐项审查表

`状态` 建议使用：`[ ]` 未审查、`[~]` 已审查/待改、`[x]` 已解决、`[-]` 决定保留。

| ID | 状态 | 位置 | 符号 | 类别 | 当前问题 | 建议方向 |
|---:|:---:|---|---|---|---|---|
| 01 | [x] | [`fetch.py`](../fetch.py) | `refactoring.catalog.sync_song_library` | ORM API | 已改为传入 `Sequence[utils.MaiData]`。 | ORM 构造、upsert 与事务均已收回 services。 |
| 02 | [x] | [`fetch.py`](../fetch.py) | `refactoring.catalog.sync_song_library` | ORM 引用 | `fetch` 已不再构造或引用 `services.MaiData`。 | utils → ORM 映射位于 services 内部。 |
| 03 | [x] | [`fetch.py`](../fetch.py) | `refactoring.catalog.apply_cn_metadata` | 内部 API | `fetch` 已不再开启数据库 session。 | CN 元数据更新由单一 services 用例管理事务。 |
| 04 | [x] | [`fetch.py`](../fetch.py) | `refactoring.catalog.apply_cn_metadata` | Session 越界 | 版本批量更新已收回 services。 | 公开 API 仅接收标量容器。 |
| 05 | [x] | [`fetch.py`](../fetch.py) | `refactoring.catalog.apply_cn_metadata` | Session 越界 | 定数批量更新已收回 services。 | 与版本更新处于同一事务。 |
| 06 | [x] | [`fetch.py`](../fetch.py) | `refactoring.catalog.apply_cn_metadata` | Session 越界 | DX Rating 刷新已收回 services。 | 更新或刷新失败时整体回滚。 |
| 07 | [x] | [`fetch.py`](../fetch.py) | `refactoring.catalog.has_song_library` | 内部 API | 维护任务已不再直接查询数据库。 | 公开 API 返回 `bool`。 |
| 08 | [x] | [`fetch.py`](../fetch.py) | `refactoring.catalog.has_song_library` | ORM 引用 | `select(MaiData)` 已收回 services。 | `fetch` 仅根据布尔结果决定是否重建。 |
| 09 | [x] | [`matcher/adx_download.py`](../matcher/adx_download.py) | `refactoring.catalog.get_maidata` | ORM API | 已改用异步曲目查询并返回 `utils.MaiData`。 | 谱面包路径与 Telegram 缓存均由 utils 对象提供。 |
| 10 | [x] | [`matcher/adx_download.py`](../matcher/adx_download.py) | `utils.MaiData` | ORM 引用 | matcher 已不再引用 services ORM。 | 使用 `utils.MaiData | None` 并处理未找到分支。 |
| 11 | [x] | [`matcher/alias.py`](../matcher/alias.py) | `refactoring.alias.add_alias` | ORM API | 曲目校验、重复判断与新增已收回同一 services 事务。 | 公开 API 仅接收标量并返回轻量状态。 |
| 12 | [x] | [`matcher/alias.py`](../matcher/alias.py) | `refactoring.alias.remove_alias` | ORM 引用 | matcher 已不再引用曲目或别名 ORM。 | 仅允许 `create_qq == qq` 的创建者删除别名。 |
| 13 | [ ] | [`matcher/context.py:56`](../matcher/context.py#L56) | `check_mu` | ORM API | 平台用户解析返回 ORM `MaiUser`。 | AID 前先改为返回 `utils.MaiUser`；AID 后由 locales 解析身份。 |
| 14 | [ ] | [`matcher/context.py:58`](../matcher/context.py#L58) | `get_mu_from_tgid` | ORM API | Telegram 账号查找返回 ORM。 | 账号绑定迁移到 locales，services 只接收 AID 并返回 utils 用户。 |
| 15 | [x] | [`matcher/context.py`](../matcher/context.py) | `refactoring.catalog.get_maidata` | ORM API | 已按 QQ、`ServerScope` 和 provider 加载 utils 成绩。 | 默认 JP 使用 `lyrasync-oto`，CN 使用 `diving-fish`。 |
| 16 | [x] | [`matcher/dxrating_calc.py`](../matcher/dxrating_calc.py) | `refactoring.catalog.get_maidata` | ORM API | 已改为通过纯边界查询 utils 曲目，不再获取 ORM。 | `get_maidata()` 禁载成绩关系，matcher 直接读取谱面定数。 |
| 17 | [ ] | [`matcher/info.py:57`](../matcher/info.py#L57) | `get_mu_from_tgid` | ORM API | Telegram 解析依赖 maib ORM 账号绑定。 | 改为 locales 解析 AID，必要时再取 `utils.MaiUser`。 |
| 18 | [ ] | [`matcher/info.py:76`](../matcher/info.py#L76) | `check_mu` | ORM API | info matcher 获取 ORM 用户。 | 改为 `get_or_create_user()` 返回 `utils.MaiUser`。 |
| 19 | [x] | [`matcher/info.py`](../matcher/info.py) | `refactoring.catalog.get_maidata` | ORM API | 单曲信息查询已直接返回含所选成绩的 utils 曲目。 | matcher 不再负责 ORM 转换。 |
| 20 | [x] | [`matcher/info.py`](../matcher/info.py) | `utils.MaiData` | ORM 引用 | info matcher 已不再引用 services ORM。 | 类型边界统一为 utils。 |
| 21 | [x] | [`matcher/info.py`](../matcher/info.py) | `refactoring.catalog.search_maidata` | ORM API | 搜索、别名命中和成绩加载均已收回 services。 | 命中别名通过 `_matched_alias` 提供。 |
| 22 | [x] | [`matcher/info_list.py`](../matcher/info_list.py) | `get_mct_list.level` | ORM API | 未启用完成表入口后的不可达查询草案已删除。 | 将来实现时直接使用 utils 查询边界。 |
| 23 | [x] | [`matcher/info_list.py`](../matcher/info_list.py) | `get_mct_list.level` | ORM API | 另一定数范围查询随不可达草案一并删除。 | 不再保留未运行的 ORM 基线。 |
| 24 | [ ] | [`matcher/info_list.py:75`](../matcher/info_list.py#L75) | `get_mu_from_tgid` | ORM API | Telegram 用户查找返回 ORM。 | 由 locales 解析 AID。 |
| 25 | [ ] | [`matcher/info_list.py:99`](../matcher/info_list.py#L99) | `check_mu` | ORM API | 列表 matcher 获取 ORM 用户。 | 改为 utils 用户 API。 |
| 26 | [x] | [`matcher/info_list.py`](../matcher/info_list.py) | `refactoring.b50.get_b50_data` | ORM API | B50 SQL、provider 过滤和 utils 组装已收回 services。 | 返回 `utils.B50Data`。 |
| 27 | [x] | [`matcher/info_list.py`](../matcher/info_list.py) | `utils.B50Data` | ORM 引用 | matcher 已删除 ORM `_build_entries` 组装层。 | 非 ALL DTO 由 `draw_b50_data()` 解包并复用原绘图函数。 |
| 28 | [x] | [`matcher/maime.py`](../matcher/maime.py) | `refactoring.aime.link` | ORM API | 已收回绑卡预查询与事务。 | 纯 services 用例；仅接收标量并抛出公开领域异常。 |
| 29 | [x] | [`matcher/maime.py`](../matcher/maime.py) | `refactoring.aime.unlink` | ORM API | 已收回解绑预查询与所有权判断。 | 纯 services 用例；解绑保留历史记录。 |
| 30 | [x] | [`matcher/maime.py`](../matcher/maime.py) | `refactoring.aime.find_aime_by_access4` | ORM API | 已收回后四位历史查找与歧义判断。 | 返回轻量 `TypedDict`，不泄漏 ORM。 |
| 31 | [x] | [`matcher/maime.py`](../matcher/maime.py) | `refactoring.aime.find_aime` | ORM API | 已收回完整卡号查询。 | 只返回当前绑定记录及公开字段。 |
| 32 | [x] | [`matcher/maime.py`](../matcher/maime.py) | `refactoring.aime.get_aimes` | ORM API | 已收回用户卡片列表查询。 | 返回轻量 `TypedDict` 列表，不泄漏 ORM。 |
| 33 | [ ] | [`matcher/sync.py:21`](../matcher/sync.py#L21) | `MaiUser` | ORM 导入 | matcher 直接从 `services.models` 导入 ORM。 | 改用 `utils.MaiUser`，并删除所有 ORM 判断。 |
| 34 | [ ] | [`matcher/sync.py:135`](../matcher/sync.py#L135) | `check_mu` | ORM API | 同步入口获取 ORM 用户。 | 返回 `utils.MaiUser`；AID 后参数改为 AID。 |
| 35 | [ ] | [`matcher/sync.py:156`](../matcher/sync.py#L156) | `check_mu` | ORM API | 同步完成后重新拉取 ORM 用户。 | 返回刷新后的 `utils.MaiUser`，或让同步用例同时返回用户数据。 |
| 36 | [x] | [`matcher/sync.py`](../matcher/sync.py) | `refactoring.catalog.search_maidata` | ORM API | legacy 标题解析已使用无成绩 utils 精确查询。 | 保留现有 SD/DX shortid 消歧逻辑。 |
| 37 | [ ] | [`matcher/temp_link.py:58`](../matcher/temp_link.py#L58) | `check_mu` | ORM API | 临时绑定流程通过 ORM 用户确保记录存在。 | AID 后由 locales 管理账号绑定；maib 仅按 AID 创建 utils 用户。 |
| 38 | [ ] | [`matcher/temp_link.py:80`](../matcher/temp_link.py#L80) | `get_mu_from_tgid` | ORM API | 临时解绑直接读取 maib ORM 账号绑定。 | 整个临时绑定流程迁移至 locales API。 |
| 39 | [x] | [`mcp/__init__.py`](../mcp/__init__.py) | `utils.MaiData` | ORM 引用 | MCP 序列化函数已改为接收 utils 曲目。 | 通过 `_id` 保留原谱面数据库 ID 输出。 |
| 40 | [x] | [`mcp/__init__.py`](../mcp/__init__.py) | `refactoring.catalog.search_maidata` | ORM API | MCP 搜索已切换为无成绩 utils 查询。 | 不加载成绩 relationship。 |
| 41 | [x] | [`mcp/__init__.py`](../mcp/__init__.py) | `refactoring.catalog.get_maidata` | ORM API | MCP 单曲查询已切换为 utils 曲目。 | 不再暴露 ORM。 |
| 42 | [x] | [`mcp/__init__.py`](../mcp/__init__.py) | `refactoring.mcp_sql.sql_query` | 内部 API | SQL 校验、超时、执行和 session 已完整收回 services。 | MCP 仅处理公开 `ReadOnlySqlError`。 |

## 建议审查顺序

1. **01–08：`fetch.py`（已完成）**
   已收回 ORM 构造、事务和曲库同步数据库操作，共消除 8 项。
2. **09–23、39–41：曲目及谱面查询（已完成）**
   曲目查询已统一返回 utils；未启用完成表的不可达 ORM 草案已删除。
3. **28–32：Aime（已完成）**
   采用 refactoring 闭包和轻量 `TypedDict`，未引入不必要的 DTO。
4. **13–18、24–25、33–38：用户与账号绑定**  
   与 locales/AID 迁移一起处理，避免重复改造。
5. **26–27：B50（已完成）**
   `utils.B50Data` 已承载聚合结果，services 内完成默认 provider 选择和 ORM 转换。
6. **42：MCP 只读 SQL（已完成）**
   SQL 校验与执行已收回 `services.refactoring.mcp_sql.sql_query`。

## 与测试基线同步

完成一项后：

1. 运行 `python -m unittest tests.test_maib_services_boundary -v`；
2. 如果某 API 已改为纯边界，将它从 `ORM_SERVICE_APIS` 移到 `PURE_SERVICE_APIS`；
3. 删除 `KNOWN_IMPURE_USAGE_MAXIMUMS` 中对应条目；
4. 重新运行全部测试，确认没有新的越界调用。

