import asyncio

import anyio
import pytest
from fastapi import HTTPException

from app.resource_lab import ResourceFault


@pytest.mark.parametrize('protected,admitted',[(False,6),(True,4)])
def test_real_worker_exhaustion_and_rollback(protected,admitted):
    async def check():
        limiter=anyio.to_thread.current_default_thread_limiter()
        limiter.total_tokens=6
        state=ResourceFault(protected,'R1' if protected else 'R0')
        try:
            result=await state.inject(6,2)
            assert result['admitted']==admitted and result['rejected']==6-admitted
            assert limiter.borrowed_tokens==(0 if protected else 6)
            with pytest.raises(HTTPException) as exc:
                await state.inject(6,2)
            assert exc.value.status_code==409
        finally:
            assert (await state.release())['rollback_verified']
        assert limiter.borrowed_tokens==0
    asyncio.run(check())


def test_fault_expires_without_controller():
    async def check():
        state=ResourceFault(False,'R0')
        await state.inject(2,1)
        await asyncio.sleep(1.1)
        assert not state.tasks
    asyncio.run(check())
