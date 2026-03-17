import io
import re
import yaml
from pathlib import Path
from pydantic import BaseModel
from typing import Dict, Optional, List

from . import services, image_gen, network
from .utils import rate_alias_map, MaiData, MaiChart, MaiChartAch, parse_status, DIFFS_MAP, MaiDataCNCache

HAS_DRIVER = False

try:
    from nonebot import get_driver
    driver = get_driver()
    HAS_DRIVER = True
except ValueError:
    DEVELOPER_TOKEN = None
else:
    from nonebot import require, logger, on_regex, get_plugin_config
    from nonebot.plugin import PluginMetadata
    from nonebot.params import RegexGroup
    from nonebot.internal.matcher import Matcher
    from nonebot.adapters.onebot.v11 import Bot, Event, Message, MessageSegment

    require("nonebot_plugin_localstore")
    require("nonebot_plugin_datastore")
    from nonebot_plugin_localstore import get_plugin_cache_dir

    class Config(BaseModel):
        DIVING_FISH_DEVELOPER_TOKEN: Optional[str] = None

    __plugin_meta__ = PluginMetadata(
        name="lyra-maib",
        description="一个QQ群的 舞萌DX 功能机器人。",
        usage="使用 help 查询使用方法",
        config=Config,
    )
    DEVELOPER_TOKEN = get_plugin_config(Config).DIVING_FISH_DEVELOPER_TOKEN

version_data = yaml.safe_load((Path.cwd() / "assets" / "versions.yaml").read_text(encoding="utf-8"))

if HAS_DRIVER:

    # =================================
    # ADX 谱面下载
    # =================================

    adx_download = on_regex(r"^下载[铺谱]面\s*(\d*)\s*(.*)$", priority=10, block=True)


    @adx_download.handle()
    async def _(bot: Bot, event: Event, matcher: Matcher, groups: tuple = RegexGroup()):
        """处理命令: 下载谱面11568"""

        raw_short_id, archive_type = groups
        archive_type = archive_type.strip().lower()
        short_id = int(raw_short_id) if raw_short_id.isdigit() else -1

        if short_id <= 0:
            # 只有在没有显式输入 ID 的情况下才尝试从回复提取
            if reply := getattr(event, "reply", None):
                replied_text = str(reply.message)
                match = re.search(r"(\d+)", replied_text)
                if match:
                    short_id = int(match.group(1))
                    logger.debug(f"从回复消息中提取到 short_id: {short_id}")

            # 仍然未找到 ID，视为误触
            # **大家当做无事发生**
            if short_id <= 0:
                return

        # 获取谱面信息
        mdt = await services.get_song_by_id(short_id)  # 不转换为 utils.MaiData，直接使用数据库对象中才包含的 zip_path
        chart_file_path = Path(mdt.zip_path) if mdt and mdt.zip_path else None

        if not chart_file_path or not chart_file_path.exists():
            logger.warning(f"谱面 id {short_id} 不存在")
            await matcher.finish("小梨没有找到这个谱面！可能还没被收录，请联系监护人确认喔qwq")
            return

        await matcher.send(f"请稍候——小梨开始准备 id {short_id} 的谱面文件啦！")

        # 4. 上传逻辑
        file_ext = "zip" if "zip" in archive_type else "adx"
        file_name = f"{short_id}.{file_ext}"
        song_name = getattr(mdt, 'title', f"id {short_id}")

        group_id = getattr(event, "group_id", None)
        if group_id:
            try:
                await bot.call_api(
                    "upload_group_file",
                    group_id=group_id,
                    file=chart_file_path.resolve().as_posix(),
                    name=file_name
                )
            except Exception as e:
                logger.error(f"上传失败: {e}")
                await matcher.finish("小梨上传谱面时遇到了问题，请联系监护人确认喔qwq")
                return
            await matcher.finish(f"小梨已经帮你把 {song_name} 的谱面传到群里啦！")
        else:
            user_id = event.get_user_id()
            try:
                await bot.call_api(
                    "upload_private_file",
                    user_id=user_id,
                    file=chart_file_path.resolve().as_posix(),
                    name=file_name
                )
            except Exception as e:
                logger.error(f"上传失败: {e}")
                await matcher.finish("小梨上传谱面时遇到了问题，请联系监护人确认喔qwq")
                return
            await matcher.finish(f"登登~请查收 {song_name} 谱面！")


    # =================================
    # 查歌
    # =================================

    async def get_song_image(mdt: services.MaiData, user_id: str | int) -> bytes:
        """提取的共用查歌并生成图片的逻辑"""
        user_id = str(user_id)
        maidata: MaiData = mdt.to_data()
        song_in_cn = await MaiDataCNCache.contains_id(maidata.shortid, get_plugin_cache_dir())
        if song_in_cn:
            # 通过 QQ 获取用户绑定的信息
            record_list = await network.sy_dev_player_record(maidata.shortid, qq=user_id, developer_token=DEVELOPER_TOKEN)
            if record_list:
                maidata.parse_sy_player_record(record_list)  # 若水鱼有数据则进行填入
        # 构建回复图片
        output = io.BytesIO()
        img = image_gen.DrawInfo(maidata, version_data, cn_level=1 if maidata.version_cn else 0).get_image()
        img.save(output, format="jpeg")
        return output.getvalue()


    mai_info = on_regex(r"^(id|info)(\d+)", priority=10, block=True)  # `id11451`,`info11451`


    @mai_info.handle()
    async def _(event: Event, matcher: Matcher, groups: tuple = RegexGroup()):
        """处理命令: id11451 / info11451"""
        _, shortid = groups
        user_id = event.get_user_id()  # 意图通过QQ查询乐曲数据
        try:
            short_id = int(shortid)
        except (ValueError, TypeError):
            return
        # 查询数据库获取曲目数据
        mdt: Optional[services.MaiData] = await services.get_song_by_id(short_id)
        if not mdt:
            await matcher.finish(f"没有找到 id{short_id} 的乐曲数据qwq")
            return
        img_bytes = await get_song_image(mdt, user_id)
        await matcher.finish(Message(f"{mdt.shortid}. {mdt.title}") + MessageSegment.image(img_bytes))


    mai_what_song = on_regex(r"^(\S+?)是什么歌([?？]?)$", priority=10, block=True)


    @mai_what_song.handle()
    async def _(event: Event, matcher: Matcher, groups: tuple = RegexGroup()):
        """处理命令: xxx是什么歌"""
        keyword, all_tag = groups
        user_id = event.get_user_id()  # 意图通过QQ查询乐曲数据
        mdt_list: List[services.MaiData] = list((
            await services.get_song_by_name_smart(keyword) if not all_tag else
            await services.get_song_by_name_blur(keyword)
        ))  # 不带问号为智能搜索，带问号进行强制搜索
        mdt_list = [mdt for mdt in mdt_list if mdt.shortid < 100000]  # 忽略宴会场
        if not mdt_list:
            await matcher.finish(f"没有找到包含「{keyword}」的乐曲数据qwq")
            return
        if len(mdt_list) == 1:
            mdt = mdt_list[0]
            msg = Message(f"找到了乐曲 {mdt.shortid}. {mdt.title}")
        elif len(mdt_list) > 4:
            await matcher.send(f"找到了 {len(mdt_list)} 首相应的乐曲！请查看以下是否有你的目标！")
            # 未来 b50 提上日程后，希望可以以 b50_box 承载曲目信息
            img = image_gen.simple_list([mdt.to_data() for mdt in mdt_list])
            output = io.BytesIO()
            img.save(output, format="jpeg")
            img_bytes = output.getvalue()
            await matcher.finish(MessageSegment.image(img_bytes))
            return
        else:
            msg = Message(f"找到了 {len(mdt_list)} 首相应的乐曲！请查看以下乐曲！")
        
        imgs = []
        for mdt in mdt_list:
            img_bytes = await get_song_image(mdt, user_id)
            imgs.append(MessageSegment.image(img_bytes))
        await matcher.finish(msg + Message().join(imgs))


    alias_setting = on_regex(r'^(添加|删除)别名\s+(?:id)?(\d+)\s+([^\s]+)$', priority=5, block=True)

    @alias_setting.handle()
    async def _(event: Event, matcher: Matcher, groups: tuple = RegexGroup()):
        """处理命令: 添加别名 id11451 xxx / 删除别名 id11451 xxx"""
        action, shortid, alias = groups
        try:
            short_id = int(shortid)
            mdt: Optional[services.MaiData] = await services.get_song_by_id(short_id)
            if not mdt:
                raise ValueError
        except (ValueError, TypeError):
            await matcher.finish("请提供正确的乐曲 ID 哦qwq")
            return

        group_id = getattr(event, "group_id", None)
        group_id = int(group_id) if group_id else None

        if action == "添加":
            # 添加别名
            new_alias = await services.add_alias(short_id, alias, short_id, group_id)
            if new_alias:
                await matcher.finish(f"成功为 {shortid} 添加别名【{alias}】！")
            else:
                await matcher.finish("这个别名似乎已经存在了捏~")
        else:
            await matcher.finish("还不支持自主删除别名喔，请联系监护人处理~")

    scorelist = on_regex(r'^([\u4E00-\u9FFF]{2,3}|\d+\.\d|\d+\+|\d+)\s*(完成表|进度|列表)$', priority=5, block=True)

    b50 = on_regex(r'b50', priority=1, block=True)


    # =================================
    # Rating 计算
    # =================================

    ra_calc = on_regex(r"^ra\s+(\S+)?\s+(\S+)", priority=5, block=True)


    @ra_calc.handle()
    async def _(matcher: Matcher, groups: tuple = RegexGroup()):
        """处理命令: ra 13.2 100.1000"""
        info, rate = groups
        level: float = 0

        # 先解析 rate
        try:
            achievement = float(rate)
        except (ValueError, TypeError):
            achievement = rate_alias_map.get(rate.lower(), -100)

        # 1. 尝试以定数形式解析
        try:
            level = float(info)
        except (ValueError, TypeError):
            pass

        # 2. 判断定数是否越界，越界则解析为纯数字 id
        if level > 20:
            level = 0  # 大于 20 则一定不为定数，驳回上述解析
            shortid = int(level)
            mai = await services.get_song_by_id(shortid)
            level = mai.charts[-1].lv if mai else 0  # 取最高难度的定数

        # 3. 尝试以 id11451/info11451/id114514紫 形式解析
        if level == 0:
            # 通过正则提取 id
            match = re.search(r'\d+', info)
            diff_info = re.search('[绿黄红紫白]', info)
            if match and any([
                'id' in info.lower(),
                'info' in info.lower(),
                diff_info,
            ]):
                level_str = match.group(0)
                try:
                    shortid = int(level_str)
                    mai = await services.get_song_by_id(shortid)
                except (ValueError, TypeError):
                    mai = None
                if mai:
                    charts = mai.charts
                    s = diff_info.group(1) if diff_info else''
                    diff = parse_status(s, DIFFS_MAP)
                    if diff:
                        # 指定了难度颜色，尝试匹配
                        for c in charts:
                            if c.difficulty == diff:
                                level = c.lv
                                break
                    level = level if level else charts[-1].lv

        # 4. 尝试解析 歌名/别名
        if level == 0:
            pass  # todo: 未实现 歌名/别名解析

        # 解析结束
        if level == 0:
            await matcher.finish("小梨无法解析你提供的定数或歌曲信息喔TT")
            return

        # 调用 MaiChart 计算 DX Rating
        chart = MaiChart(shortid=0, difficulty=0, lv=level)
        chart.set_ach(MaiChartAch(shortid=0, difficulty=0, server="CN", achievement=achievement))
        ra = chart.get_dxrating()

        await matcher.finish("小梨算出来咯！\n"
                            f"定数{level}*{achievement:.4f}% -> Rating: {ra}"
                            "\n该 ra 不考虑 AP 的额外分数哦！" if achievement > 100.5 else "")
