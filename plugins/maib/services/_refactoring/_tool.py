from typing import Protocol, TypeVar, Awaitable, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from nonebot_plugin_datastore import create_session as get_session

_T_co = TypeVar("_T_co", covariant=True)


class FuncWithSession(Protocol[_T_co]):
    def __call__(self, *, session: AsyncSession) -> Awaitable[_T_co]: ...


class execute_func:

    @staticmethod
    async def select(
        func: FuncWithSession[_T_co],
        *,
        session: Optional[AsyncSession],
    ) -> _T_co:
        if session is not None:
            return await func(session=session)

        async with get_session() as session:
            return await func(session=session)

    @staticmethod
    async def action(
        func: FuncWithSession[_T_co],
        *,
        session: Optional[AsyncSession],
        refresh: bool = False,
        ) -> _T_co:
        if session is not None:
            result = await func(session=session)
            await session.flush()
            if refresh and result is not None:
                await session.refresh(result)
            return result

        async with get_session() as session:
            result = await func(session=session)
            await session.commit()
            if refresh and result is not None:
                await session.refresh(result)
            return result