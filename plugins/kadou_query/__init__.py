from nonebot import on_regex
from nonebot.plugin import PluginMetadata

# import plugin_help as p_help
import utils as dt
from radar import radar
from cmd_query import cmd_query_all


__plugin_meta__ = PluginMetadata(
    name="Kadou Query",
    description="一个QQ群的排卡上报/查询功能机器人，支持私有命令和消息读取。",
    usage="使用 .机厅几 查询帮助",
    # config=Config,
)


id_data = dt.IDData()
# 群组权限常量
GROUP_WHITELIST = id_data.get_whitelist()
GROUP_BLOCKLIST = id_data.get_blacklist()
# 外部机器人QQ号常量
# SOURCE_BOT = list()


# on_help = on_regex(r"^[.。]\s*机厅\s*几")
#
# @on_help.handle()
# async def _(event):
#     """处理 .机厅几 帮助命令"""
#     if (event.group_id in GROUP_WHITELIST.keys()) and (event.group_id not in GROUP_BLOCKLIST):
#         await p_help.plugin_help(event)


on_radar = on_regex(r"^[.。 ]\s*([^\s\d]+)\s*(几|([1-9]?\d)|\+\s*([1-9]?\d)|-\s*([1-9]?\d))")

@on_radar.handle()
async def _(event):
    """处理 .xx几 查询/修改命令"""
    if (event.group_id not in GROUP_BLOCKLIST) and (event.group_id in GROUP_WHITELIST.keys()):
        output = await radar(event)  # 使用 radar 进行分配
        await event.finish(output)


on_radar_all = on_regex(r"^[.。/]\s*j")

@on_radar_all.handle()
async def _(event):
    """处理 .j 集体查询指令"""
    if (event.group_id not in GROUP_BLOCKLIST) and (event.group_id in GROUP_WHITELIST.keys()):
        output = await cmd_query_all(event.group_id)
        await event.finish(output)


# on_listen = on_regex(r"")
#
# @on_listen.handle()
# async def _(event):
#     """处理来自其他特定Bot的消息"""
#     # dev 暂不开发
#     if (event.group_id not in GROUP_BLOCKLIST) and (event.group_id in GROUP_WHITELIST.keys()):
#         ...
#     return None


# """
# `.kd <command>`
# <command>:
# - on
#   example: `.kd on`
# - off
#   example: `.kd off`
# """
# on_permission_cmd = on_regex(r"")
#
# @on_permission_cmd.handle()
# async def _(event):
#     """处理群管理员开关排卡功能指令"""
#     # dev 暂不开发
#     if event.group_id in GROUP_BLOCKLIST:
#         ...
#     return None


# """
# `.kd {group_id} <command> <args>`
# <command>:
# - whitelist    arg: {city_code} or None
#   example: `.kd 1234567890 whitelist 黑Z`
# - blacklist    arg: in or out
#   example: `.kd 1234567890 blacklist out`
# """
# on_super_cmd = on_regex(r"")
#
# @on_super_cmd.handle()
# async def _(event):
#     """处理超级管理员黑白名单修改指令"""
#     # dev 暂不开发
#     ...
