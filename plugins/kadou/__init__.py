from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import asyncio
import json

from nonebot import require, logger, on_regex
from nonebot.adapters.onebot.v11 import GroupMessageEvent as OneBotV11GroupMessageEvent
from nonebot.params import RegexDict

require("nonebot_plugin_localstore")
require("nonebot_plugin_locales")
from nonebot_plugin_localstore import get_plugin_data_dir
from nonebot_plugin_locales import locales_init

Reply = locales_init(Path(__file__).parent / "assets" / "lang")

# 初始化插件数据目录
data_dir = get_plugin_data_dir()
data_dir.mkdir(parents=True, exist_ok=True)

# 同一群的数据更新必须串行执行，避免“读取旧值 -> 分别写回”造成覆盖。
# 此锁仅在当前进程生效；多进程/多实例部署应使用数据库事务或进程间锁。
group_locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

# ================= 基础 IO 函数 =================

def load_json(path: Path) -> dict:
    if not path.exists():
        return {}

    raw_data = ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw_data = f.read()
        data = json.loads(raw_data)
        if not isinstance(data, dict):
            logger.error(
                "JSON 根节点不是对象，按空数据处理：path=%s，原始内容=%r",
                path,
                raw_data,
            )
            return {}
        return data
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        # 损坏文件不应阻断 matcher；保留异常堆栈和尽可能读取到的原始内容以便排查。
        logger.exception(
            "读取 JSON 失败，按空数据继续处理：path=%s，原始内容=%r",
            path,
            raw_data,
        )
        return {}

def save_json(path: Path, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def now_local() -> datetime:
    """Return the business time in UTC+8, independent of host timezone."""
    tz=timezone(timedelta(hours=8), name="UTC+8")
    return datetime.now(tz)

# ================= 核心上下文获取 =================

def get_store_context(event: OneBotV11GroupMessageEvent, name: str, is_hider: bool = False):
    """
    通用上下文获取函数
    is_hider=True 时，读取 hider_manifest.json 和 hider_kadou 字段
    """
    manifest_file = "hider_manifest.json" if is_hider else "manifest.json"
    manifest = load_json(data_dir / manifest_file)
    data_id = manifest.get(str(event.group_id))
    if not data_id:
        return None

    file_path = data_dir / f"{data_id}.json"
    data = load_json(file_path)

    info = data.get("info", {})
    store_info = info.get(name)
    if not store_info:
        return None

    store_id = str(store_info.get("id"))
    kadou_key = "hider_kadou" if is_hider else "kadou"

    # 确保 data 中存在对应的 kadou 键，便于直接引用修改
    if kadou_key not in data:
        data[kadou_key] = {}
    kadou = data[kadou_key]

    if store_id not in kadou:
        kadou[store_id] = {"num": 0, "time": ""}

    return {
        "data": data,
        "file_path": file_path,
        "store_info": store_info,
        "store_id": store_id,
        "kadou": kadou,
    }

# ================= 通用业务逻辑 =================

async def format_status(
    label: str, kadou_data: dict, today_str: str, *,
    prefix: str = "",
    hider: bool = False,
    hider_indent: str = "",
) -> str:
    """Format a localized status message."""
    time_str = kadou_data.get("time", "")

    if time_str[:10] != today_str:
        key = "status.hider.not_updated" if hider else "status.common.not_updated"
        if hider:
            return await Reply(key, hider_indent=hider_indent)
        return await Reply(key, prefix=prefix, label=label)

    num = kadou_data.get("num", 0)
    display_time = time_str[11:] if len(time_str) > 10 else time_str
    key = "status.hider.updated" if hider else "status.common.updated"
    if hider:
        return await Reply(key, hider_indent=hider_indent, num=num, display_time=display_time)
    return await Reply(key, prefix=prefix, label=label, num=num, display_time=display_time)

def calculate_new_num(current_num: int, sign: str | None, change_num: int) -> tuple[int, str | None]:
    """
    通用人数计算
    返回: (新数值, 错误信息)
    """
    if not sign:
        return change_num, None
    if sign == "+":
        return current_num + change_num, None
    if sign == "-":
        new_num = current_num - change_num
        if new_num < 0:
            return current_num, "减少后人数小于0人，请确定"
        return new_num, None
    return current_num, None

def execute_update(ctx: dict, sign: str | None, num: int) -> tuple[int, str | None]:
    """
    通用更新执行函数
    处理跨天重置、计算、保存
    """
    store_id = ctx["store_id"]
    store_kadou = ctx["kadou"][store_id]
    today_str = now_local().date().isoformat()
    time_str = store_kadou.get("time", "")

    # 非当日数据重置；包含异常或未来日期，避免它们被误视为今天已更新。
    if time_str[:10] != today_str:
        store_kadou["num"] = 0

    current_num = store_kadou.get("num", 0)
    new_num, error_msg = calculate_new_num(current_num, sign, num)

    if error_msg:
        return current_num, error_msg

    store_kadou["num"] = new_num
    store_kadou["time"] = now_local().strftime("%Y-%m-%d %H:%M")

    # 由于 kadou 是 data 的引用，直接保存即可
    save_json(ctx["file_path"], ctx["data"])

    return new_num, None

def sync_to_hider(event: OneBotV11GroupMessageEvent, name: str, current_num: int):
    """普通更新时，同步数据到 Hider"""
    hider_manifest = load_json(data_dir / "hider_manifest.json")
    hider_data_id = hider_manifest.get(str(event.group_id))
    if not hider_data_id:
        return

    hider_file_path = data_dir / f"{hider_data_id}.json"
    hider_data = load_json(hider_file_path)

    hider_info = hider_data.get("info", {})
    hider_store_info = hider_info.get(name)
    if not hider_store_info:
        return

    hider_store_id = str(hider_store_info.get("id"))

    if "hider_kadou" not in hider_data:
        hider_data["hider_kadou"] = {}
    hider_kadou = hider_data["hider_kadou"]

    if hider_store_id not in hider_kadou:
        hider_kadou[hider_store_id] = {"num": 0, "time": ""}

    hider_kadou[hider_store_id]["num"] = current_num
    hider_kadou[hider_store_id]["time"] = now_local().strftime("%Y-%m-%d %H:%M")

    save_json(hider_file_path, hider_data)

# ================= Matcher 1: 查询单店 (含 Hider) =================

matcher_query = on_regex(r"^(?P<name>\S{1,2})几$", priority=10, block=True)

@matcher_query.handle()
async def _(event: OneBotV11GroupMessageEvent, args: dict = RegexDict()):
    name = args.get("name", "")
    ctx = get_store_context(event, name, is_hider=False)
    if not ctx:
        return

    store_info = ctx["store_info"]
    store_kadou = ctx["kadou"][ctx["store_id"]]
    today_str = now_local().date().isoformat()
    store_name = store_info.get("name", name)

    manifest = load_json(data_dir / "manifest.json")
    data_id = manifest.get(str(event.group_id), "")
    prefix_text = await Reply("status.prefix", city_id=data_id) if data_id else ''
    msg = await format_status(store_name, store_kadou, today_str, prefix=prefix_text)

    # Hider 数据（仅当群有 hider 权限时显示）
    hider_ctx = get_store_context(event, name, is_hider=True)
    if hider_ctx:
        hider_kadou = hider_ctx["kadou"][hider_ctx["store_id"]]
        hider_msg = await format_status("Hider", hider_kadou, today_str, hider=True, hider_indent=" "*4)
        msg += f"\n{hider_msg}"

    await matcher_query.finish(msg)

# ================= Matcher 2: 普通更新 (同步 Hider) =================

matcher_update = on_regex(r"^(?P<name>\S{1,2})(?P<sign>[+-])?(?P<num>\d+)$", priority=10, block=True)

@matcher_update.handle()
async def _(event: OneBotV11GroupMessageEvent, args: dict = RegexDict()):
    name = args.get("name", "")
    sign = args.get("sign")
    num = int(args.get("num", 0))

    # 普通更新与 Hider 同步共享同一个读-改-写临界区。
    async with group_locks[event.group_id]:
        ctx = get_store_context(event, name, is_hider=False)
        if not ctx:
            return

        new_num, error_msg = execute_update(ctx, sign, num)
        if error_msg:
            await matcher_update.finish(await Reply("errors.num_less_than_zero"))

        sync_to_hider(event, name, new_num)

        store_info = ctx["store_info"]
        store_name = store_info.get("name", name)
        await matcher_update.finish(
            await Reply("update.success", store_name=store_name, new_num=new_num)
        )

# ================= Matcher 3: Hider 独立更新 =================

matcher_hider_update = on_regex(r"^[.。](?P<name>\S{1,2})(?P<sign>[+-])?(?P<num>\d+)$", priority=10, block=True)

@matcher_hider_update.handle()
async def _(event: OneBotV11GroupMessageEvent, args: dict = RegexDict()):
    name = args.get("name", "")
    sign = args.get("sign")
    num = int(args.get("num", 0))

    # 与普通更新共用锁，避免 Hider 独立更新和普通更新同步相互覆盖。
    async with group_locks[event.group_id]:
        ctx = get_store_context(event, name, is_hider=True)
        if not ctx:
            return

        new_num, error_msg = execute_update(ctx, sign, num)
        if error_msg:
            await matcher_hider_update.finish(await Reply("errors.num_less_than_zero"))

        store_info = ctx["store_info"]
        store_name = store_info.get("name", name)
        await matcher_hider_update.finish(
            await Reply("update.hider_success", store_name=store_name, new_num=new_num)
        )

# ================= Matcher 4: 遍历输出 (/j) =================

matcher_list = on_regex(r"^/j$", priority=10, block=True)

@matcher_list.handle()
async def _(event: OneBotV11GroupMessageEvent):
    manifest = load_json(data_dir / "manifest.json")
    data_id = manifest.get(str(event.group_id))
    if not data_id:
        return

    file_path = data_dir / f"{data_id}.json"
    data = load_json(file_path)

    info = data.get("info", {})
    kadou = data.get("kadou", {})

    if not info:
        return

    today_str = now_local().date().isoformat()
    HIDER_INDENT = " "*4
    messages = []

    for name_key, store_info in info.items():
        store_id = str(store_info.get("id"))
        store_name = store_info.get("name", name_key)

        store_kadou = kadou.get(store_id, {"num": 0, "time": ""})
        prefix_text = await Reply("status.prefix", city_id=data_id) if data_id else ''
        line = await format_status(store_name, store_kadou, today_str, prefix=prefix_text)

        # Hider（仅当群有 hider 权限时显示）
        hider_ctx = get_store_context(event, name_key, is_hider=True)
        if hider_ctx:
            hider_kadou = hider_ctx["kadou"][hider_ctx["store_id"]]
            hider_line = await format_status(
                "Hider", hider_kadou, today_str,
                hider=True, hider_indent=HIDER_INDENT,
            )
            line += f"\n{hider_line}"

        messages.append(line)

    if messages:
        await matcher_list.finish("\n".join(messages))
