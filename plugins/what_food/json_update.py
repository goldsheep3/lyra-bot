import json
import numpy as np
import shutil
import random
from pathlib import Path
from nonebot import logger

from .models import EatableItem, ScoreRecord, UserPreference
from .services import create_session

async def full_migrate_old_data(
    food_json_path: Path, 
    drink_json_path: Path, 
    food_npz_path: Path, 
    drink_npz_path: Path,
    user_offset_json_path: Path
):
    """
    深度迁移脚本：合并打乱 ID，注入评分及用户偏好，并备份旧文件
    """
    config = [
        {"cat": "Food", "json": food_json_path, "npz": food_npz_path},
        {"cat": "Drink", "json": drink_json_path, "npz": drink_npz_path}
    ]

    # --- 第一阶段：收集并打乱所有食物项 ---
    all_items_to_create = []
    old_to_new_mapping = {} # 格式: {(category, old_id): new_database_id}

    for cfg in config:
        if not cfg["json"].exists():
            continue
            
        with open(cfg["json"], 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
            for old_id_str, info in raw_data.items():
                all_items_to_create.append({
                    "old_id": int(old_id_str),
                    "name": info["name"],
                    "category": cfg["cat"],
                    "is_wine": info.get("is_wine", False),
                    "create_qq": -1
                })

    if not all_items_to_create:
        logger.warning("未发现可迁移的食物/饮品数据文件。")
    else:
        # 核心逻辑：随机打乱顺序
        random.shuffle(all_items_to_create)
        logger.info(f"已打乱共 {len(all_items_to_create)} 项数据，准备分配新 ID。")

        # --- 第二阶段：写入数据库并构建 ID 映射 ---
        async with create_session() as session:
            for index, item_info in enumerate(all_items_to_create, start=1):
                new_item = EatableItem(
                    id=index, 
                    name=item_info["name"],
                    category=item_info["category"],
                    is_wine=item_info["is_wine"],
                    create_qq=item_info["create_qq"],
                    current_score=0.0,
                    total_weighted_sum=0,
                    total_weight=0
                )
                session.add(new_item)
                old_to_new_mapping[(item_info["category"], item_info["old_id"])] = index
            
            await session.commit()
            logger.success(f"基础项目迁移完成，最高新 ID 为: {len(all_items_to_create)}")

        # --- 第三阶段：解析 NPZ 并注入评分 ---
        score_total = 0
        for cfg in config:
            if not cfg["npz"].exists():
                continue

            with np.load(cfg["npz"]) as npz_file:
                data = npz_file['data']
                old_item_ids = npz_file['item_ids'].tolist()
                user_ids = npz_file['user_ids'].tolist()

            async with create_session() as session:
                for i_idx, old_id in enumerate(old_item_ids):
                    new_id = old_to_new_mapping.get((cfg["cat"], old_id))
                    if not new_id: continue

                    db_item = await session.get(EatableItem, new_id)
                    if not db_item: continue
                    
                    for u_idx, user_id in enumerate(user_ids):
                        score = int(data[i_idx, u_idx])
                        if score <= 0: continue
                        
                        # 映射逻辑：-127 (旧版 SU) -> -25 (新版 SU)，权重 15
                        current_weight = 15 if user_id == -127 else 1
                        final_user_id = -25 if user_id == -127 else user_id

                        new_record = ScoreRecord(
                            item_id=new_id,
                            user_id=final_user_id,
                            score=score,
                            weight=current_weight
                        )
                        session.add(new_record)

                        db_item.total_weighted_sum += score * current_weight
                        db_item.total_weight += current_weight
                        score_total += 1

                    if db_item.total_weight > 0:
                        db_item.current_score = round(db_item.total_weighted_sum / db_item.total_weight, 2)
                
                await session.commit()
            logger.info(f"已完成 {cfg['cat']} 类的评分迁移。")

    # --- 第四阶段：迁移用户偏好 (User Preference) ---
    pref_count = 0
    if user_offset_json_path.exists():
        logger.info("正在迁移用户偏好数据...")
        with open(user_offset_json_path, 'r', encoding='utf-8') as f:
            try:
                user_offsets = json.load(f)
                async with create_session() as session:
                    for uid_str, offset in user_offsets.items():
                        user_id = int(uid_str)
                        # 注意：模型中字段名为 target_score 或 offset，请确保与 models.py 一致
                        # 此处根据您之前 services.py 的逻辑使用 target_score
                        new_pref = UserPreference(user_id=user_id, target_score=float(offset))
                        session.add(new_pref)
                        pref_count += 1
                    await session.commit()
                logger.success(f"用户偏好迁移完成，共 {pref_count} 条记录。")
            except Exception as e:
                logger.error(f"用户偏好解析失败: {e}")

    # --- 第五阶段：清理与备份 ---
    files_to_backup = [food_json_path, drink_json_path, food_npz_path, drink_npz_path, user_offset_json_path]
    for p in files_to_backup:
        if p.exists():
            backup_p = p.with_suffix(p.suffix + '.old')
            try:
                shutil.move(str(p), str(backup_p))
                logger.info(f"已备份: {p.name} -> {backup_p.name}")
            except Exception as e:
                logger.error(f"备份文件 {p.name} 失败: {e}")
    
    logger.success(f"所有迁移任务结束！食物项: {len(all_items_to_create)}, 评分: {score_total}, 偏好: {pref_count}")
