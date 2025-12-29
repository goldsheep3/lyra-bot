import sqlite3
from pathlib import Path
from typing import Dict, List

from loguru import logger

from extract_maidata import process_zip_files, MaiData, UtageMaiData


def create_database(db_path:  Path) -> None:
    """
    创建 SQLite 数据库和表结构

    Args:
        db_path: 数据库文件路径
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 创建主表：maidata
    cursor.execute('DROP TABLE IF EXISTS maidata')
    cursor.execute('''
                   CREATE TABLE maidata
                   (
                       shortid         INTEGER PRIMARY KEY, -- 使用 shortid 作为主键
                       title           TEXT    NOT NULL,    -- 曲名
                       bpm             INTEGER NOT NULL,    -- 写谱 bpm
                       artist          TEXT,                -- 艺术家
                       genre           TEXT NOT NULL,       -- 流派
                       cabinet         TEXT NOT NULL,       -- 谱面类型(SD/DX)
                       version         INTEGER NOT NULL,    -- 谱面更新版本（日服）
                       version_cn      INTEGER,             -- 谱面更新版本（国服）
                       converter       TEXT                 -- 谱面来源
                   )
                   ''')

    # 创建谱面表：charts
    cursor.execute('DROP TABLE IF EXISTS charts')
    cursor.execute('''
                   CREATE TABLE charts
                   (
                       id           INTEGER PRIMARY KEY AUTOINCREMENT,
                       shortid      INTEGER NOT NULL,       -- 关联 maidata 表的 ID
                       chart_number INTEGER NOT NULL,       -- 谱面难度编号 (1-6)
                       lv           REAL    NOT NULL,       -- 谱面难度定数
                       des          TEXT    NOT NULL,       -- 谱师
                       inote        TEXT    NOT NULL,       -- 谱面文本
                       
                       FOREIGN KEY (shortid) REFERENCES maidata (shortid) ON DELETE CASCADE,
                       UNIQUE (shortid, chart_number)
                   )
                   ''')

    # 创建 utage 表：utage_maidata
    cursor.execute('DROP TABLE IF EXISTS utage_maidata')
    cursor.execute('''
                    CREATE TABLE utage_maidata
                    (
                        shortid         INTEGER PRIMARY KEY, -- 使用 shortid 作为主键
                        title           TEXT    NOT NULL,    -- 曲名
                        bpm             INTEGER NOT NULL,    -- 写谱 bpm
                        artist          TEXT,                -- 艺术家
                        genre           TEXT NOT NULL,       -- 流派
                        cabinet         TEXT NOT NULL,       -- 谱面类型(SD/DX)
                        version         INTEGER,             -- 谱面更新版本
                        converter       TEXT,                -- 谱面来源
                        
                        utage_tag       TEXT,                -- Utage 标签
                        buddy           BOOLEAN              -- Buddy 人数
                    )
                    ''')

    # 创建 utage 谱面表：utage_charts
    cursor.execute('DROP TABLE IF EXISTS utage_charts')
    cursor.execute('''
                   CREATE TABLE utage_charts
                   (
                       id           INTEGER PRIMARY KEY AUTOINCREMENT,
                       shortid      INTEGER NOT NULL,       -- 关联 maidata 表的 ID
                       chart_number INTEGER NOT NULL,       -- 谱面难度编号 (1-6)
                       lv           REAL    NOT NULL,       -- 谱面难度定数
                       des          TEXT    NOT NULL,       -- 谱师
                       inote        TEXT    NOT NULL,       -- 谱面文本

                       FOREIGN KEY (shortid) REFERENCES utage_maidata (shortid) ON DELETE CASCADE,
                       UNIQUE (shortid, chart_number)
                   )
                   ''')

    # 创建别名表
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS aliases
                   (
                       id       INTEGER PRIMARY KEY AUTOINCREMENT,
                       shortid  INTEGER NOT NULL,           -- 关联 maidata 表的 ID
                       alias    TEXT    NOT NULL,           -- 乐曲别名
                       
                       create_time INTEGER NOT NULL,
                       create_qq   INTEGER NOT NULL,
                       create_qq_group INTEGER,
                       
                       FOREIGN KEY (shortid) REFERENCES maidata (shortid) ON DELETE CASCADE,
                       UNIQUE (shortid, alias)
                   )
                   ''')

    # 创建索引
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_maidata_title ON maidata(title)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_maidata_shortid ON maidata(shortid)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_charts_lv ON charts(lv)')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_utage_maidata_title ON utage_maidata(title)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_utage_charts_utage_maidata_id ON utage_charts(shortid)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_utage_charts_lv ON utage_charts(lv)')

    conn.commit()
    conn.close()

    logger.info("✅ 数据库表结构创建完成")


def insert_normal_maidata(db_path: Path, maidata: MaiData) -> bool:
    """
    插入普通 MaiData 数据到数据库

    Args:
        db_path: 数据库文件路径
        maidata: MaiData 对象

    Returns:
        是否插入成功
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 插入主表数据
        cursor.execute('''
            INSERT INTO maidata 
            (
                shortid        , -- 使用 shortid 作为主键
                title          , -- 曲名
                bpm            , -- 写谱 bpm
                artist         , -- 艺术家
                genre          , -- 流派
                cabinet        , -- 谱面类型(SD/DX)
                version        , -- 谱面更新版本
                version_cn     , -- 谱面更新版本（国服）
                converter        -- 谱面来源
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            maidata.shortid,
            maidata.title,
            maidata.bpm,
            maidata.artist,
            maidata.genre,
            maidata.cabinet,
            maidata.version,
            maidata.version_cn,
            maidata.converter
        ))

        # 插入谱面数据
        for chart_num in range(2, 7):
            chart = getattr(maidata, f'chart{chart_num}')
            if chart:
                cursor.execute('''
                               INSERT INTO charts
                                   (shortid, chart_number, lv, des, inote)
                               VALUES (?, ?, ?, ?, ?)
                               ''', (
                                   maidata.shortid,
                                   chart_num,
                                   chart.lv,
                                   chart.des,
                                   chart.inote
                               ))

        conn.commit()
        conn.close()
        return True

    except sqlite3.Error as e:
        logger.info(f"❌ 数据库错误: {e}")
        return False
    except Exception as e:
        logger.info(f"❌ 插入失败: {e}")
        return False


def insert_utage_maidata(db_path: Path, maidata: UtageMaiData) -> bool:
    """
    插入宴会场 MaiData 数据到数据库

    Args:
        db_path: 数据库文件路径
        maidata: UtageMaiData 对象

    Returns:
        是否插入成功
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 插入主表数据
        cursor.execute('''
                       INSERT INTO utage_maidata
                       (
                           shortid        , -- 使用 shortid 作为主键
                           title          , -- 曲名
                           bpm            , -- 写谱 bpm
                           artist         , -- 艺术家
                           genre          , -- 流派
                           cabinet        , -- 谱面类型(SD/DX)
                           version        , -- 谱面更新版本
                           converter      , -- 谱面来源
                           
                           utage_tag      , -- Utage 标签
                           buddy           -- Buddy 人数
                       )
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ''', (
                           maidata.shortid,
                           maidata.title,
                           maidata.bpm,
                           maidata.artist,
                           maidata.genre,
                           maidata.cabinet,
                           maidata.version,
                           maidata.converter,

                           maidata.utage_tag,
                           maidata.buddy,
                       ))

        # 插入谱面数据
        for chart_num in range(2, 8):
            chart = getattr(maidata, f'chart{chart_num}')
            if chart:
                cursor.execute('''
                               INSERT INTO utage_charts
                                   (shortid, chart_number, lv, des, inote)
                               VALUES (?, ?, ?, ?, ?)
                               ''', (
                                   maidata.shortid,
                                   chart_num,
                                   chart.lv,
                                   chart.des,
                                   chart.inote
                               ))

        conn.commit()
        conn.close()
        return True

    except sqlite3.Error as e:
        logger.info(f"❌ 数据库错误: {e}")
        return False
    except Exception as e:
        logger.info(f"❌ 插入失败: {e}")
        return False


def batch_insert_maidata(db_path: Path, maidata: List[MaiData | UtageMaiData]) -> int:
    """
    批量插入 MaiData 数据到数据库

    Args:
        db_path: 数据库文件路径
        maidata: MaiData

    Returns:
        成功插入的数量
    """
    success_count = 0
    total_count = len(maidata)

    logger.info(f"💾 开始批量插入 {total_count} 条数据")

    for mai in maidata:
        if isinstance(mai, UtageMaiData):
            if insert_utage_maidata(db_path, mai):
                success_count += 1
                logger.info(f"✅ [{success_count}/{total_count}] {mai.shortid}:\t{mai.title}")
            else:
                logger.info(f"❌ [{success_count}/{total_count}] {mai.shortid}:\t插入失败")
        else:
            if insert_normal_maidata(db_path, mai):
                success_count += 1
                logger.info(f"✅ [{success_count}/{total_count}] {mai.shortid}:\t{mai.title}")
            else:
                logger.info(f"❌ [{success_count}/{total_count}] {mai.shortid}:\t插入失败")

    logger.info(f"🎉 批量插入完成，成功 {success_count}/{total_count} 条")
    return success_count


def get_database_stats(db_path: Path) -> Dict[str, any]:
    """
    获取数据库统计信息

    Args:
        db_path: 数据库文件路径

    Returns:
        统计信息字典
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 统计普通歌曲数量
    cursor.execute('SELECT COUNT(*) FROM maidata')
    normal_song_count = cursor.fetchone()[0]

    # 统计普通谱面数量
    cursor.execute('SELECT COUNT(*) FROM charts')
    normal_chart_count = cursor.fetchone()[0]

    # 统计 utage 歌曲数量
    cursor.execute('SELECT COUNT(*) FROM utage_maidata')
    utage_song_count = cursor.fetchone()[0]

    # 统计 utage 谱面数量
    cursor.execute('SELECT COUNT(*) FROM utage_charts')
    utage_chart_count = cursor.fetchone()[0]

    # 统计各难度谱面数量（普通）
    cursor.execute('''
                   SELECT chart_number, COUNT(*) as count
                   FROM charts
                   GROUP BY chart_number
                   ORDER BY chart_number
                   ''')
    difficulty_stats = cursor.fetchall()

    conn.close()

    return {
        'normal_songs': normal_song_count,
        'normal_charts': normal_chart_count,
        'utage_songs': utage_song_count,
        'utage_charts': utage_chart_count,
        'difficulty_distribution': {f'chart{num}': count for num, count in difficulty_stats}
    }


if __name__ == "__main__":

    logger.info("🚀 开始处理 maimai 数据")

    # 配置路径
    database_path = Path(input("DATABASE FILE: "))

    config_yaml_path = Path(input("CONFIG YAML PATH: "))
    import yaml
    with open(config_yaml_path, "r", encoding="utf-8") as f:
        versions_config: Dict[int, str] = yaml.safe_load(f)

    zip_folder_paths = []
    while True:
        zip_folder_path = input("ZIP FOLDER (leave empty to finish): ")
        if not zip_folder_path:
            break
        zip_folder_paths.append(Path(zip_folder_path))

    # 创建数据库
    logger.info("📦 创建数据库")
    create_database(database_path)

    # 提取数据
    logger.info("📦 提取 zip 文件数据")
    maidata_list = list()
    for path in zip_folder_paths:
        new_list = process_zip_files(path, versions_config)
        old_set = {m.shortid for m in maidata_list}
        # 过滤重复 shortid
        add_list = [new for new in new_list if new.shortid not in old_set]
        maidata_list += add_list

    # 补充 CN 版本信息
    logger.info("✉ 提取 CN 文件数据")
    from adx_downloader import MergeChartCNVersionData
    from extract_maidata import parse_diving_fish_version
    cn_ver = MergeChartCNVersionData().merge_chart_cnver_data()  # id: version
    for mai in maidata_list:
        raw_cn_ver = cn_ver.get(str(mai.shortid), "")
        raw_cn_ver = raw_cn_ver if raw_cn_ver else ""
        if not isinstance(mai, UtageMaiData):
            mai.version_cn = parse_diving_fish_version(raw_cn_ver, versions_config)

    # 批量插入
    logger.info("💾 插入数据到数据库")
    batch_insert_maidata(database_path, maidata_list)

    # 显示统计信息
    logger.info("📊 数据库统计信息:")
    stats = get_database_stats(database_path)
    logger.info(f"  普通歌曲数:  {stats['normal_songs']}")
    logger.info(f"  普通谱面数: {stats['normal_charts']}")
    logger.info(f"  Utage 歌曲数: {stats['utage_songs']}")
    logger.info(f"  Utage 谱面数: {stats['utage_charts']}")
