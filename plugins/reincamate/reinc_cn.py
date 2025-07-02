import os
import json
import random

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from .reincamate import Reincamate


class ReincamateCN(Reincamate):
    """投胎中国"""

    def rgl_random(self, data_path: Path = os.path.join(os.path.dirname(__file__),'cn_humans.json')) -> tuple[str, str, str]:
        with open(data_path, 'r', encoding='utf-8') as file:
            data = json.load(file)

        regions = data.get('country', [])
        chosen_region = random.choices(
            regions,
            weights=[region['population'] for region in regions],
            k=1
        )[0]
        region = chosen_region.get('region', '失落之地')
        gender = self._r100('男', '女', chosen_region.get('male_ratio', 0))
        location_type = self._r100('城市', '农村', data.get('city_ratio', 0))

        return region, gender, location_type

    def generate_img(self, r, g, l, history=None) -> Path | None:
        """生成投胎结果图片"""
        return None
    
    def reincamate(self):
        """投胎处理函数"""
        amount = self._cd_calender()
        if amount < 0:
            return self._msg_output(f'投胎CD中，请{-amount}秒后再试！')
        
        r, g, l = self.rgl_random()
        img_path = self.generate_img(r, g, l, history=None)

        return self._msg_output(
            f' 投胎成功！\n您投胎成了{r}{l}的{g}孩。',
            img_path
        )
    
