# maib services 重构规划

## 1. 目标

本次重构以 `plugins.maib.services` 为边界，将当前按 CRUD 和历史实现拆分的接口，整理为按业务用例分包的稳定服务层。

最终目标如下：

1. 对外仅暴露业务用例，不暴露 ORM、`AsyncSession` 或事务辅助器。
2. 公开方法负责创建和结束事务；访问数据库的非公开方法必须加入调用方事务。
3. 移除 `get_session`、`execute_func` 以及公开方法的可选 `session` 参数。
4. 将 `services.refactoring` 中已经稳定的新接口移至正式业务模块。
5. 被新接口完整替代的旧顶层接口不再保留兼容导出。
6. 保留尚未重写的列表筛选业务，并将静态方法转换为普通函数。
7. `services/__init__.py` 只包含模块 import 和 `__all__`。

## 2. 边界与术语

### 2.1 公开方法

满足以下条件的方法属于公开服务方法：

- 可由 `plugins.maib` 中 matcher、Web API、定时维护任务等 services 包外代码调用；
- 参数和返回值不包含 ORM 模型；
- 不接受 `session` 参数；
- 自行管理所需的 session 和事务；
- 对调用方提供稳定的业务语义，而不是数据库 CRUD 语义。

### 2.2 内部数据库方法

访问数据库但不对 services 包外公开的方法：

- 使用下划线前缀或放入 `_internal` 包；
- 必须通过仅关键字参数接收 `session: AsyncSession`；
- 不允许将 `session` 声明为 `Optional`；
- 不允许自行创建 session；
- 不允许 `commit` 或 `rollback`；
- 可以按需 `flush` 和 `refresh`；
- 只能参与公开用例创建的事务。

### 2.3 纯计算辅助函数

不访问数据库的格式化、规范化、合并和 DTO 构造函数不强制接收 session，例如：

- `_normalize_ach`
- `_build_diff`
- `_normalize_access`
- `_json_safe`

这些函数应保持纯函数特征，不引入无意义的数据库依赖。

## 3. 目标目录结构

```text
services/
├── __init__.py
├── models.py                   # ORM 模型，不属于公开服务 API
├── catalog.py                  # 单曲获取、曲名/别名搜索
├── query.py                    # 曲目、谱面、成绩列表筛选
├── alias.py                    # 用户别名操作
├── achievement.py              # 聚合成绩写入
├── record.py                   # 原始游玩记录导入
├── b50.py                      # B50 聚合
├── user.py                     # 用户及平台账号关联
├── aime.py                     # Aime 卡绑定
├── websync.py                  # Web 配对码及访问令牌
├── archive.py                  # 谱面文件标识
├── mcp_sql.py                  # MCP 只读 SQL
├── maintenance/
│   ├── __init__.py
│   ├── catalog.py              # 曲库和元数据维护
│   ├── alias.py                # 外部别名库同步
│   ├── id_mapping.py           # shortid 重映射
│   └── record.py               # 历史记录回填和重建
└── _internal/
    ├── __init__.py
    ├── catalog_repo.py
    ├── achievement_repo.py
    ├── record_repo.py
    ├── user_repo.py
    ├── sync_state.py
    └── rating_refresh.py
```

`refactoring` 是迁移期命名空间，重构完成后删除。

## 4. 最终公开方法表

### 4.1 稳定业务接口

| 模块 | 最终方法 | 当前来源 | 说明 |
|---|---|---|---|
| `catalog` | `get_maidata` | `refactoring.catalog.get_maidata` | 按 shortid 返回曲目 DTO |
| `catalog` | `search_maidata` | `refactoring.catalog.search_maidata` | 按标题或别名搜索曲目 DTO |
| `query` | `list_maidata_by_genre` | `get_mdt_list.genre` | 按流派筛选曲目 |
| `query` | `list_maidata_by_version` | `get_mdt_list.version` | 按版本范围筛选曲目 |
| `query` | `list_charts_by_level` | `get_mct_list.level` | 按定数范围筛选谱面 |
| `query` | `list_achievements_by_user` | `get_mca_list.user` | 获取用户成绩列表 |
| `query` | `list_achievements_by_rate` | `get_mca_list.achievement` | 按完成率筛选成绩 |
| `query` | `list_achievements_by_dxrating` | `get_mca_list.dxrating` | 按 DX Rating 筛选成绩 |
| `alias` | `add_alias` | `refactoring.alias.add_alias` | 添加用户别名 |
| `alias` | `remove_alias` | `refactoring.alias.remove_alias` | 删除用户本人创建的别名 |
| `achievement` | `is_source_current` | `get_last_sy_hash` | 判断指定来源哈希是否已经成功处理 |
| `achievement` | `update_achievements` | `upd_ach_batch` | 写入已经聚合好的成绩并刷新派生缓存；成功时可同时记录来源哈希 |
| `record` | `ingest_records` | `add_record_batch` + `get_record_achs` + `upd_ach_batch` | 原子完成记录写入、聚合、成绩更新和缓存刷新 |
| `b50` | `get_b50_data` | `refactoring.b50.get_b50_data` | 返回 B50 DTO |
| `user` | `get_or_create_from_qq` | `refactoring.user.get_or_create_maiuser_from_qq` | 获取或创建 QQ 用户 DTO |
| `user` | `get_or_create_from_telegram` | `refactoring.user.get_or_create_maiuser_from_tg` | 获取或创建 Telegram 用户 DTO |
| `user` | `get_qq_from_telegram` | `refactoring.link.get_qq_from_tg` | 查询 Telegram 绑定的 QQ |
| `user` | `link_telegram` | `set_mu_tgid` | 建立 QQ 与 Telegram 关联 |
| `user` | `unlink_telegram` | `del_mu_tgid` | 移除 QQ 与 Telegram 关联 |
| `aime` | `link` | `refactoring.aime.link` | 绑定 Aime 卡 |
| `aime` | `unlink` | `refactoring.aime.unlink` | 解绑 Aime 卡 |
| `aime` | `find` | `refactoring.aime.find_aime` | 按完整卡号查询当前绑定 |
| `aime` | `find_by_access4` | `refactoring.aime.find_aime_by_access4` | 按后四位查询卡片 |
| `aime` | `list_for_user` | `refactoring.aime.get_aimes` | 返回用户当前绑定卡片 |
| `websync` | `create_pairing_code` | 当前同名方法 | 创建 Web 配对码 |
| `websync` | `exchange_pairing_code` | 当前同名方法 | 交换配对码并签发访问令牌 |
| `websync` | `authenticate_access_token` | 当前同名方法 | 验证访问令牌 |
| `archive` | `update_telegram_file_id` | `upd_mdt_tg_fileid` | 更新谱面包 Telegram 文件标识 |
| `mcp_sql` | `sql_query` | `refactoring.mcp_sql.sql_query` | 执行受限只读 SQL |

### 4.2 维护任务接口

维护接口允许 services 包外的定时任务调用，但不作为 matcher 或 Web API 的常规业务接口。

| 模块 | 最终方法 | 当前来源 | 说明 |
|---|---|---|---|
| `maintenance.catalog` | `sync_song_library` | `refactoring.catalog.sync_song_library` | 同步曲库 |
| `maintenance.catalog` | `apply_cn_metadata` | `refactoring.catalog.apply_cn_metadata` | 更新国服版本、定数和 Rating 缓存 |
| `maintenance.catalog` | `apply_fit_levels` | 新增，包装 `set_mct_level_batch(..., FIT)` | 更新拟合定数 |
| `maintenance.catalog` | `has_song_library` | `refactoring.catalog.has_song_library` | 判断曲库是否为空 |
| `maintenance.alias` | `sync_aliases` | 包装 `add_ma_batch` | 批量同步外部别名库 |
| `maintenance.id_mapping` | `get_pending_mappings` | 当前同名方法 | 获取待处理 shortid 映射 |
| `maintenance.id_mapping` | `resolve_mapping` | `resolve_id_mapping` | 执行一条 shortid 映射 |
| `maintenance.record` | `backfill_and_rebuild_achievements` | `backfill_record_shortids` + 后续聚合更新 | 回填历史记录并重建受影响成绩 |

## 5. 记录导入用例

### 5.1 公开入口

```python
async def ingest_records(
    user_id: int,
    records: Sequence[utils.sync.LyraRecordV3],
) -> RecordIngestResult:
    ...
```

建议结果 DTO：

```python
@dataclass
class RecordIngestResult:
    report: utils.MaiChartAchDiffReport
    unmatched_items: list[tuple[str, int]]
    affected_count: int
```

### 5.2 单事务流程

```text
ingest_records
  ├── 创建 session
  ├── _insert_records(..., session=session)
  ├── _aggregate_record_achievements(..., session=session)
  ├── _update_achievements(..., session=session)
  ├── _refresh_rating_cache(..., session=session)
  └── commit
```

任一步骤失败时整个事务回滚，避免出现“原始记录已提交，但聚合成绩或 Rating 未更新”的中间状态。

### 5.3 独立成绩更新

`achievement.update_achievements` 继续作为独立公开用例存在，用于：

- 旧版同步格式直接生成的成绩；
- 不经过 `MaiRecord` 的成绩 provider；
- 已经在调用方完成聚合的成绩输入。

`record.ingest_records` 与 `achievement.update_achievements` 共享内部 `_update_achievements` 实现，但不能互相调用公开入口，以免嵌套创建 session。

## 6. 列表查询迁移

以下类只充当静态命名空间，应转换为普通函数：

```text
get_mdt_list.genre       -> query.list_maidata_by_genre
get_mdt_list.version     -> query.list_maidata_by_version
get_mct_list.level       -> query.list_charts_by_level
get_mca_list.user        -> query.list_achievements_by_user
get_mca_list.achievement -> query.list_achievements_by_rate
get_mca_list.dxrating    -> query.list_achievements_by_dxrating
```

迁移要求：

1. 保留现有筛选、排序、`allow_utage` 和成绩加载语义。
2. 公开函数不接受 session。
3. 数据库查询移动到接受 session 的内部函数。
4. 在公开函数关闭 session 前转换为 DTO，不向调用方返回 ORM 对象。
5. `get_mca_list.b50` 不作为列表查询继续公开，B50 统一走 `b50.get_b50_data`。

## 7. 事务管理规则

### 7.1 公开写方法模板

```python
async def public_write_use_case(...) -> Result:
    async with create_session() as session:
        try:
            result = await _internal_write(..., session=session)
            await session.commit()
            return result
        except Exception:
            await session.rollback()
            raise
```

### 7.2 公开读方法模板

```python
async def public_read_use_case(...) -> Result:
    async with create_session() as session:
        value = await _internal_read(..., session=session)
        return _to_dto(value)
```

### 7.3 内部数据库方法模板

```python
async def _internal_write(
    ...,
    *,
    session: AsyncSession,
) -> Result:
    ...
```

### 7.4 强制约束

- 删除 `get_session = create_session` 别名，转为使用 ``。
- 删除 `execute_func` 类。
- 公开签名中不得出现 `session`。
- 内部数据库方法不得使用 `session=None`。
- 内部数据库方法不得创建新 session。
- 内部数据库方法不得提交或回滚事务。
- 公开方法不得调用另一个会创建 session 的公开方法；共同逻辑必须下沉为内部方法。
- 网络请求不应长期占用数据库事务；必要时由公开用例分阶段管理多个短 session。

## 8. 旧接口处置

### 8.1 被新接口完整替代，删除旧公开接口

| 旧接口 | 新接口 |
|---|---|
| `get_user_aimes` | `aime.list_for_user` |
| `get_aime` | `aime.find` |
| `get_aime_with_access4` | `aime.find_by_access4` |
| `add_aime` | `aime.link` |
| `unlink_aime` | `aime.unlink` |
| `get_ma` | `catalog.search_maidata` |
| `add_ma` | `alias.add_alias` |
| `del_ma` | `alias.remove_alias` |
| `get_mdt.id` | `catalog.get_maidata` |
| `get_mdt.title` | `catalog.search_maidata` |
| `get_b50` / `get_mca_list.b50` | `b50.get_b50_data` |

### 8.2 降为内部实现

| 当前接口 | 内部位置或包装入口 |
|---|---|
| `add_record_batch` | `_internal.record_repo._insert_records` |
| `get_record_achs` | `_internal.record_repo._aggregate_record_achievements` |
| `upd_ach_batch` | `_internal.achievement_repo._update_achievements` |
| `add_ma_batch` | `_internal` 实现，由 `maintenance.alias.sync_aliases` 包装 |
| `sync_mdt_list` | `_internal.catalog_repo` |
| `set_mdt_version_batch` | `_internal.catalog_repo` |
| `set_mct_level_batch` | `_internal.catalog_repo` |
| 所有 `rfs_*` | `_internal.rating_refresh` |
| `get_mu` / `check_mu` / `set_mu_username` | `_internal.user_repo` |
| `get_last_sy_hash` | `_internal.sync_state._get_last_source_hash`，由 `achievement.is_source_current` 包装 |
| `set_last_sy_hash` | `_internal.sync_state._set_last_source_hash`，只由 `achievement.update_achievements` 在同一事务调用 |
| `normalize_readonly_sql` | `mcp_sql._normalize_readonly_sql` |

### 8.3 无替代需求，删除

- `set_mct_level`
- `set_mct_version`
- `add_mdt`
- `add_mct`
- `get_mca`
- `set_mca`
- `get_mu_from_tgid`

列表查询方法不在删除范围内，按第 6 节迁移。

## 9. `services/__init__.py`

最终文件只保留模块导入和 `__all__`：

```python
from . import (
    achievement,
    aime,
    alias,
    archive,
    b50,
    catalog,
    mcp_sql,
    query,
    record,
    user,
    websync,
)
from . import maintenance

__all__ = [
    "achievement",
    "aime",
    "alias",
    "archive",
    "b50",
    "catalog",
    "mcp_sql",
    "query",
    "record",
    "user",
    "websync",
    "maintenance",
]
```

禁止在 `__init__.py` 中继续定义事务辅助类、函数别名或重新导出全部业务函数。调用方统一通过模块命名空间调用：

```python
await services.record.ingest_records(...)
await services.achievement.update_achievements(...)
await services.query.list_maidata_by_version(...)
await services.catalog.get_maidata(...)
await services.maintenance.catalog.sync_song_library(...)
```

## 10. 分阶段迁移顺序

### 阶段一：建立事务和内部层

1. 创建 `_internal` 包。
2. 将旧 CRUD 实现拆为强制接收 session 的内部函数。
3. 为现有公开入口增加自行管理 session 的包装。
4. 移除公开方法的 `session` 参数。
5. 确保内部函数不 commit、rollback 或创建 session。

### 阶段二：合并记录导入

1. 实现 `RecordIngestResult`。
2. 实现 `record.ingest_records` 单事务流水线。
3. 修改 matcher 和 Web API 的 v0.3 调用。
4. 实现 `maintenance.record.backfill_and_rebuild_achievements`。
5. 将三个旧方法降为内部实现。

### 阶段三：迁移列表查询

1. 创建 `query.py`。
2. 将静态方法逐个转换为普通函数。
3. 保持原筛选及排序行为。
4. 增加 ORM 到 DTO 的转换。
5. 删除 `get_mdt_list`、`get_mct_list`、`get_mca_list` 类。

### 阶段四：提升 refactoring 接口

1. 将 `refactoring.catalog`、`alias`、`aime`、`b50`、`user`、`mcp_sql` 移至正式模块。
2. 更新 matcher、Web API 和维护任务的调用路径。
3. 删除被完整替代的旧公开入口。
4. 删除 `services/refactoring`。

### 阶段五：收紧导出

1. 将维护入口移动到 `maintenance`。
2. 完成 `__init__.py` 的模块化导出。
3. 检查 services 包外是否仍有旧顶层函数调用。
4. 删除 `get_session` 和 `execute_func`。
5. 删除不再使用的旧模块和兼容代码。

## 11. 验收标准

重构完成时必须满足：

1. services 包外没有代码传入或持有 `AsyncSession`。
2. 所有公开方法签名均不包含 `session`。
3. 所有内部数据库方法均要求 `session: AsyncSession`，且没有默认值。
4. 内部数据库方法中不存在 `create_session`、`commit` 或 `rollback`。
5. `record.ingest_records` 的记录、成绩及 Rating 更新处于同一事务。
6. 列表筛选功能全部保留，且已由静态方法转换为普通函数。
7. 公开方法不返回 ORM 模型。
8. `services/__init__.py` 只包含 import 和 `__all__`。
9. `services.refactoring` 已删除。
10. 包外不存在旧顶层服务方法调用。
11. SQLite 和 PostgreSQL 下的批量写入行为均通过测试。
12. 现有 matcher、Web API、MCP 和维护任务行为保持一致。

## 12. 保留函数的内部方法拆分

本节规定每个最终保留的公开函数应如何拆分。命名可以在实现时微调，但事务边界和职责边界不得反向合并。

### 12.1 `catalog`

#### `get_maidata`

```text
get_maidata                         # 公开：创建只读 session、返回 DTO
  ├── _get_maidata_orm             # DB：按 shortid 查询并预加载所需关联
  └── _to_maidata_dto              # 纯函数：ORM -> utils.MaiData
```

内部签名建议：

```python
async def _get_maidata_orm(
    shortid: int,
    *,
    qq: int | None,
    server: ServerScope,
    provider: str | None,
    session: AsyncSession,
) -> MaiData | None:
    ...
```

查询加载选项由纯查询构造函数 `_maidata_load_options` 生成，不需要 session。

#### `search_maidata`

```text
search_maidata                      # 公开：校验 mode、创建只读 session、返回 DTO 列表
  ├── _search_maidata_orm           # DB：执行 title/name/blur 查询
  │   ├── _build_search_filter      # 纯函数：构造 SQL 条件
  │   └── _count_blur_results       # DB：模糊查询前计数
  └── _to_maidata_dto              # 纯函数：转换并设置 matched alias
```

`smart` 回退逻辑属于公开用例编排，但所有查询都必须复用同一个 session。不得通过公开 `search_maidata` 递归调用自身。

### 12.2 `query`

列表查询保留现有业务语义，但去掉静态类。每个公开函数对应一个接收 session 的 ORM 查询函数：

| 公开函数 | 内部数据库函数 | DTO 转换 |
|---|---|---|
| `list_maidata_by_genre` | `_list_maidata_by_genre_orm` | `_to_maidata_dto_list` |
| `list_maidata_by_version` | `_list_maidata_by_version_orm` | `_to_maidata_dto_list` |
| `list_charts_by_level` | `_list_charts_by_level_orm` | `_to_maichart_dto_list` |
| `list_achievements_by_user` | `_list_achievements_by_user_orm` | `_to_achievement_dto_list` |
| `list_achievements_by_rate` | `_list_achievements_by_rate_orm` | `_to_achievement_dto_list` |
| `list_achievements_by_dxrating` | `_list_achievements_by_dxrating_orm` | `_to_achievement_dto_list` |

可共享以下纯查询构造函数：

- `_maidata_query_options(qq)`
- `_chart_query_options(qq)`
- `_achievement_query_options()`
- `_normalize_numeric_range(value)`

不要将六种筛选压缩为一个接收大量可选参数的万能查询函数；它会削弱类型约束并产生难以验证的条件组合。

### 12.3 `alias`

#### `add_alias`

```text
add_alias                           # 公开：创建事务、commit、处理完整性冲突
  └── _add_alias                    # DB：检查曲目、检查重复、插入别名
      └── _song_exists              # DB：共享曲目存在性查询
```

#### `remove_alias`

```text
remove_alias                        # 公开：创建事务并 commit
  └── _remove_alias                 # DB：检查曲目、别名和所有权，然后删除
      └── _song_exists              # DB：共享查询
```

并发插入建议使用数据库冲突语句或 savepoint。内部函数不得调用 `session.rollback()` 回滚公开方法拥有的整个事务。

### 12.4 `achievement`

#### `is_source_current`

```text
is_source_current                   # 公开：创建只读 session
  └── _get_last_source_hash         # DB：读取用户指定来源的最后成功哈希
```

初期可只支持 DivingFish；内部接口应保留 `source` 参数，避免继续增加特定 provider 字段访问函数。

#### `update_achievements`

建议签名：

```python
async def update_achievements(
    user_id: int,
    achievements: Sequence[utils.MaiChartAch],
    *,
    source: str | None = None,
    source_hash: str | None = None,
) -> utils.MaiChartAchDiffReport:
    ...
```

```text
update_achievements                 # 公开：创建事务并 commit
  ├── _update_achievements          # DB：加载并插入/合并成绩
  │   ├── _normalize_achievement    # 纯函数
  │   ├── _deduplicate_achievements # 纯函数
  │   ├── _load_chart_map           # DB
  │   ├── _load_achievement_map     # DB
  │   ├── _build_diff               # 纯函数
  │   └── _apply_merged_achievement # 纯函数/ORM 赋值
  ├── _refresh_user_chart_ratings   # DB：刷新受影响谱面及用户汇总缓存
  └── _set_last_source_hash         # DB：仅在整个更新成功时写入来源哈希
```

当传入 `source_hash` 时，哈希写入必须与成绩更新同事务提交。由此删除独立公开的 `set_last_sy_hash`。

### 12.5 `record`

#### `ingest_records`

```text
ingest_records                      # 公开：拥有整个导入事务
  ├── _insert_records               # DB：批量插入原始记录并返回受影响键
  │   ├── _resolve_record_shortid   # DB：同事务内按 title/cabinet 解析 shortid
  │   └── _build_record_rows        # 纯函数：构造批量写入数据
  ├── _aggregate_record_achievements# DB：聚合受影响键的历史最佳成绩
  │   └── _merge_record_achievement # 纯函数
  ├── _update_achievements          # DB：复用 achievement 内部实现
  └── _refresh_user_chart_ratings   # DB：由成绩内部实现触发，不重复刷新
```

`_insert_records` 和 `_aggregate_record_achievements` 不再单独公开。公开结果只包含报告、未匹配项目和受影响数量，不暴露 `_RecordKey`。

### 12.6 `b50`

#### `get_b50_data`

```text
get_b50_data                        # 公开：校验 scope、创建只读 session、组装 B50Data
  ├── _get_user_for_b50             # DB：读取更新时间数据
  ├── _select_b50_entries           # DB：分别查询 b35/b15
  ├── _build_b50_entry              # 纯函数：成绩 ORM -> 曲目 DTO 条目
  └── _format_update_at             # 纯函数
```

`_select_b50_entries` 使用 `target: Literal["b35", "b15"]` 即可，不再保留旧 `get_mca_list.b50` 公开入口。

### 12.7 `user`

#### `get_or_create_from_qq`

```text
get_or_create_from_qq               # 公开：分阶段管理短事务和网络请求
  ├── _get_or_create_user           # DB：读取或创建用户
  ├── _fetch_default_username       # 外部网络调用，不持有 DB 事务
  ├── _set_username                 # DB：第二个短事务更新用户名
  └── _to_user_dto                  # 纯函数
```

不得在等待 DivingFish 网络响应时保持数据库事务。

#### `get_or_create_from_telegram`

```text
get_or_create_from_telegram         # 公开：自行完成完整编排
  ├── _get_qq_from_telegram         # DB
  ├── _get_or_create_user           # DB：与 QQ 入口共享
  ├── _fetch_default_username       # 网络调用
  ├── _set_username                 # DB
  └── _to_user_dto                  # 纯函数
```

为避免公开方法嵌套创建 session，该方法不直接调用公开的 `get_or_create_from_qq`；允许复用内部函数，公开编排代码可少量重复。

#### `get_qq_from_telegram`

```text
get_qq_from_telegram                # 公开：只读 session
  └── _get_qq_from_telegram         # DB：返回 int | None
```

#### `link_telegram` / `unlink_telegram`

```text
link_telegram                       # 公开：事务入口
  └── _link_telegram                # DB：校验用户及绑定冲突并写入

unlink_telegram                     # 公开：事务入口
  └── _unlink_telegram              # DB：清除绑定
```

新的内部实现应明确处理目标用户不存在、Telegram 已绑定其他 QQ 等情况，不能继续静默不更新。

### 12.8 `aime`

| 公开函数 | 内部数据库函数 | 纯函数/共享函数 |
|---|---|---|
| `link` | `_link_aime` | `_normalize_access`、`_raise_linked` |
| `unlink` | `_unlink_aime` | `_normalize_access` |
| `find` | `_find_aime` | `_normalize_access`、`_to_aime_found_info` |
| `find_by_access4` | `_find_aime_by_access4` | `_normalize_access4`、`_to_aime_found_info` |
| `list_for_user` | `_list_aimes_for_user` | `_to_aime_info` |

`link` 的并发插入冲突必须使用 savepoint 或数据库 upsert 处理。不得在 `_link_aime` 中执行整个 session 的 rollback 后再查询。

### 12.9 `websync`

#### `create_pairing_code`

```text
create_pairing_code                 # 公开：限制 TTL、事务入口
  ├── _get_or_create_user           # DB：复用 user repo
  ├── _issue_pairing_code           # DB：生成唯一哈希并覆盖用户旧记录
  ├── _generate_pairing_secret      # 纯函数/随机源
  └── _hash_text                    # 纯函数
```

#### `exchange_pairing_code`

```text
exchange_pairing_code               # 公开：规范化输入、事务入口
  ├── _consume_pairing_code         # DB：校验并标记配对码已使用
  ├── _revoke_user_tokens           # DB
  ├── _generate_access_token        # 纯函数/随机源
  └── _hash_text                    # 纯函数
```

为防止并发重复兑换，`_consume_pairing_code` 应使用条件更新或行锁，而不是简单“先查再改”。

#### `authenticate_access_token`

```text
authenticate_access_token           # 公开：规范化 token、事务入口
  └── _authenticate_access_token     # DB：验证 token 并更新 last_used_at
```

该方法虽然以查询为主，但会更新最后使用时间，因此属于写事务。

### 12.10 `archive`

#### `update_telegram_file_id`

```text
update_telegram_file_id             # 公开：校验 kind、事务入口
  └── _update_telegram_file_id       # DB：执行目标缓存列更新
```

用 `kind: Literal["adx", "zip"]` 替代语义不明确的 `endname`。

### 12.11 `mcp_sql`

#### `sql_query`

```text
sql_query                           # 公开：规范化 SQL、创建只读事务、序列化结果
  ├── _normalize_readonly_sql       # 纯函数：解析、验证、表名映射和 LIMIT
  ├── _execute_readonly_sql         # DB：设置超时并执行 SQL
  └── _json_safe                    # 纯函数：结果序列化
```

`_normalize_readonly_sql` 不再进入 `__all__`。`ReadOnlySqlError` 仍作为 `sql_query` 的公开错误类型保留。

### 12.12 `maintenance.catalog`

#### `sync_song_library`

```text
sync_song_library                   # 公开维护入口：事务入口
  ├── _map_song_dtos_to_orm         # 纯函数
  └── _upsert_song_library          # DB：更新曲目及谱面
      ├── _load_existing_songs      # DB
      ├── _apply_song_fields        # 纯函数/ORM 赋值
      └── _merge_song_charts        # 纯函数/ORM 关系更新
```

#### `apply_cn_metadata`

```text
apply_cn_metadata                   # 公开维护入口：单事务
  ├── _normalize_level_updates      # 纯函数
  ├── _update_song_versions         # DB：批量更新 version_cn
  ├── _update_chart_levels          # DB：批量更新 lv_cn
  └── _refresh_chart_ratings        # DB：刷新受影响成绩和用户缓存
```

#### `apply_fit_levels`

```text
apply_fit_levels                    # 公开维护入口：事务入口
  ├── _normalize_level_updates      # 纯函数
  └── _update_chart_levels          # DB：指定 SLevelSource.FIT
```

拟合定数目前不参与正式 JP/CN Rating 计算，因此不触发 Rating 刷新；若未来计算规则改变，再显式加入。

#### `has_song_library`

```text
has_song_library                    # 公开维护入口：只读 session
  └── _has_song_library             # DB：执行 exists/limit 查询
```

### 12.13 `maintenance.alias`

#### `sync_aliases`

```text
sync_aliases                        # 公开维护入口：事务入口
  ├── _normalize_alias_rows         # 纯函数：去重、清理空别名
  ├── _load_existing_song_ids       # DB：过滤不存在曲目
  └── _insert_aliases_ignore_conflict # DB：按方言批量 upsert
```

该接口保留 `source` 或 `creator_id` 参数，以区分 YuzuChaN、LXNS 等维护来源；不复用面向用户权限校验的 `alias.add_alias`。

### 12.14 `maintenance.id_mapping`

#### `get_pending_mappings`

```text
get_pending_mappings                # 公开维护入口：只读 session
  └── _get_pending_mappings         # DB
```

#### `resolve_mapping`

```text
resolve_mapping                     # 公开维护入口：单映射事务
  └── _resolve_mapping              # DB：总体编排
      ├── _load_mapping_source      # DB
      ├── _load_mapping_target      # DB
      ├── _copy_song_to_target      # DB/ORM：目标不存在
      ├── _merge_song_into_target   # DB/ORM：目标存在
      ├── _merge_achievement        # 纯函数/ORM 赋值
      └── _delete_mapping_rule      # DB
```

每一条映射独立提交，避免一个坏映射回滚整批维护任务。内部删除不能再吞掉所有异常；预期的不存在情况应显式判断，其他数据库异常必须向上传播。

### 12.15 `maintenance.record`

#### `backfill_and_rebuild_achievements`

```text
backfill_and_rebuild_achievements   # 公开维护入口
  ├── _backfill_record_shortids     # DB：回填并按用户返回受影响键
  ├── _aggregate_record_achievements# DB：复用 record repo
  ├── _update_achievements          # DB：复用 achievement repo
  └── _refresh_user_chart_ratings   # DB：由成绩更新触发
```

数据量较小时可以使用一个事务。若历史记录量可能很大，公开方法应按用户或固定批次分别创建短事务；批次边界由公开维护用例管理，内部函数仍不得 commit。

## 13. 内部复用关系

为避免新分包再次产生循环导入，内部依赖方向固定为：

```text
公开业务模块 / maintenance
        ↓
_internal.record_repo
        ↓
_internal.achievement_repo
        ↓
_internal.rating_refresh
        ↓
_internal.catalog_repo / user_repo / sync_state
        ↓
models
```

约束：

1. `_internal` 不导入公开业务模块。
2. 公开模块之间不通过对方的公开函数复用数据库逻辑。
3. 共享数据库逻辑下沉到 `_internal`。
4. 共享纯函数可放在最贴近业务的模块，不必全部集中到通用 `utils.py`。
5. `maintenance` 可以依赖 `_internal`，但稳定业务模块不依赖 `maintenance`。
