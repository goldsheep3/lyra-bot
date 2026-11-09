from .tool import request_json


BASE_URL = "https://www.yuzuchan.moe/api/maimaidx"


class YuzuChaN:
    @staticmethod
    async def yuzuchan_alias_list() -> dict | None:
        """`~/maimaidxalias`"""
        return await request_json(
            BASE_URL + "/maimaidxalias",
            project_name="yuzuchan*/maimaidxalias"
        )
