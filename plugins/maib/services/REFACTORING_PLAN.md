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
| `achievement` | `update_achievements` | `upd_ach_batch` | 写入已经聚合好的成绩并刷新派生缓存 |
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
| `get_last_sy_hash` / `set_last_sy_hash` | `_internal.sync_state` |
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

