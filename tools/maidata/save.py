import sys
from pathlib import Path
from typing import Dict, List

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

# 导入 maib 插件中的 MaiData 相关类
sys.path.insert(0, Path.cwd().as_posix())
from plugins.maib import utils, models


async def init_db(engine):
    """初始化数据库表结构"""
    async with engine.begin() as conn:
        await conn.run_sync(models.Model.metadata.create_all)
    logger.info("数据库表结构同步完成")


async def upsert_maidata(session: AsyncSession, data: utils.MaiData):
    """插入或更新 MaiData 数据"""
    result = await session.execute(
        select(models.MaiData)
        .where(models.MaiData.shortid == data.shortid)
        .options(selectinload(models.MaiData.charts))
    )
    existing = result.scalar_one_or_none()
    img_path_str = str(data.img_path).lower()
    if '.zip' in img_path_str:
        # 找到最后一个 .zip 的索引并截取，确保路径完整
        idx = img_path_str.rfind('.zip')
        # 转换为字符串存储到数据库
        zip_path = str(data.img_path)[:idx + 4]
    else:
        zip_path = None
    if existing:
        # 更新已有数据
        existing.title = data.title
        existing.bpm = data.bpm
        existing.artist = data.artist
        existing.genre = data.genre
        existing.cabinet = data.cabinet
        existing.version = data.version
        existing.version_cn = data.version_cn
        existing.converter = data.converter
        existing.zip_path = zip_path
        existing.is_utage = data.utage
        existing.utage_tag = data.utage_tag
        existing.buddy = data.buddy
    else:
        existing = models.MaiData(
            shortid=data.shortid,
            title=data.title,
            bpm=data.bpm,
            artist=data.artist,
            genre=data.genre,
            cabinet=data.cabinet,
            version=data.version,
            version_cn=data.version_cn,
            converter=data.converter,
            zip_path=zip_path,
            is_utage=data.utage,
            utage_tag=data.utage_tag,
            buddy=data.buddy
        )
        # 创建新数据
        session.add(existing)

    # 处理谱面数据
    existing_charts = {chart.chart_number: chart for chart in existing.charts}
    for chart in data.charts:
        chart_num = chart.difficulty
        if chart_num in existing_charts:
            # 更新已有谱面
            existing_chart = existing_charts[chart_num]
            existing_chart.lv = chart.lv
            existing_chart.des = chart.des
            existing_chart.inote = chart.inote
        else:
            # 添加新谱面
            new_chart = models.MaiChart(
                shortid=data.shortid,
                chart_number=chart.difficulty,
                lv=chart.lv,
                des=chart.des,
                inote=chart.inote
            )
            session.add(new_chart)


async def run_import(sql_alchemy: str, maidata_list: List[utils.MaiData]):
    # SQLite 异步连接字符串
    engine = create_async_engine(sql_alchemy)
    async_session = async_sessionmaker(
        bind=engine,
        expire_on_commit=False
    )

    await init_db(engine)

    async with async_session() as session:
        total = len(maidata_list)
        for idx, mai in enumerate(maidata_list):
            try:
                await upsert_maidata(session, mai)
                # 每 50 条提交一次
                if idx % 50 == 0:
                    await session.commit()
                logger.info(f"进度: [{idx+1}/{total}] {mai.shortid} - {mai.title}")
            except Exception as e:
                logger.error(f"处理 {mai.shortid} 失败: {e}")
                await session.rollback()

        await session.commit()

    await engine.dispose()
    logger.success("数据同步完成")


def get_sql_alchemy_from_env(env_file: str = ".env.prod") -> str:
    """从 .env 文件中提取数据库文件路径"""
    env_path = Path().cwd() / env_file
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("DATASTORE_DATABASE_URL"):
                    # 获取等号后的部分并去除引号及空格
                    return line.split("=", 1)[1].strip().strip("'").strip('"')
    return ""


if __name__ == "__main__":

    # Loguru 日志配置
    logger.remove()
    logger.add(
        sink=lambda msg: print(msg, end=""),
        level="INFO",
        format="<green>{time:HH:mm:ss}</green> <cyan>[{level}]</cyan> {message}\n",
        colorize=False,
    )

    # 版本映射配置
    config_yaml_path = Path.cwd() / "versions.yaml"
    import yaml
    with open(config_yaml_path, "r", encoding="utf-8") as f:
        versions_config: Dict[int, str] = yaml.safe_load(f)

    from .fetch import process_chart_folders, sync_diving_fish_version
    # 从 ZIP 获取 maidata 数据
    maidata_list = process_chart_folders([  # 排前的优先级更高
        Path.cwd() / "plugin_data" / "maib" / "charts",
        Path.cwd() / "plugin_data" / "maib" / "charts1",
        Path.cwd() / "plugin_data" / "maib" / "charts2",
    ], versions_config)
    maidata_list = sync_diving_fish_version(maidata_list, versions_config)

    logger.success(f"\n提取 {len(maidata_list)} 个谱面数据")

    sql_alchemy = get_sql_alchemy_from_env(".env.prod")
    if sql_alchemy:
        import asyncio
        asyncio.run(run_import(sql_alchemy, maidata_list))
