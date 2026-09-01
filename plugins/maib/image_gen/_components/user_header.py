"""
image_gen.components.user_header
用户信息组件
"""
import io
from typing import Optional, Union

from PIL import Image

from ..color import TRANSPARENT, WHITE, GRAY, BLACK
from ..utils import MS, ImageManager, FontManager, FontCode
from .base import TextDrawStyle, Drawer
from ..tools import FullWidthConverter, get_dxra_frame_filename


class UserHeaderBadge:
    """用户信息 header 组件"""
    
    @classmethod
    def board(cls, dxrating: Optional[int], username: str, avatar: Optional[Union[bytes, Image.Image]] = None,
              display_content: str = "Update: [JP] Unknown Update Time",
              dxra_cirp_frame: bool = True, dan: Optional[int] = None, ms: MS = MS()) -> Image.Image:
        """生成用户信息看板"""
        width, height = 310, 50
        img = Image.new("RGBA", ms.xy(width, height), TRANSPARENT)
        drawer = Drawer(img, ms=ms)
        
        # plate
        plate_size = (310, 50)
        plate_xy = (0, 0)
        plate_img = ImageManager.plate_default(size=ms.xy(*plate_size))
        if plate_img:
            img.paste(plate_img, ms.xy(*plate_xy), plate_img)

        # avatar
        avatar_size = (44, 44)
        avatar_xy = (3, 3)
        avatar_radius = 2
        avatar_img: Optional[Image.Image] = None
        if avatar:
            if isinstance(avatar, bytes):
                try:
                    avatar_img = Image.open(io.BytesIO(avatar)).convert("RGBA")
                except Exception:
                    pass
            elif isinstance(avatar, Image.Image):
                avatar_img = avatar.copy().convert("RGBA")
        avatar_img = avatar_img or Image.new("RGBA", ms.xy(*avatar_size), color=BLACK)
        if avatar_img.size != ms.xy(*avatar_size):
            resized_avatar = avatar_img.resize(ms.xy(*avatar_size), Image.Resampling.LANCZOS)
            avatar_img.close()
            avatar_img = resized_avatar
        avatar_mask = drawer.get_mask(*avatar_size, radius=avatar_radius, ms=ms)
        img.paste(avatar_img, ms.xy(*avatar_xy), avatar_mask)
        avatar_mask.close()
        drawer.rounded_rect(*avatar_xy, *avatar_size, radius=avatar_radius, fill=None,
                            outline=GRAY if plate_img else WHITE, width=0.5)
        
        # DXRating
        dxrating_size = (75, 15)
        dxrating_xy = (48, 2.5)
        if dxrating is not None:
            dxra_img_filename = get_dxra_frame_filename(dxrating, cirp_frame=dxra_cirp_frame)
            dxra_img = ImageManager.dxrating_image(dxra_img_filename, size=ms.xy(*dxrating_size))
            if dxra_img:
                img.paste(dxra_img, ms.xy(*dxrating_xy), dxra_img)
            else:
                x, y, w, h = *dxrating_xy, *dxrating_size
                x, y, w, h = x+0.5, y+0.5, w-1, h-1
                drawer.rounded_rect(x, y, w, h, radius=1, fill=WHITE,
                                    outline=GRAY, width=0.5)
                drawer.text(x=x+8, y=y+h/2, text="  DX\nRating", tds=TextDrawStyle(
                        fill=BLACK, anchor="lm", font=FontManager.font(FontCode.JBMono_Medium, size=ms.x(5))
                ))
            # DXRating 值
            dxrating_font = FontManager.font(FontCode.MiSans_Demibold, size=ms.x(8.5))
            for i, digit in enumerate(str(dxrating)[::-1]):
                drawer.text(110 - 6 * i, 10, text=digit, tds=TextDrawStyle(
                    fill="#FCC916", anchor="mm", font=dxrating_font, stroke="#333333", stroke_width=0.5
                ))

        # Username
        username_size = (115, 17)
        username_xy = (48.5, 19)
        drawer.rounded_rect(*username_xy, *username_size,
                            fill=WHITE, radius=2,
                            outline=GRAY, width=0.5)
        drawer.text(username_xy[0]+0.5, username_xy[1]+8.5, text=FullWidthConverter.convert(username), tds=TextDrawStyle(
            fill=BLACK, anchor="lm", font=FontManager.font(FontCode.MiSans_Demibold, size=ms.x(10))
        ))
        
        # dan
        if len(username) <= 8 and dan is not None:
            # 名字长度不超过8字符，段位空间存在
            dan_size = (34, 15)
            dan_xy = (128, 20)
            dan_img = ImageManager.dan(dan, size=ms.xy(*dan_size))
            if dan_img:
                img.paste(dan_img, ms.xy(*dan_xy), dan_img)
        
        # Shougou
        shougou_size = (115, 9)
        shougou_xy = (48.5, 38)
        drawer.capsule(*shougou_xy, *shougou_size, fill="#FCC916",
                       outline="#DFAE00", outline_width=0.5)
        drawer.text(shougou_xy[0]+shougou_size[0]/2, shougou_xy[1]+shougou_size[1]/2, text=display_content, tds=TextDrawStyle(
            fill=BLACK, anchor="mm", font=FontManager.font(FontCode.MiSans_Demibold, size=ms.x(6))
        ))

        return img
