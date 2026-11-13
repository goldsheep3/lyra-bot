from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import nonebot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


class CatalogRefactoringTest(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            nonebot.get_driver()
        except ValueError:
            nonebot.init()

        plugin = nonebot.get_plugin("maib") or nonebot.load_plugin("plugins.maib")
        if plugin is None:
            raise RuntimeError("failed to load plugins.maib")

        from plugins.maib import utils
        from plugins.maib.services.models import MaiChart, MaiData, Model
        from plugins.maib.services.refactoring import catalog

        cls.catalog = catalog
        cls.utils = utils
        cls.MaiChart = MaiChart
        cls.MaiData = MaiData
        cls.Model = Model

    async def asyncSetUp(self) -> None:
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as connection:
            await connection.run_sync(self.Model.metadata.create_all)
        self.session_patch = patch.object(
            self.catalog,
            "get_session",
            self.sessions,
        )
        self.session_patch.start()

    async def asyncTearDown(self) -> None:
        self.session_patch.stop()
        await self.engine.dispose()

    def _song(self):
        chart = self.utils.MaiChart(
            shortid=1,
            difficulty=5,
            lv_jp=13.7,
            des="Designer",
        )
        song = self.utils.MaiData(
            shortid=1,
            title="Song",
            bpm=180,
            artist="Artist",
            genre=1,
            cabinet="DX",
            version=25,
            version_cn=None,
            converter="provider-a",
            img_path=Path("covers/song.png"),
        )
        song.set_chart(chart)
        return song

    async def test_sync_song_library_accepts_utils_objects(self) -> None:
        self.assertFalse(await self.catalog.has_song_library())

        await self.catalog.sync_song_library([self._song()])

        self.assertTrue(await self.catalog.has_song_library())
        async with self.sessions() as session:
            song = await session.get(self.MaiData, 1)
            chart = await session.scalar(
                select(self.MaiChart).where(
                    self.MaiChart.shortid == 1,
                    self.MaiChart.difficulty == 5,
                )
            )
        assert song is not None
        assert chart is not None
        self.assertEqual(song.provider, "provider-a")
        self.assertEqual(chart.designer, "Designer")

    async def test_apply_cn_metadata_updates_song_and_chart(self) -> None:
        await self.catalog.sync_song_library([self._song()])

        await self.catalog.apply_cn_metadata(
            [(1, 24)],
            [{"shortid": 1, "difficulty": 5, "level": 13.5}],
        )

        async with self.sessions() as session:
            song = await session.get(self.MaiData, 1)
            chart = await session.scalar(
                select(self.MaiChart).where(
                    self.MaiChart.shortid == 1,
                    self.MaiChart.difficulty == 5,
                )
            )
        assert song is not None
        assert chart is not None
        self.assertEqual(song.version_cn, 24)
        self.assertEqual(chart.lv_cn, 13.5)

    async def test_apply_cn_metadata_rolls_back_as_one_transaction(self) -> None:
        await self.catalog.sync_song_library([self._song()])

        with patch.object(
            self.catalog,
            "rfs_dxra_batch",
            side_effect=RuntimeError("refresh failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "refresh failed"):
                await self.catalog.apply_cn_metadata(
                    [(1, 24)],
                    [{"shortid": 1, "difficulty": 5, "level": 13.5}],
                )

        async with self.sessions() as session:
            song = await session.get(self.MaiData, 1)
            chart = await session.scalar(
                select(self.MaiChart).where(
                    self.MaiChart.shortid == 1,
                    self.MaiChart.difficulty == 5,
                )
            )
        assert song is not None
        assert chart is not None
        self.assertIsNone(song.version_cn)
        self.assertIsNone(chart.lv_cn)


if __name__ == "__main__":
    unittest.main()
