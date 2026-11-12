# maib services 边界审计

> 生成日期：2026-11-12  
> 审计来源：`tests/test_maib_services_boundary.py`  
> 当前结果：62 处外部 services 调用，37 个未解决不纯事项；Aime 闭包已解决原清单中的 5 项。

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
| ORM API | 23 |
| ORM 引用 | 7 |
| ORM 导入 | 1 |
| 内部 API | 3 |
| Session 越界 | 3 |
| **未解决合计** | **37** |
| 已解决（Aime） | 5 |

## 逐项审查表

`状态` 建议使用：`[ ]` 未审查、`[~]` 已审查/待改、`[x]` 已解决、`[-]` 决定保留。

| ID | 状态 | 位置 | 符号 | 类别 | 当前问题 | 建议方向 |
|---:|:---:|---|---|---|---|---|
| 01 | [ ] | [`fetch.py:320`](../fetch.py#L320) | `sync_mdt_list` | ORM API | 曲库解析层向 services 传入 ORM 列表。 | 使 `sync_song_library` / `sync_mdt_list` 直接接收 `Sequence[utils.MaiData]`。 |
| 02 | [ ] | [`fetch.py:321`](../fetch.py#L321) | `MaiData` | ORM 引用 | `fetch` 直接构造 `services.MaiData` ORM。 | 删除 `services.MaiData.from_utils()` 外部调用，在 services 内部映射。 |
| 03 | [ ] | [`fetch.py:403`](../fetch.py#L403) | `get_session` | 内部 API | `fetch` 直接开启数据库 session。 | 提供单一 `sync_cn_metadata` services 用例封装整个事务。 |
| 04 | [ ] | [`fetch.py:405`](../fetch.py#L405) | `set_mdt_version_batch` | Session 越界 | 外部向 services 传入 session。 | 并入 `sync_cn_metadata`，或由 services 公开函数自行管理事务。 |
| 05 | [ ] | [`fetch.py:407`](../fetch.py#L407) | `set_mct_level_batch` | Session 越界 | 外部向 services 传入 session。 | 与版本更新、DX Rating 刷新纳入同一 services 用例。 |
| 06 | [ ] | [`fetch.py:412`](../fetch.py#L412) | `rfs_dxra_batch` | Session 越界 | 外部组织曲库更新后的缓存刷新。 | 由 `sync_cn_metadata` 在事务内自动刷新。 |
| 07 | [ ] | [`fetch.py:540`](../fetch.py#L540) | `get_session` | 内部 API | 维护任务直接查询数据库。 | 增加 `services.has_song_library() -> bool`。 |
| 08 | [ ] | [`fetch.py:541`](../fetch.py#L541) | `MaiData` | ORM 引用 | 维护任务直接构建 `select(services.MaiData.shortid)`。 | 由 `has_song_library()` 内部查询。 |
| 09 | [ ] | [`matcher/adx_download.py:269`](../matcher/adx_download.py#L269) | `get_mdt.id` | ORM API | 下载 matcher 获取 ORM 曲目。 | 改用返回 `utils.MaiData` 的 `get_song()`；缓存 ID 更新仍走 services。 |
| 10 | [ ] | [`matcher/adx_download.py:269`](../matcher/adx_download.py#L269) | `MaiData` | ORM 引用 | matcher 类型标注依赖 services ORM。 | 改为 `utils.MaiData | None`。 |
| 11 | [ ] | [`matcher/alias.py:52`](../matcher/alias.py#L52) | `get_mdt.id` | ORM API | 别名 matcher 为判断曲目存在而获取 ORM。 | 使用 `get_song()` 或轻量 `song_exists(shortid)`。 |
| 12 | [ ] | [`matcher/alias.py:52`](../matcher/alias.py#L52) | `MaiData` | ORM 引用 | matcher 类型标注依赖 services ORM。 | 改为 `utils.MaiData | None`，或在只判存在时去掉对象。 |
| 13 | [ ] | [`matcher/context.py:56`](../matcher/context.py#L56) | `check_mu` | ORM API | 平台用户解析返回 ORM `MaiUser`。 | AID 前先改为返回 `utils.MaiUser`；AID 后由 locales 解析身份。 |
| 14 | [ ] | [`matcher/context.py:58`](../matcher/context.py#L58) | `get_mu_from_tgid` | ORM API | Telegram 账号查找返回 ORM。 | 账号绑定迁移到 locales，services 只接收 AID 并返回 utils 用户。 |
| 15 | [ ] | [`matcher/context.py:80`](../matcher/context.py#L80) | `get_mdt.id` | ORM API | 上下文加载曲目后在 matcher 调用 `to_utils()`。 | services 根据用户/provider scope 直接返回 `utils.MaiData`。 |
| 16 | [ ] | [`matcher/dxrating_calc.py:60`](../matcher/dxrating_calc.py#L60) | `get_mdt.id` | ORM API | DX Rating 计算为取谱面定数而获取 ORM。 | 使用 `get_song()` 返回的 utils 曲目。 |
| 17 | [ ] | [`matcher/info.py:57`](../matcher/info.py#L57) | `get_mu_from_tgid` | ORM API | Telegram 解析依赖 maib ORM 账号绑定。 | 改为 locales 解析 AID，必要时再取 `utils.MaiUser`。 |
| 18 | [ ] | [`matcher/info.py:76`](../matcher/info.py#L76) | `check_mu` | ORM API | info matcher 获取 ORM 用户。 | 改为 `get_or_create_user()` 返回 `utils.MaiUser`。 |
| 19 | [ ] | [`matcher/info.py:110`](../matcher/info.py#L110) | `get_mdt.id` | ORM API | 单曲信息查询返回 ORM，matcher 自行转 utils。 | `get_song()` 直接返回含成绩范围的 `utils.MaiData`。 |
| 20 | [ ] | [`matcher/info.py:110`](../matcher/info.py#L110) | `MaiData` | ORM 引用 | info matcher 类型标注依赖 services ORM。 | 改为 `utils.MaiData | None`。 |
| 21 | [ ] | [`matcher/info.py:150`](../matcher/info.py#L150) | `get_mdt.title` | ORM API | 搜索返回 ORM 列表，matcher 遍历 ORM aliases。 | 返回 `utils.MaiData`，将命中别名放入 `MaiData._matched_alias`。 |
| 22 | [ ] | [`matcher/info_list.py:84`](../matcher/info_list.py#L84) | `get_mct_list.level` | ORM API | 定数筛选返回 ORM `MaiChart`。 | 返回 `utils.MaiChart`；展示所需曲目信息可使用 `_maidata` 附加。 |
| 23 | [ ] | [`matcher/info_list.py:96`](../matcher/info_list.py#L96) | `get_mct_list.level` | ORM API | 另一定数范围查询返回 ORM。 | 与 22 合并迁移到 utils 谱面查询。 |
| 24 | [ ] | [`matcher/info_list.py:169`](../matcher/info_list.py#L169) | `get_mu_from_tgid` | ORM API | Telegram 用户查找返回 ORM。 | 由 locales 解析 AID。 |
| 25 | [ ] | [`matcher/info_list.py:193`](../matcher/info_list.py#L193) | `check_mu` | ORM API | 列表 matcher 获取 ORM 用户。 | 改为 utils 用户 API。 |
| 26 | [ ] | [`matcher/info_list.py:237`](../matcher/info_list.py#L237) | `get_b50` | ORM API | B50 返回 ORM 成绩列表，外部组装绘图数据。 | 引入 `B50Data`，services 内部完成 provider 选择和所需数据加载。 |
| 27 | [ ] | [`matcher/info_list.py:241`](../matcher/info_list.py#L241) | `MaiChartAch` | ORM 引用 | `_build_entries` 显式标注 ORM，并读取 `ach.chart.maidata`。 | 删除该 ORM 组装层，直接消费 `B50Data`。 |
| 28 | [x] | [`matcher/maime.py`](../matcher/maime.py) | `refactoring.aime.link` | ORM API | 已收回绑卡预查询与事务。 | 纯 services 用例；仅接收标量并抛出公开领域异常。 |
| 29 | [x] | [`matcher/maime.py`](../matcher/maime.py) | `refactoring.aime.unlink` | ORM API | 已收回解绑预查询与所有权判断。 | 纯 services 用例；解绑保留历史记录。 |
| 30 | [x] | [`matcher/maime.py`](../matcher/maime.py) | `refactoring.aime.find_aime_by_access4` | ORM API | 已收回后四位历史查找与歧义判断。 | 返回轻量 `TypedDict`，不泄漏 ORM。 |
| 31 | [x] | [`matcher/maime.py`](../matcher/maime.py) | `refactoring.aime.find_aime` | ORM API | 已收回完整卡号查询。 | 只返回当前绑定记录及公开字段。 |
| 32 | [x] | [`matcher/maime.py`](../matcher/maime.py) | `refactoring.aime.get_aimes` | ORM API | 已收回用户卡片列表查询。 | 返回轻量 `TypedDict` 列表，不泄漏 ORM。 |
| 33 | [ ] | [`matcher/sync.py:21`](../matcher/sync.py#L21) | `MaiUser` | ORM 导入 | matcher 直接从 `services.models` 导入 ORM。 | 改用 `utils.MaiUser`，并删除所有 ORM 判断。 |
| 34 | [ ] | [`matcher/sync.py:135`](../matcher/sync.py#L135) | `check_mu` | ORM API | 同步入口获取 ORM 用户。 | 返回 `utils.MaiUser`；AID 后参数改为 AID。 |
| 35 | [ ] | [`matcher/sync.py:156`](../matcher/sync.py#L156) | `check_mu` | ORM API | 同步完成后重新拉取 ORM 用户。 | 返回刷新后的 `utils.MaiUser`，或让同步用例同时返回用户数据。 |
| 36 | [ ] | [`matcher/sync.py:280`](../matcher/sync.py#L280) | `get_mdt.title` | ORM API | legacy 记录解析为解析 shortid 而获取 ORM。 | 使用返回 utils 的精确标题查询，更好的方向是将整个记录导入收回 services。 |
| 37 | [ ] | [`matcher/temp_link.py:58`](../matcher/temp_link.py#L58) | `check_mu` | ORM API | 临时绑定流程通过 ORM 用户确保记录存在。 | AID 后由 locales 管理账号绑定；maib 仅按 AID 创建 utils 用户。 |
| 38 | [ ] | [`matcher/temp_link.py:80`](../matcher/temp_link.py#L80) | `get_mu_from_tgid` | ORM API | 临时解绑直接读取 maib ORM 账号绑定。 | 整个临时绑定流程迁移至 locales API。 |
| 39 | [ ] | [`mcp/__init__.py:36`](../mcp/__init__.py#L36) | `MaiData` | ORM 引用 | MCP 序列化函数直接接收 ORM。 | 改为序列化 `utils.MaiData`。 |
| 40 | [ ] | [`mcp/__init__.py:81`](../mcp/__init__.py#L81) | `get_mdt.title` | ORM API | MCP 搜索返回 ORM。 | 使用 utils 曲目搜索 API。 |
| 41 | [ ] | [`mcp/__init__.py:87`](../mcp/__init__.py#L87) | `get_mdt.id` | ORM API | MCP 单曲查询返回 ORM。 | 使用 `get_song()` 返回 `utils.MaiData`。 |
| 42 | [ ] | [`mcp/__init__.py:101`](../mcp/__init__.py#L101) | `get_session` | 内部 API | MCP 只读 SQL 工具直接获取 services session。 | 将 SQL 校验和执行整体封装为 services 内部只读用例。 |

## 建议审查顺序

1. **01–08：`fetch.py`**  
   先收回 ORM 构造、事务和曲库同步编排，可一次消除 8 项。
2. **09–23、39–41：曲目及谱面查询**  
   使曲目查询统一返回 utils 对象，并使用 `_matched_alias` / `_maidata` 等查询附加字段。
3. **28–32：Aime（已完成）**
   采用 refactoring 闭包和轻量 `TypedDict`，未引入不必要的 DTO。
4. **13–18、24–25、33–38：用户与账号绑定**  
   与 locales/AID 迁移一起处理，避免重复改造。
5. **26–27：B50**  
   引入 `B50Data`，同时落实默认 provider 选择。
6. **42：MCP 只读 SQL**  
   单独评估该管理工具是否允许特例；若不特例，则收回 services。

## 与测试基线同步

完成一项后：

1. 运行 `python -m unittest tests.test_maib_services_boundary -v`；
2. 如果某 API 已改为纯边界，将它从 `ORM_SERVICE_APIS` 移到 `PURE_SERVICE_APIS`；
3. 删除 `KNOWN_IMPURE_USAGE_MAXIMUMS` 中对应条目；
4. 重新运行全部测试，确认没有新的越界调用。

