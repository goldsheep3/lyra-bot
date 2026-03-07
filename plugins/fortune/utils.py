import json
from datetime import datetime
from hashlib import md5
from pathlib import Path

import anyio

from nonebot.adapters.onebot.v11 import Message, MessageSegment
from nonebot_plugin_localstore import get_plugin_data_dir


# --- Fortune Calculation ---

# 运势权重列表，根据计算值决定吉凶
FORTUNE_WEIGHTS: list[tuple[int, str]] = [
    (400, "大吉"),
    (1000, "吉"),
    (1600, "中吉"),
    (2800, "小吉"),
    (3200, "平吉"),
    (3600, "小凶"),
    (3875, "凶"),
    (4096, "大凶"),
]

def get_fortune(timestamp: int, user_id: int, items: str | list[str]) -> list[str]:
    """
    根据时间戳、用户ID和运势项目列表生成确定性的运势结果。
    如果只提供一个项目名称（字符串），会自动处理为列表。

    Args:
        timestamp: 当日零点时间戳
        user_id: 用户 ID
        items: 一个或多个运势项目的名称

    Returns:
        与项目列表顺序对应的运势结果列表
    """
    if isinstance(items, str):
        items = [items]

    date_str = datetime.fromtimestamp(timestamp).strftime("%Y%m%d")
    user_id_str = str(user_id)

    def _calculate(item_name: str) -> str:
        """内部函数，计算单个项目的运势"""
        source_str = f"{user_id_str}_{date_str}_{item_name}".encode("utf-8")
        hash_hex = md5(source_str).hexdigest()
        # 截取哈希值的一部分用于计算
        value_hex = hash_hex[2:5]
        decimal_value = int(value_hex, 16)

        for limit, name in FORTUNE_WEIGHTS:
            if decimal_value < limit:
                return name
        return FORTUNE_WEIGHTS[-1][1]

    return [_calculate(item) for item in items]


# --- Data and Message Handling ---

# 自动获取插件数据目录并定义文件路径
_FORTUNE_ITEMS_FILE = get_plugin_data_dir() / "fortune_items.json"
_FORTUNE_ITEMS_CACHE: dict[str, list[str]] = {}
_FORTUNE_DESC_FILE = get_plugin_data_dir() / "fortune_desc.json"
_FORTUNE_DESC_CACHE: dict[str, list[str]] = {}

async def _load_items() -> dict[str, list[str]]:
    """私有函数：从 JSON 加载原始数据"""
    path = anyio.Path(_FORTUNE_ITEMS_FILE)
    if not await path.exists():
        return {}
    try:
        content = await path.read_text(encoding="utf-8")
        return json.loads(content)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}

async def _save_items(data: dict[str, list[str]]):
    """异步私有函数：持久化并刷新缓存"""
    content = json.dumps(data, ensure_ascii=False, indent=4)
    async_path = anyio.Path(_FORTUNE_ITEMS_FILE)
    await async_path.write_text(content, encoding="utf-8")
    
    _FORTUNE_ITEMS_CACHE.clear()

async def get_fortune_items(group_id: int) -> list[str]:
    gid_str = str(group_id)
    if gid_str in _FORTUNE_ITEMS_CACHE:
        return _FORTUNE_ITEMS_CACHE[gid_str]

    data = await _load_items()
    if gid_str not in data:
        await set_fortune_items(group_id)  # 初始化默认项
        data = await _load_items()  # 重新加载以获取默认项

    _FORTUNE_ITEMS_CACHE[gid_str] = data[gid_str]
    return data[gid_str]

async def set_fortune_items(group_id: int, items: list[str] | None = None):
    """设置运势项，items 为 None 时使用硬编码默认值"""
    if items is None:
        # 在这里定义你的默认初始项
        items = ["舞萌", "中二", "太鼓", "PJSK", "雀魂", "MC"]
    
    data = await _load_items()
    data[str(group_id)] = items
    await _save_items(data)

async def add_fortune_item(group_id: int, item: str) -> bool:
    """添加单项：获取 -> 查重 -> 设置"""
    current_items = await get_fortune_items(group_id)
    
    if item in current_items:
        return False
    
    # 组合新列表并保存
    new_items = [*current_items, item]
    await set_fortune_items(group_id, new_items)
    return True

async def get_fortune_desc(fortune: str) -> list[str]:
    """根据运势结果返回对应的描述文本"""
    global _FORTUNE_DESC_CACHE

    if not _FORTUNE_DESC_CACHE:
        desc_async_path = anyio.Path(_FORTUNE_DESC_FILE)
        if await desc_async_path.exists():
            try:
                _FORTUNE_DESC_CACHE = json.loads(
                    await desc_async_path.read_text(encoding="utf-8")
                )
            except:
                _FORTUNE_DESC_CACHE = {}

        # 如果加载失败或为空，尝试加载默认文件
        if not _FORTUNE_DESC_CACHE:
            default_path = Path(__file__).parent / "default_fortune_desc.json"
            default_async_path = anyio.Path(default_path)
            if await default_async_path.exists():
                try:
                    _FORTUNE_DESC_CACHE = json.loads(
                        await default_async_path.read_text(encoding="utf-8")
                    )
                except:
                    _FORTUNE_DESC_CACHE = {}

    return _FORTUNE_DESC_CACHE.get(fortune, [])

async def build_fortune_message(today_timestamp: int, user_id: int, fortune_data: list[tuple[str, str]]) -> Message:
    """
    构建运势结果的最终消息。

    Args:
        today_timestamp: 当日零点时间戳
        user_id: 用户 ID
        fortune_data: 一个包含 (项目名, 运势结果) 元组的可迭代对象

    Returns:
        构建好的 Message 对象
    """
    fortunes = {fortune: [] for fortune in ["大吉", "吉", "中吉", "小吉", "平吉", "小凶", "凶", "大凶"]}
    for item, fortune in fortune_data[1:]:  # 跳过总运势信息
        fortunes[fortune].append(item)

    main_fortune = fortune_data[0][1]  # 总运势结果
    desc = await get_fortune_desc(main_fortune)
    main_desc = desc[(today_timestamp + user_id) % len(desc)] if desc else ''
    msg = [
        f"小梨来啦！你今天的运势是：【{main_fortune}】！",
        main_desc,
        '',
        "今日你的特别运势："
    ]
    for fortune, items in fortunes.items():
        if items:
            item_str = " ".join(items)
            msg.append(f"【{fortune}】{item_str}")
    msg.append("无论运势如何，小梨都在陪着你呢！")
    result = Message('\n'.join(msg))
    return result
