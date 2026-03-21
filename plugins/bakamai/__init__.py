"""
Minecraft 服务器自助过白插件
支持 Java 版和 Bedrock 版白名单自动添加
"""

import json
from typing import Optional, Literal, Tuple
from pydantic import BaseModel

import httpx
import paramiko
from mcrcon import MCRcon

from nonebot import on_regex, require, get_plugin_config
from nonebot.adapters.onebot.v11 import Bot, MessageEvent
from nonebot.log import logger
from nonebot.permission import SUPERUSER

require("nonebot_plugin_localstore")
from nonebot_plugin_localstore import get_plugin_data_file


# ==================== 配置常量 ====================

class Config(BaseModel):
    bakamai_allowed_groups: list[int] = []

    bakamai_ssh_host: str = ""
    bakamai_ssh_port: int = 0
    bakamai_ssh_username: str = ""
    bakamai_ssh_password: str = ""
    bakamai_mcserver_whitelist_path: str = ""
    bakamai_rcon_host: str = ""
    bakamai_rcon_port: int = 0
    bakamai_rcon_password: str = ""


cfg = get_plugin_config(Config)

# API 配置
MCPROFILE_API_BASE = "https://mcprofile.io/api/v1"
# 本地数据文件路径
DATA_FILE_PATH = get_plugin_data_file("whitelist_data.json")


# 允许响应的群组列表
ALLOWED_GROUPS = cfg.bakamai_allowed_groups

# 服务器 SSH 配置
SSH_HOST = cfg.bakamai_ssh_host
SSH_PORT = cfg.bakamai_ssh_port
SSH_USERNAME = cfg.bakamai_ssh_username
SSH_PASSWORD = cfg.bakamai_ssh_password

# Minecraft 服务器配置
WHITELIST_JSON_PATH = cfg.bakamai_mcserver_whitelist_path

# RCON 配置
RCON_HOST = cfg.bakamai_rcon_host
RCON_PORT = cfg.bakamai_rcon_port
RCON_PASSWORD = cfg.bakamai_rcon_password

# ==================== 工具函数 ====================


def load_data() -> dict:
    """加载本地绑定数据"""
    if not DATA_FILE_PATH.exists():
        return {}
    try:
        with open(DATA_FILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"❌ 加载数据文件失败:  {e}")
        return {}


def save_data(data: dict) -> bool:
    """保存本地绑定数据"""
    try:
        # 确保父目录存在
        DATA_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

        with open(DATA_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger. error(f"❌ 保存数据文件失败: {e}")
        return False


def find_user_by_username(username: str) -> Optional[str]:
    """
    根据游戏用户名查找对应的 QQ 号

    :param username: 游戏用户名
    :return: QQ 号字符串，未找到返回 None
    """
    data = load_data()
    username_lower = username.lower()

    for user_id, bindings in data.items():
        for binding in bindings:
            if binding["username"].lower() == username_lower:
                return user_id

    return None


async def get_group_member_card(bot: Bot, group_id: int, user_id: int) -> Optional[str]:
    """
    获取群成员的群昵称

    Args:
        bot: Bot 实例
        group_id: 群号
        user_id: 用户 QQ 号

    Returns:
        群昵称，获取失败返回 None
    """
    try:
        member_info = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
        # 优先使用群名片，其次是昵称
        card = member_info.get("card") or member_info.get("nickname")
        return card
    except Exception as e:
        logger. warning(f"⚠️ 获取群成员 {user_id} 信息失败: {e}")
        return None


async def get_uuid_from_api(username: str, platform: Literal["java", "bedrock"]) -> Optional[str]:
    """
    从 mcprofile.io API 获取玩家 UUID

    :param username: 游戏用户名
    :param platform: "java" 或 "bedrock"
    :return: UUID 字符串，失败返回 None
    """
    try:
        if platform == "java":
            api_url = f"{MCPROFILE_API_BASE}/java/username/{username}"
            uuid_field = "uuid"
        else:   # bedrock
            api_url = f"{MCPROFILE_API_BASE}/bedrock/gamertag/{username}"
            uuid_field = "floodgateuid"

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(api_url)
            response.raise_for_status()
            data = response.json()

            uuid = data.get(uuid_field)
            if not uuid:
                logger.error(f"❌ API 响应中未找到 {uuid_field} 字段")
                return None

            return uuid

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            logger.warning(f"⚠️ 玩家 {username} 在 API 中不存在")
        else:
            logger.error(f"❌ API 请求失败: HTTP {e.response.status_code}")
        return None
    except httpx.HTTPError as e:
        logger. error(f"❌ 网络请求失败: {e}")
        return None
    except (KeyError, ValueError) as e:
        logger.error(f"❌ API 响应解析失败: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ 未知错误: {e}")
        return None


def get_ssh_client() -> paramiko.SSHClient:
    """
    创建并连接 SSH 客户端

    Returns:
        已连接的 SSH 客户端
    """
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # 密码认证 (Password-based authentication)
    ssh_client.connect(
        hostname=SSH_HOST,
        port=SSH_PORT,
        username=SSH_USERNAME,
        password=SSH_PASSWORD
    )

    return ssh_client


def get_uuid_from_remote_whitelist(username: str) -> Optional[str]:
    """
    从服务器白名单中查找指定用户名的 UUID

    :param username: 游戏用户名
    :return: UUID 字符串，未找到返回 None
    """

    # 通过 SSH 读取服务器上的 whitelist.json
    ssh_client = None
    try:
        ssh_client = get_ssh_client()
        sftp = ssh_client.open_sftp()

        with sftp.file(WHITELIST_JSON_PATH, "r") as remote_file:
            content = remote_file.read().decode("utf-8")
            whitelist = json.loads(content)

        sftp.close()
        logger.info(f"✅ 成功获取服务器白名单，共 {len(whitelist)} 条记录")

    except Exception as e:
        logger.error(f"❌ 获取服务器白名单失败: {e}")
        return None
    finally:
        if ssh_client:
            ssh_client.close()

    # 查找指定用户名的 UUID
    for entry in whitelist:
        if entry.get("name", "") == username:
            uuid = entry.get("uuid")
            logger.info(f"✅ 从服务器白名单中找到 {username} 的 UUID: {uuid}")
            return uuid

    logger.warning(f"⚠️ 服务器白名单中未找到 {username}")
    return None


async def whitelist_add_by_rcon(username: str) -> Tuple[bool, Optional[str]]:
    """
    Java 版玩家 API 查询失败时，尝试通过 RCON 直接添加白名单
    然后从服务器白名单文件中反向获取 UUID

    :param username: 游戏用户名
    :return: UUID 字符串，未找到返回 None
    """
    try:
        with MCRcon(RCON_HOST, RCON_PASSWORD, port=RCON_PORT) as mcr:
            response = mcr.command(f"whitelist add {username}")
            logger.debug(f"🔧 RCON 添加白名单响应: {response}")

            # 检查响应中是否包含 "added" 字样
            if "added" in response.lower():
                # 从服务器白名单文件中反向获取 UUID
                uuid = get_uuid_from_remote_whitelist(username)
                if uuid:
                    logger.info(f"✅ RCON 添加白名单成功:  {username}")
                    return True, uuid
                else:
                    logger.error(f"❌ RCON 添加成功但无法从服务器获取 UUID")
                    return False, None
            else:
                logger.error(f"❌ RCON 添加白名单失败: {response}")
                return False, None

    except Exception as e:
        logger.error(f"❌ RCON 连接或执行失败: {e}")
        return False, None


def execute_rcon_command(command:  str) -> Tuple[bool, str]:
    """
    执行 RCON 命令

    Args:
        command: RCON 命令

    Returns:
        (是否成功, 响应内容)
    """
    try:
        with MCRcon(RCON_HOST, RCON_PASSWORD, port=RCON_PORT) as mcr:
            response = mcr.command(command)
            logger.info(f"✅ RCON 命令执行成功: {command}")
            return True, response
    except Exception as e:
        logger.error(f"❌ RCON 命令执行失败: {e}")
        return False, str(e)


def update_remote_whitelist(data: dict) -> bool:
    """
    通过 SSH 更新服务器上的 whitelist.json

    :param data: 本地绑定数据字典
    :return: 是否成功
    """
    # 构造 whitelist.json 内容
    whitelist_entries = []
    for user_id, bindings in data.items():
        for binding in bindings:
            whitelist_entries.append({
                "uuid": binding["uuid"],
                "name": binding["username"]
            })

    whitelist_json = json.dumps(whitelist_entries, ensure_ascii=False, indent=2)

    ssh_client = None
    try:
        # 连接 SSH
        ssh_client = get_ssh_client()

        # 通过 SFTP 写入文件
        sftp = ssh_client.open_sftp()
        with sftp.file(WHITELIST_JSON_PATH, "w") as remote_file:
            remote_file.write(whitelist_json)
        sftp.close()

        logger.info("✅ whitelist.json 更新成功")
        return True

    except Exception as e:
        logger.error(f"❌ SSH 连接或文件写入失败: {e}")
        return False
    finally:
        if ssh_client:
            ssh_client.close()


def reload_whitelist_via_rcon() -> bool:
    """通过 RCON 执行 whitelist reload 命令"""
    try:
        with MCRcon(RCON_HOST, RCON_PASSWORD, port=RCON_PORT) as mcr:
            response = mcr.command("whitelist reload")
            logger.info(f"✅ RCON 执行成功: {response}")
            return True
    except Exception as e:
        logger.error(f"❌ RCON 执行失败: {e}")
        return False


async def check_superuser(bot: Bot, event: MessageEvent) -> bool:
    """
    检查用户是否为超级用户

    Args:
        bot: Bot 实例
        event: 消息事件

    Returns:
        是否为超级用户
    """
    return await SUPERUSER(bot, event)


async def process_whitelist_add(
        username: str,
        platform: Literal["java", "bedrock"],
        target_user_id: int,
        admin_user_id: Optional[int] = None
) -> str:
    """
    处理白名单添加的核心逻辑

    :param username: 游戏用户名
    :param platform: 平台类型
    :param target_user_id: 目标用户 ID
    :param admin_user_id: 管理员用户 ID（如果是管理员操作）
    :return: 结果消息字符串
    """

    platform_name = "Java 版" if platform == "java" else "基岩版"  # Platform display name

    logger.info(f"📝 处理白名单添加请求: 用户 {target_user_id}, 平台 {platform_name}, 用户名 {username}"
                f"{f", 请求来自 {admin_user_id}" if admin_user_id else ""}")

    # 读取本地数据
    data = load_data()
    user_bindings = data.get(str(target_user_id), [])

    # 检查绑定限制
    if not admin_user_id:
        for binding in user_bindings:
            if binding["platform"] == platform:
                return (f"小梨提醒你：已经绑定过{platform_name}的账号啦！你现在绑定的是{binding['username']}。"
                        "如果需要更换账号，请联系腐竹手动修改喵！")

    uuid = None
    # Bedrock: 从 API 获取 UUID
    if platform == "bedrock":
        logger.info(f"🔍 正在查询 {platform_name} 玩家信息...")
        uuid = await get_uuid_from_api(username, platform)
    # Java: RCON 直接添加
    elif platform == "java":
        logger.info(f"🔧 使用 RCON 添加 {username}")

        success, fallback_uuid = await whitelist_add_by_rcon(username)
        if success and fallback_uuid:
            uuid = fallback_uuid
            logger.info(f"✅ 使用 RCON fallback 成功添加并获取 UUID: {username} -> {uuid}")

    if not uuid:
        return "小梨没有找到玩家UUID！请联系腐竹查看！"

    # 添加绑定记录
    new_binding = {
        "platform": platform,
        "uuid": uuid,
        "username":  username
    }

    if target_user_id not in data:
        data[target_user_id] = []
    data[target_user_id].append(new_binding)

    # 保存本地数据
    if not save_data(data):
        return "小梨保存绑定数据失败！请联系腐竹查看！"
    logger.info(f"💾 用户 {target_user_id} 绑定数据已保存")

    # 更新服务器白名单文件
    logger.info("📤 正在更新服务器白名单...")
    if not update_remote_whitelist(data):
        return "小梨白名单更新失败了qwq……"

    # RCON 刷新白名单
    logger.info("🔄 正在刷新白名单...")
    if not reload_whitelist_via_rcon():
        return "小梨白名单更新失败了qwq……"

    logger.info(f"✅ 用户 {target_user_id} 白名单添加完成")
    return f"{"." if platform == "bedrock" else ""}{username}白名单添加成功啦！"


async def process_whitelist_remove(
        username: str,
        platform: Literal["java", "bedrock"],
        admin_user_id: int
):
    """
    处理白名单删除的核心逻辑
    """
    platform_name = "Java 版" if platform == "java" else "基岩版"  # Platform display name

    logger.info(f"📝 处理白名单删除请求: 平台 {platform_name}, 用户名 {username}, 请求来自 {admin_user_id}")

    # 读取本地数据
    data = load_data()
    # 查找要删除的绑定
    removed_binding = None
    for k, v in data.items():
        for binding in v:
            if binding["platform"] == platform and binding["username"] == username:
                # 找到目标 username
                removed_binding = binding
                v.remove(binding)

                # 保存本地数据
                if not save_data(data):
                    return "小梨保存绑定数据失败！请联系腐竹查看！"
                logger.info(f"💾 用户 {k} 绑定数据已保存 (删除 {username})")
                break

    # 更新服务器白名单文件
    logger.info("📤 正在更新服务器白名单...")
    if not update_remote_whitelist(data):
        return "小梨白名单更新失败了qwq……"

    # RCON 刷新白名单
    logger.info("🔄 正在刷新白名单...")
    if not reload_whitelist_via_rcon():
        return "小梨白名单更新失败了qwq……"

    if not removed_binding:
        return "小梨没有找到该名字的绑定记录。事已至此，同步一下（"
    else:
        return f"已经成功删除{"." if platform == "bedrock" else ""}{username}的白名单。"


# ==================== 事件处理 ====================


mc_count = on_regex("^mc几", priority=15, block=False)


@mc_count.handle()
async def handle_mc_count(bot, event, matcher):
    """处理查询在线玩家数量请求"""

    # 群组过滤：仅允许的群组才响应
    if (group_id := getattr(event, "group_id", None)) not in ALLOWED_GROUPS:
        return
    logger.info(f"📝 用户 {event.user_id} 查询在线玩家数量")

    # 执行 RCON list 命令
    success, response = execute_rcon_command("list")
    if not success:
        logger.warning(f"Bakamai Server RCON 无响应: {response}")
        await matcher.finish(f"服务器游玩人数：\nBakamai 服务器: ?人 (服务器宕机)")
        return

    # 提取在线玩家数量
    try:
        count_part = response.split(":")[0]  # 格式如 " There are 0 of a max of 8 players online:"
        online_count = int(count_part.split(" ")[2])
        _max_count = int(count_part.split(" ")[7])
    except (IndexError, ValueError) as e:
        logger.error(f"❌ 解析 RCON 响应失败: {e}")
        await matcher.finish(f"服务器游玩人数：\nBakamai 服务器: 0人 (更新于 现在)")
        return

    await matcher.finish(f"服务器游玩人数：\nBakamai 服务器: {online_count}人 (更新于 现在)")



# 用户查询在线玩家列表
list_players_matcher = on_regex("^list$", priority=10, block=True)


@list_players_matcher. handle()
async def handle_list_players(bot, event, matcher):
    """处理查询在线玩家列表请求"""

    # 群组过滤：仅允许的群组才响应
    if (group_id := getattr(event, "group_id", None)) not in ALLOWED_GROUPS:
        return
    logger.info(f"📝 用户 {event.user_id} 查询在线玩家列表")

    # 执行 RCON list 命令
    success, response = execute_rcon_command("list")
    if not success:
        logger.warning(f"Bakamai Server RCON 无响应: {response}")
        await matcher.finish(f"[Bakamai] 服务器好像没有反应哦，小梨建议你问问腐竹（")
        return

    # 提取玩家名列表
    player_names_str = response.split(":")[1].strip()  # 如果存在，则为以逗号`,`分隔的玩家名字符串
    if not player_names_str:
        await list_players_matcher.finish("[Bakamai] 小梨看啦，服务器现在没人哦~")
        return
    player_names = [player.strip() for player in player_names_str.split(",")]

    # 构建玩家信息列表
    result_lines = [f"[Bakamai] 服务器现在有{len(player_names)}个人在肝：\n"]
    for player_name in player_names:
        # 查找玩家对应的 QQ 号
        user_id = find_user_by_username(player_name)

        if user_id:
            # 获取群昵称
            group_member_card = await get_group_member_card(bot, group_id, int(user_id))

            if group_member_card:
                result_lines.append(f"• {player_name} ({group_member_card})")
            else:
                result_lines.append(f"• {player_name} (QQ: {user_id})")
        else:
            # 未绑定的玩家
            result_lines. append(f"• {player_name} (未绑定)")

    result = "\n".join(result_lines)
    await list_players_matcher.finish(result)


# 超级用户白名单管理（优先级较高，支持添加和删除）
admin_whitelist_matcher = on_regex(r'^(添加|删除)白名单\s+(\.?)([0-9a-zA-Z\-_]+)\s+(\d+)$',
                                   priority=10, block=True, permission=SUPERUSER)


@admin_whitelist_matcher.handle()
async def handle_admin_whitelist_request(event, matcher):
    """处理超级用户白名单管理请求"""

    # 群组过滤：仅允许的群组才响应
    if getattr(event, "group_id", None) not in ALLOWED_GROUPS:
        return

    matched = matcher.state["_matched"]
    action, dot, username, target_user_id = matched.groups()

    # 判断平台：有点号为 Bedrock 版，无点号为 Java 版
    platform:  Literal["java", "bedrock"] = "bedrock" if dot else "java"

    if action == "添加":
        # 调用统一的添加逻辑
        result = await process_whitelist_add(username, platform, target_user_id, event.user_id)
    elif action == "删除":
        # 调用删除逻辑
        result = await process_whitelist_remove(username, platform, event.user_id)
    else:
        return  # 不应发生，用于 IDE 警告消除
    await admin_whitelist_matcher.finish("[Bakamai] " + result)


# 普通用户白名单添加（优先级较低）
user_whitelist_matcher = on_regex(r'^(添加)白名单\s+(\.?)([0-9a-zA-Z\-_]+)$', priority=5, block=True)


@user_whitelist_matcher.handle()
async def handle_user_whitelist_request(event, matcher):
    """处理普通用户白名单添加请求"""

    # 群组过滤：仅允许的群组才响应
    if getattr(event, "group_id", None) not in ALLOWED_GROUPS:
        return

    matched = matcher.state["_matched"]
    action, dot, username = matched.groups()

    # 判断平台：有点号为 Bedrock 版，无点号为 Java 版
    platform:  Literal["java", "bedrock"] = "bedrock" if dot else "java"

    result = await process_whitelist_add(username, platform, event.user_id)
    await admin_whitelist_matcher.finish("[Bakamai] " + result)


# 管理员查看白名单
view_whitelist_matcher = on_regex("^查看白名单$", priority=5, block=True, permission=SUPERUSER)


@view_whitelist_matcher.handle()
async def handle_view_whitelist(event):
    """处理管理员查看白名单请求"""

    # 群组过滤：仅允许的群组才响应
    if getattr(event, "group_id", None) not in ALLOWED_GROUPS:
        return
    logger.info(f"超级用户 {event.user_id} 查看白名单")

    # 读取本地数据
    data = load_data()
    if not data:
        await view_whitelist_matcher.finish("白名单为空，暂无绑定记录")
        return

    # 构建白名单信息
    result_lines = ["白名单绑定记录：\n"]

    total_bindings = 0
    for user_id, bindings in data. items():
        result_lines.append(f"QQ {user_id}:")
        for binding in bindings:
            platform_name = "Java 版" if binding["platform"] == "java" else "基岩版"
            result_lines.append(f"  - {platform_name}:  {binding['username']}")
            total_bindings += 1
        result_lines.append("")

    result_lines.append(f"总计: {len(data)} 个用户，{total_bindings} 条绑定记录")

    result = "\n".join(result_lines)
    await view_whitelist_matcher.finish(result)
