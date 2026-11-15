from __future__ import annotations

import unittest
from unittest.mock import patch

import nonebot
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


class AliasRefactoringTest(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            nonebot.get_driver()
        except ValueError:
            nonebot.init()

        plugin = nonebot.get_plugin("maib") or nonebot.load_plugin("plugins.maib")
        if plugin is None:
            raise RuntimeError("failed to load plugins.maib")

        from plugins.maib.services.models import MaiAlias, MaiData, Model
        from plugins.maib.services.refactoring import alias

        cls.alias = alias
        cls.MaiAlias = MaiAlias
        cls.MaiData = MaiData
        cls.Model = Model

    async def asyncSetUp(self) -> None:
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as connection:
            await connection.run_sync(self.Model.metadata.create_all)
        self.session_patch = patch.object(self.alias, "get_session", self.sessions)
        self.session_patch.start()

        async with self.sessions() as session:
            session.add(
                self.MaiData(
                    shortid=1,
                    title="Song",
                    bpm=180,
                    artist="Artist",
                    genre=1,
                    cabinet="DX",
                    version_jp=25,
                    version_cn=None,
                    provider="provider-a",
                    img_path="covers/song.png",
                )
            )
            await session.commit()

    async def asyncTearDown(self) -> None:
        self.session_patch.stop()
        await self.engine.dispose()

    async def test_add_alias_validates_song_and_duplicate(self) -> None:
        self.assertEqual(await self.alias.add_alias(999, "Alias", qq=10001), "missing")
        self.assertEqual(await self.alias.add_alias(1, "Alias", qq=10001), "success")
        self.assertEqual(await self.alias.add_alias(1, "Alias", qq=10002), "exists")

    async def test_remove_alias_requires_creator_qq(self) -> None:
        self.assertEqual(await self.alias.remove_alias(1, "Missing", qq=10001), "not_exists")

        await self.alias.add_alias(1, "Alias", qq=10001)
        self.assertEqual(await self.alias.remove_alias(1, "Alias", qq=10002), "not_owner")
        self.assertEqual(await self.alias.remove_alias(1, "Alias", qq=10001), "success")
        self.assertEqual(await self.alias.remove_alias(1, "Alias", qq=10001), "not_exists")

    async def test_remove_alias_rejects_unknown_song(self) -> None:
        self.assertEqual(await self.alias.remove_alias(999, "Alias", qq=10001), "missing")

    async def test_remove_alias_rejects_alias_without_matching_creator(self) -> None:
        async with self.sessions() as session:
            session.add(self.MaiAlias(shortid=1, name="Legacy", create_qq=None))
            await session.commit()

        self.assertEqual(await self.alias.remove_alias(1, "Legacy", qq=10001), "not_owner")


if __name__ == "__main__":
    unittest.main()
