# lyra-maisync 同步模块设计

> 接收篡改猴脚本导出的 `.json.gz.b64` 数据，支持批量导入最佳成绩和游玩历史。
> 两条路径：`file_receiver`（私聊发文件）和 `Sync API`（HTTP POST）。

---

## 目录结构

```
maib/sync/
├── __init__.py        # 导出 & 模块初始化
├── decoder.py         # 共享：前缀检测 → base64 → gzip → JSON
├── service.py         # 共享：存表 + 合并最优 + 生成 report
├── auth.py            # 独有：rolling hash 链认证
├── api.py             # 独有：FastAPI POST /v1/sync
└── models.py          # 数据库模型
```

---

## 数据格式

### 输入格式

篡改猴脚本导出的 `.json.gz.b64` 文件内容：

```
lyra_maisync:json.gz.base64:v0.3.0;{base64编码的gzip压缩JSON}
```

解码后 JSON 结构：

```json
[
  {
    "sheetId": "Link__dxrt__sd__dxrt__4",
    "title": "Link",
    "type": "sd",
    "diff": "Expert",
    "achievement": 100.0,
    "dxscore": 425,
    "combo": "fc",
    "sync": "fs",
    "play_time": "2026-07-01 12:34:56",
    "_record_type": "history"     // 标记字段，下同
  },
  {
    "sheetId": "Link__dxrt__sd__dxrt__4",
    "title": "Link",
    "type": "sd",
    "diff": "Expert",
    "achievement": 100.5,
    "dxscore": 429,
    "combo": "ap",
    "sync": "fdx",
    "play_time": "",
    "_record_type": "best"        // 最佳记录（无 play_time）
  }
]
```

- `_record_type = "history"`：全量游玩历史，带 `play_time`
- `_record_type = "best"`：最佳成绩快照，无 `play_time`
- `_record_type` 缺失时：默认按 `play_time` 是否为空判断

---

## 数据库模型

### `maib_sync_users` — 同步认证

```python
class SyncUser(Model):
    __tablename__ = "maib_sync_users"

    user_id: int            # QQ 号 (PK)
    current_hash: str       # 当前滚动 hash
    hash_platform: str      # 发起 sync 的平台 ("OneBot V11" / "Telegram")
    created_at: int
    updated_at: int
```

### `maib_play_history` — 全量游玩历史

```python
class PlayHistory(Model):
    __tablename__ = "maib_play_history"

    id: int                 # 自增 PK
    user_id: int            # QQ 号
    sheet_id: str           # 曲目标识
    title: str
    type: str               # "sd" / "dx"
    diff: str
    achievement: float
    dxscore: int
    combo: str
    sync: str
    play_time: str          # 游玩时间，去重依据
    raw_data: str | None    # 原始 JSON 备份
    created_at: int

    # 唯一约束：(user_id, sheet_id, play_time)
```

### `maib_play_best` — 最佳成绩快照

```python
class PlayBest(Model):
    __tablename__ = "maib_play_best"

    user_id: int            # QQ 号 (PK1)
    sheet_id: str           # 曲目标识 (PK2)
    title: str
    type: str
    diff: str
    achievement: float
    dxscore: int
    combo: str
    sync: str
    updated_at: int

    # 主键：(user_id, sheet_id) — 覆盖更新
```

---

## 处理流程

### 共享解码流程（`decoder.py` + `service.py`）

```
                    ┌──────────────────────┐
                    │  原始数据字符串        │
                    │  "lyra-maisync_v3..." │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │  检测前缀头            │
                    │  "lyra-maisync_v3."   │
                    └──────────┬───────────┘
                         失败  │  成功
                        ┌─────┘
                        ▼
                  返回 None
                               │
                               ▼
                    ┌──────────────────────┐
                    │  去掉前缀 → base64    │
                    │  → gzip 解压 → JSON  │
                    └──────────┬───────────┘
                         失败  │  成功
                        ┌─────┘
                        ▼
                  返回 None
                               │
                               ▼
                    ┌──────────────────────┐
                    │  遍历 JSON 数组        │
                    │  按 _record_type 分流  │
                    └──────┬───────────────┘
                           │
             ┌─────────────┴─────────────┐
             ▼                           ▼
    ┌──────────────────┐      ┌──────────────────┐
    │  history 类       │      │  best 类          │
    │  → play_history   │      │  → play_best      │
    │  (user_id,sheet,  │      │  (user_id,sheet   │
    │   play_time 去重)  │      │   PK, 覆盖更新)   │
    └────────┬─────────┘      └────────┬─────────┘
             │                         │
             └─────────────┬───────────┘
                           ▼
                    ┌──────────────────────┐
                    │  合并最优到            │
                    │  maib_maichartachs    │
                    │  (取 history + best   │
                    │   的最高 achievement) │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │  生成 report           │
                    │  新增/更新/漏报统计    │
                    └──────────────────────┘
```

### 路径 A：`file_receiver`

```
私聊发 .json.gz.b64 文件
       │
       ▼
检测 QQ 号 → 获取 user_id
       │
       ▼
调用 decoder.decode() → service.process()
       │
       ▼
直接回复 report 给当前聊天窗口
（不做认证，私有聊天天然安全）
```

### 路径 B：`Sync API`

```
POST /v1/sync
Body: { user_id, code, next_hash, data }
       │
       ▼
提取 user_id, code, next_hash  ← 轻量操作
       │
       ▼
auth.verify_and_roll(user_id, code, next_hash)
       │
  ┌────┴────┐
  │  失败   │  成功
  ▼        ▼
返回 401  调用 decoder.decode() → service.process()
不碰 data       │
                ▼
         生成 report
                │
                ▼
         返回 API 响应
                │
                ▼
         同时推送到 hash_platform 用户
         （如 QQ 私聊发送 report）
```

---

## 认证流程（`auth.py`）

### 初始化

```
用户发 "获取同步码"
  → 生成 6 位 InitialCode
  → current_hash = SHA256(InitialCode)
  → 存 SyncUser(user_id, current_hash, hash_platform)
  → 返回 InitialCode 给用户
```

### 数据同步

```
客户端（篡改猴）：
  last_hash = SHA256(InitialCode)
  code = 随机串
  next_hash = SHA256(last_hash + code)
  → POST { user_id, code, next_hash, data }

服务端：
  current_hash = 从 DB 查
  computed = SHA256(current_hash + code)
  if computed != next_hash → 401
  current_hash = next_hash  ← 滚动
  保存数据
```

---

## API 接口

### `POST /v1/sync`

**请求：**
```json
{
  "user_id": 2940119626,
  "code": "abc123",
  "next_hash": "sha256hex...",
  "data": "lyra-maisync_v3.base64;..."
}
```

**响应（成功）：**
```json
{
  "success": true,
  "message": "同步成功！保存 120 条记录，更新 15 条成绩",
  "saved_history": 100,
  "saved_best": 20,
  "merged_count": 15,
  "unmatched": ["曲目A", "曲目B"]
}
```

**响应（认证失败）：**
```json
{
  "success": false,
  "message": "认证失败，请重新获取同步码"
}
```

---

## 模块依赖关系

```
matcher.py
  ├── sync/decoder.py     ← 调用解码
  ├── sync/service.py     ← 调用存库 + 合并
  └── services.py         ← 现有曲目查询

sync/api.py
  ├── sync/auth.py        ← 调用认证
  ├── sync/decoder.py     ← 调用解码
  ├── sync/service.py     ← 调用存库 + 合并
  └── services.py         ← 现有曲目查询
```

---

## 实施步骤

1. 建 `sync/models.py`：`SyncUser`、`PlayHistory`、`PlayBest`
2. 写 `sync/decoder.py`：前缀检测 + base64 + gzip + JSON
3. 写 `sync/service.py`：存表 + 合并最优 + 生成 report
4. 写 `sync/auth.py`：rolling hash 认证
5. 写 `sync/api.py`：FastAPI 路由
6. 改 `file_receiver`：调用 decoder + service
7. 注册 `获取同步码` 命令
8. 测试