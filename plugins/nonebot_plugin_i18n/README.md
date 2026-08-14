# nonebot-plugin-i18n

基于 NoneBot 的轻量语言国际化插件，通过依赖注入向协程上下文注入语言包，为插件提供多语言回复能力。

## 使用方式

### 1. 初始化

在插件的 `__init__.py` 或 `matcher.py` 中创建一个 i18n 实例，指向你的语言包目录：

```python
from pathlib import Path
from plugins.nonebot_plugin_i18n import use_i18n, reply

i18n_dir = Path(__file__).parent / "assets" / "i18n"
i18n = use_i18n(i18n_dir)
```

### 2. 在 handler 中注入

```python
@matcher.handle()
async def my_handler(bot: Bot, event: Event, matcher: Matcher, _i18n = i18n):
    current_i18n_data.set(_i18n)
    await matcher.send(reply("my_key", username="Alice"))
```

### 3. 编写语言包 YAML

在 `assets/i18n/` 下创建 `zh_CN.yaml`：

```yaml
my_key: "你好，{username}！"
language_name: "中文"
```

支持嵌套、列表随机选择、参数格式化。

## ⚠️ 注意事项

### 1️⃣ ContextVar 跨协程上下文丢失

`current_i18n_data` 是一个 `contextvars.ContextVar`。NoneBot 的依赖注入系统在执行 dependency 函数和 handler 函数时，**运行在不同的协程上下文中**。这意味着：

```python
# ❌ 错误的写法：_ 接收了依赖注入的返回值，但没有 set 到 handler 上下文
async def my_handler(..., _ = i18n):
    reply("xxx")  # reply() 读 ContextVar → {} 空字典！
```

```python
# ✅ 正确的写法：用命名参数接收返回值，在 handler 入口处手动 set
async def my_handler(..., _i18n = i18n):
    current_i18n_data.set(_i18n)   # 在 handler 上下文里 set
    reply("xxx")                    # 现在能正常读取了
```

**要点：**
- 不要用 `_` 作为参数名（会被当作丢弃变量）
- dependency 函数需要 `return i18n_data`（`use_i18n` 已内置）
- 在每个 handler 入口处调用 `current_i18n_data.set(_i18n)`

### 2️⃣ reply() 参数名必须与模板一致

模板中使用 `{变量名}` 占位时，`reply()` 传入的关键字参数名必须完全匹配：

```yaml
# zh_CN.yaml
greeting: "你好，{username}！"
```

```python
reply("greeting", username="Alice")  # ✅ → "你好，Alice！"
reply("greeting", name="Alice")      # ❌ → "你好，{username}！"
```

`SafeFormatter` 找不到参数不会报错，只会原样输出 `{变量名}`。

### 3️⃣ 传显示名而不是用户 ID

模板中的 `{username}` 期望的是可读的显示名称，不是数字 QQ 号：

```python
# 先获取显示名
target_username = await get_user_display_name(bot, group_id, user_id)
# 再传入
reply("greeting", username=target_username)  # ✅
reply("greeting", username=user_id)          # ❌ → 显示 QQ 号
```

### 4️⃣ dependency 需要 `bot` 参数

`i18n_dependency` 内部需要 `bot.adapter.get_name()` 获取平台信息，以及 `event.get_user_id()` 获取用户 ID 来查询数据库中的语言设置。

如果 handler 的签名中缺少 `bot: Bot` 参数，dependency 拿不到适配器信息，语言包加载会静默失败：

```python
# ❌ 缺少 bot 参数 → dependency 拿不到 adapter
async def handler(event: Event, matcher: Matcher, _i18n = i18n):

# ✅ 必须加上 bot 参数
async def handler(bot: Bot, event: Event, matcher: Matcher, _i18n = i18n):
```

### 5️⃣ 语言包降级策略

语言加载的查找顺序为：目标语言 → `zh_CN` → `en_US`。建议至少提供 `zh_CN.yaml` 作为保底。

## 语言文件结构

```
assets/i18n/
├── zh_CN.yaml    # 简体中文
├── en_US.yaml    # 英文（可选）
└── ja.yaml       # 日文（可选）
```

## 切换语言

用户可通过以下指令切换语言：
```
切换语言 zh_CN
set_lang en_US
lang ja
```