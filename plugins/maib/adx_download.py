import re
import json
import httpx
import zipfile
import tempfile
from pathlib import Path
from typing import Dict, List, Set

from nonebot import require, logger
from nonebot.internal.matcher import Matcher

require("nonebot_plugin_localstore")
from nonebot_plugin_localstore import get_plugin_cache_dir as get_cache_dir

from nonebot.adapters.onebot.v11 import Bot, Event


class NotExistChart(Exception): pass


class BadLogger:
    """在无 nonebot2 日志记录器情况下的占位类"""
    @staticmethod
    def critical(msg: str): print("CRITICAL:", msg)
    @staticmethod
    def success(msg: str): print("SUCCESS:", msg)
    @staticmethod
    def trace(msg: str): print("TRACE:", msg)
    @staticmethod
    def debug(msg: str): print("DEBUG:", msg)
    @staticmethod
    def info(msg: str): print("INFO:", msg)
    @staticmethod
    def warning(msg: str): print("WARNING:", msg)
    @staticmethod
    def error(msg: str): print("ERROR:", msg)


class AdxCacheManager:
    """AstroDX 谱面下载缓存管理器"""

    def __init__(self, cache_dir: Path, nb_logger=None):
        self.logger = nb_logger if nb_logger else BadLogger()  # 日志捕获
        self.cache_dir = cache_dir
        self.adx_cache_index_path = cache_dir / "cache_index.json"
        self.short_id_index_path = cache_dir / "short_id_index.json"

        def _get_adx_cache_index_path():
            try:
                with self.adx_cache_index_path.open("r", encoding="utf-8") as file:
                    result: List[int] = json.load(file)
            except json.JSONDecodeError:
                result: List[int] = []
            except OSError:
                with self.adx_cache_index_path.open("w", encoding="utf-8") as f:
                    json.dump([], f, ensure_ascii=False, indent=2)
                _get_adx_cache_index_path()
            except Exception as ex:
                logger.error(f"读取缓存索引文件发生了未经预料的错误: {ex}")
                result: List[int] = []
            return result

        # short_id -> Path (bga オーバーライド nobga)
        self.bga_map: Dict[int, Path] = {}  # bga 映射
        self.nobga_map: Dict[int, Path] = {}  # nobga 映射
        self.recent_calls: List[int] = []  # 最近调用顺序
        self.exist_short_ids: Set[int] = set()  # 已存在的 short_id 列表
        self.get_json_cache()
        self._scan_cache_files(_get_adx_cache_index_path())

    def get_json_cache(self):
        """通过谱面源 index.json 获取已知谱面 ID 列表。"""
        url = "https://raw.githubusercontent.com/Neskol/Maichart-Converts/refs/heads/master/index.json"
        self.logger.info("正在获取谱面源 short_id_index.json")
        try:
            response = httpx.get(url, timeout=10.0)
            response.raise_for_status()
            data: dict = response.json()  # 尝试下载最新版
            if data:
                # 更新缓存文件
                with self.short_id_index_path.open("w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                self.logger.info("已更新 short_id_index.json 缓存文件")
        except httpx.HTTPError as ex:
            self.logger.warning("未获取到 short_id_index.json 谱面源，尝试使用缓存文件")
            if self.short_id_index_path.exists():
                with self.short_id_index_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)  # 尝试使用缓存文件
                self.logger.info("已使用缓存文件作为谱面源")
            else:
                self.logger.error(f"获取谱面源失败，且无缓存文件可用。无法检验谱面有效性。错误信息: {ex}")
                return
        self.exist_short_ids = set(int(short_id) for short_id in data.keys())
        self.logger.info(f"已获取 {len(self.exist_short_ids)} 个已知谱面 ID")

    def _scan_cache_files(self, recent_index: List[int]):
        """初始化: 扫描缓存目录，建立 short_id 到文件路径的映射。"""
        t: set[int] = set()
        files = list(self.cache_dir.glob("adx_*.zip"))
        for file in files:
            match = re.match(r"adx_(\d+)(_nobga)?\.zip", file.name)
            if not match: continue

            short_id: int = int(match.group(1))
            bga: bool = False if match.group(2) else True
            t.add(short_id)
            if bga:
                self.bga_map[short_id] = file
            else:
                self.nobga_map[short_id] = file

        # 更新 recent_index
        self.recent_calls: List[int] = [sid for sid in recent_index if sid in t]
        for sid in t:
            if sid not in self.recent_calls:
                self.recent_calls.append(sid)

    def _convert_bga_to_nobga(self, short_id: int) -> Path:
        """将 bga 文件转换为 nobga 文件，返回新文件路径。"""
        bga_path: Path = self.bga_map[short_id]
        nobga_path: Path = self.cache_dir / f"adx_{short_id}_nobga.zip"

        try:
            # 使用临时目录进行解压和处理
            with tempfile.TemporaryDirectory(dir=self.cache_dir) as temp_dir:
                temp_dir_path = Path(temp_dir)
                # 解压 bga zip 包
                with zipfile.ZipFile(bga_path, "r") as zip_ref:
                    zip_ref.extractall(temp_dir_path)
                # 删除 pv.mp4 文件（如果存在）
                pv_file = temp_dir_path / "pv.mp4"
                if pv_file.exists():
                    pv_file.unlink()
                    self.logger.info(f"已删除 {str(pv_file)}")
                else:
                    self.logger.info("未找到 pv.mp4，这可能是一个无PV的谱面。")
                    return bga_path  # 直接返回原文件路径
                # 重新压缩为 nobga zip 包
                with zipfile.ZipFile(nobga_path, "w", zipfile.ZIP_DEFLATED) as zip_write:
                    for file in temp_dir_path.rglob("*"):
                        if file.is_file():
                            arcname = file.relative_to(temp_dir_path)
                            zip_write.write(file, arcname)
                self.logger.info(f"已生成: {str(nobga_path)}")
        except (zipfile.BadZipFile, OSError) as ex:
            self.logger.error(f"转换 bga 到 nobga 文件转换失败: {ex}")
            raise ex  # 重新抛出异常
        except Exception as ex:
            self.logger.error(f"转换 bga 到 nobga 失败的未知异常: {ex}")
            raise ex
        return nobga_path

    def _cache_update_and_clean(self, short_id: int):

        CACHE_MAX = 39  # 预计可配置的最大缓存数量
        # 更新最近调用顺序
        if short_id in self.recent_calls:
            self.recent_calls.remove(short_id)
        self.recent_calls.append(short_id)
        # 清理多余缓存
        if len(self.recent_calls) > CACHE_MAX:
            # 先删除1/3的旧缓存
            remove_count = len(self.recent_calls) - CACHE_MAX // 3
            to_remove = self.recent_calls[:remove_count]
            for sid in to_remove:
                # 删除文件
                for path_map in (self.bga_map, self.nobga_map):
                    if sid in path_map:
                        try:
                            path_map[sid].unlink()
                            self.logger.info(f"已删除缓存文件: {str(path_map[sid])}")
                        except FileNotFoundError:
                            if path_map is self.bga_map:
                                self.logger.info(f"未删除不存在的缓存文件: {str(path_map[sid])}")
                            self.logger.warning(f"删除不存在的缓存文件失败: {str(path_map[sid])}")
                        del path_map[sid]
                self.recent_calls.remove(sid)
                self.logger.info(f"已从缓存记录中移除 id{sid}")

            # 检查剩余的旧的1/2是否有 nobga 版本可删除
            to_remove_nobga = self.recent_calls[:len(self.recent_calls)//2]
            for sid in to_remove_nobga:
                # 由于无 pv 的谱面 nobga 映射可能与 bga 映射相同，需检查后删除
                if sid in self.nobga_map and (self.nobga_map[sid] == self.bga_map.get(sid, None)):
                    # 删除文件
                    try:
                        self.nobga_map[sid].unlink()
                        self.logger.info(f"已删除缓存文件: {str(self.nobga_map[sid])}")
                    except FileNotFoundError:
                        self.logger.warning(f"删除不存在的缓存文件失败: {str(self.nobga_map[sid])}")
                    # 从 nobga 映射中移除
                    del self.nobga_map[sid]

    async def _download(self, short_id: int, bga: bool = False) -> Dict[str, str | Path | Exception]:
        """下载所需文件，保存到缓存目录，返回文件路径。"""
        suffix = "" if bga else "_nobga"
        file_path = self.cache_dir / f"adx_{short_id}{suffix}.zip"
        url = "https://api.milkbot.cn/server/api/{}download?id={}".format( "" if bga else "nobga_", short_id )

        try:
            self.logger.info(f"正在下载文件 {url} -> {str(file_path)}")
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
                file_path.write_bytes(response.content)
                return {"status": "success", "file_path": file_path}
        except httpx.HTTPError as ex:
            self.logger.error(f"网络请求失败: {ex}")
            return {"status": "failed", "error": ex}
        except OSError as ex:
            self.logger.error(f"文件写入失败: {ex}")
            return {"status": "failed", "error": ex}
        except Exception as ex:
            self.logger.error(f"未知异常: {ex}")
            return {"status": "failed", "error": ex}

    async def get_file(self, short_id: int, bga: bool) -> Dict[str, str | Path | Exception]:
        """
        主要方法：通过直接调用缓存或现场下载等方式获取目标谱面文件路径。

        返回值格式:
        {
            "status": "success" | "failed",
            "file_path": Path,  # 仅当 status 为 "success" 时存在
            "error": Exception,  # 仅当 status 为 "failed" 时存在
            "function": "cache_hit" | "bga_to_nobga" | "download"  # 调用来源
        }
        """
        if self.exist_short_ids and short_id not in self.exist_short_ids:
            # 可能的有效性检查，检查到不存在的谱面，直接返回 NotExistChart 错误
            self.logger.info(f"id{short_id} 不在已知谱面列表中，跳过下载")
            return {"status": "failed", "error": NotExistChart()}
        self._cache_update_and_clean(short_id)  # 维护最近调用顺序

        # 尝试直接获取
        f_map = self.bga_map if bga else self.nobga_map
        file_path = f_map.get(short_id, None)
        # 完全匹配 ( bga->bga, nobga->nobga )
        if file_path and file_path.exists():
            return {'status': "success", "file_path": file_path, "function": "cache_hit"}
        # 完全匹配失败
        if not bga:
            # 尝试从 bga 转换
            bga_path = self.bga_map.get(short_id, None)
            if bga_path and bga_path.exists():
                # ( nobga->bga )
                nobga_path = self._convert_bga_to_nobga(short_id)
                self.nobga_map[short_id] = nobga_path
                return {"status": "success", "file_path": nobga_path, "function": "bga_to_nobga"}
        # 下载并更新
        new_get = await self._download(short_id, bga)
        new_get['function'] = "download"
        if new_get.get("status") == "success":
            f_map[short_id] = new_get['file_path']  # 更新对应映射
        return new_get


adx_cache_manager = AdxCacheManager(get_cache_dir(), logger)
acm = adx_cache_manager  # 方便调用的别名


async def handle_download(bot: Bot, event: Event, matcher: Matcher, short_id: int):
    """捕获消息，下载谱面文件并上传至群文件"""

    group_id = event.group_id if hasattr(event, "group_id") else None
    logger.debug(f"group_id: {group_id}")
    if not group_id:
        logger.debug("未检测到group_id，非群聊环境")
        await matcher.finish("现在小梨只能把谱面传到群文件喔qwq")
        return

    await matcher.send(f"想玩id{short_id}是吧，小梨正在翻箱倒柜.gif")

    logger.info(f"开始请求下载文件 {short_id}.zip")
    result = await acm.get_file(short_id, False)
    if result['status'] != "success":
        # 错误处理
        error: Exception = result['error']
        if isinstance(error, httpx.HTTPError):
            await matcher.finish(f"果咩纳塞——小梨没下载到id{short_id}的谱面！如果需要的话，再试一次吧（")
            return
        elif isinstance(error, NotExistChart):
            await matcher.finish(f"不许耍小梨！没有id是{short_id}的谱面！！！")
            return
    logger.info(f"成功通过 {result['function']} 获取谱面文件。")
    chart_file_path = result['file_path']

    # 解压并读取maidata.txt第一行
    logger.info("开始解压zip文件")
    maidata_title = None
    with tempfile.TemporaryDirectory(dir=get_cache_dir()) as tmp_dir:
        with zipfile.ZipFile(chart_file_path, "r") as zip_ref:
            zip_ref.extractall(tmp_dir)
        maidata_path = Path(tmp_dir) / "maidata.txt"
        if maidata_path.exists():
            logger.info("找到 maidata.txt，开始读取标题")
            with maidata_path.open("r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    title_match = re.search(r"&title=(.*)", line)
                    if title_match:
                        maidata_title = title_match.group(1).strip()
                        logger.info(f"成功读取谱面标题: {maidata_title}")
                        break
        else:
            logger.error("谱面中未找到 maidata.txt ?!")
    if not maidata_title:
        logger.error(f"读取谱面标题失败，maidata.txt 内容异常。对应谱面：id{short_id} -> {str(chart_file_path)}")
        await matcher.finish("小梨下载到的谱面好像有问题……请求助小梨在这边的监护人QAQ")
        return

    # 上传到QQ群文件
    logger.info(f"{short_id}.zip 开始上传群文件")
    await bot.call_api(
        "upload_group_file",
        group_id=group_id,
        file=chart_file_path.as_posix(),
        name=f"{short_id}.zip"
    )
    logger.success(f"{short_id}.zip 上传成功")
    finish_message = f"{maidata_title}(id{short_id})" if maidata_title else f"id{short_id}"
    await matcher.finish(f"小梨已经帮你把 {finish_message} 的谱面传到群里啦！")
