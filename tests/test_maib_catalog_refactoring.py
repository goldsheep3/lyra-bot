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

        from plugins.maib import config, utils
        from plugins.maib.services.models import MaiAlias, MaiChart, MaiChartAch, MaiData, Model
        from plugins.maib.services.refactoring import catalog
        from plugins.maib.utils.enums import Server, ServerScope

        cls.catalog = catalog
        cls.config = config
        cls.utils = utils
        cls.MaiChart = MaiChart
        cls.MaiChartAch = MaiChartAch
        cls.MaiAlias = MaiAlias
        cls.MaiData = MaiData
        cls.Model = Model
        cls.Server = Server
        cls.ServerScope = ServerScope

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
            designer="Designer",
        )
        song = self.utils.MaiData(
            shortid=1,
            title="Song",
            bpm=180,
            artist="Artist",
            genre=1,
            cabinet="DX",
            version_jp=25,
            version_cn=None,
            converter="provider-a",
            img_path=Path("covers/song.png"),
            zip_path=Path("charts/song.zip"),
            _tg_adx_id_cache="adx-file-id",
            _tg_zip_id_cache="zip-file-id",
        )
        song.set_chart(chart)
        return song

    async def _add_achievement_rows(self) -> None:
        await self.catalog.sync_song_library([self._song()])
        async with self.sessions() as session:
            chart = await session.scalar(
                select(self.MaiChart).where(
                    self.MaiChart.shortid == 1,
                    self.MaiChart.difficulty == 5,
                )
            )
            assert chart is not None
            session.add_all(
                [
                    self.MaiChartAch(
                        chart_id=chart.id,
                        shortid=1,
                        difficulty=5,
                        server=self.Server.CN,
                        provider="diving-fish",
                        qq=10001,
                        achievement=1_000_000,
                    ),
                    self.MaiChartAch(
                        chart_id=chart.id,
                        shortid=1,
                        difficulty=5,
                        server=self.Server.CN,
                        provider="provider-alt",
                        qq=10001,
                        achievement=990_000,
                    ),
                    self.MaiChartAch(
                        chart_id=chart.id,
                        shortid=1,
                        difficulty=5,
                        server=self.Server.JP,
                        provider="lyrasync-oto",
                        qq=10001,
                        achievement=980_000,
                    ),
                    self.MaiChartAch(
                        chart_id=chart.id,
                        shortid=1,
                        difficulty=5,
                        server=self.Server.JP,
                        provider="provider-alt",
                        qq=10001,
                        achievement=970_000,
                    ),
                    self.MaiChartAch(
                        chart_id=chart.id,
                        shortid=1,
                        difficulty=5,
                        server=self.Server.CN,
                        provider="diving-fish",
                        qq=10002,
                        achievement=960_000,
                    ),
                ]
            )
            await session.commit()

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

    async def test_get_song_returns_utils_data_and_resolves_pack_path(self) -> None:
        self.assertIsNone(await self.catalog.get_maidata(999))
        await self.catalog.sync_song_library([self._song()])

        song = await self.catalog.get_maidata(1)

        assert song is not None
        self.assertIsInstance(song, self.utils.MaiData)
        chart = song.get_chart(5)
        assert chart is not None
        self.assertIsNotNone(chart._id)
        self.assertEqual(song.zip_path, Path("charts/song.zip"))
        self.assertEqual(song.get_telegram_cache("adx"), "adx-file-id")
        self.assertEqual(song.get_telegram_cache("zip"), "zip-file-id")
        with patch.object(self.config, "CHART_DATA_DIR", "D:/maib-data"):
            self.assertEqual(
                song.get_zip_path(),
                Path("D:/maib-data/charts/song.zip"),
            )

    async def test_get_maidata_filters_achievements_by_scope_and_provider(self) -> None:
        await self._add_achievement_rows()

        unloaded = await self.catalog.get_maidata(1)
        cn = await self.catalog.get_maidata(1, qq=10001)
        jp = await self.catalog.get_maidata(
            1,
            qq=10001,
            server=self.ServerScope.JP,
        )
        all_default = await self.catalog.get_maidata(
            1,
            qq=10001,
            server=self.ServerScope.ALL,
        )
        cn_override = await self.catalog.get_maidata(
            1,
            qq=10001,
            provider="provider-alt",
        )
        all_override = await self.catalog.get_maidata(
            1,
            qq=10001,
            server=self.ServerScope.ALL,
            provider="provider-alt",
        )

        assert unloaded is not None
        assert cn is not None
        assert jp is not None
        assert all_default is not None
        assert cn_override is not None
        assert all_override is not None
        self.assertEqual(unloaded.get_chart(5).get_ach(self.Server.CN).achievement, -100)
        self.assertEqual(cn.get_chart(5).get_ach(self.Server.CN).achievement, 100.0)
        self.assertEqual(cn.get_chart(5).get_ach(self.Server.JP).achievement, -100)
        self.assertEqual(jp.get_chart(5).get_ach(self.Server.JP).achievement, 98.0)
        self.assertEqual(all_default.get_chart(5).get_ach(self.Server.CN).achievement, 100.0)
        self.assertEqual(all_default.get_chart(5).get_ach(self.Server.JP).achievement, 98.0)
        self.assertEqual(cn_override.get_chart(5).get_ach(self.Server.CN).achievement, 99.0)
        self.assertEqual(all_override.get_chart(5).get_ach(self.Server.CN).achievement, 99.0)
        self.assertEqual(all_override.get_chart(5).get_ach(self.Server.JP).achievement, 97.0)

    async def test_search_maidata_returns_utils_and_matched_alias(self) -> None:
        await self._add_achievement_rows()
        async with self.sessions() as session:
            session.add(self.MaiAlias(shortid=1, name="Test Alias", create_qq=10001))
            await session.commit()

        songs = await self.catalog.search_maidata(
            "test alias",
            qq=10001,
            server=self.ServerScope.ALL,
        )

        self.assertEqual(len(songs), 1)
        self.assertIsInstance(songs[0], self.utils.MaiData)
        self.assertEqual(songs[0]._matched_alias, "Test Alias")
        chart = songs[0].get_chart(5)
        assert chart is not None
        self.assertEqual(chart.get_ach(self.Server.CN).achievement, 100.0)
        self.assertEqual(chart.get_ach(self.Server.JP).achievement, 98.0)

    async def test_search_maidata_keeps_blur_result_limit(self) -> None:
        await self.catalog.sync_song_library([self._song()])
        with patch.object(self.config, "MAX_BLUR_SEARCH_RESULTS", 0):
            with self.assertRaises(self.utils.BlurSearchTooManyResultsError):
                await self.catalog.search_maidata("song", mode="blur")

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
