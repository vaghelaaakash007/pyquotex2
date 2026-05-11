"""Unit tests for WaitableSlot and wait_until."""
import asyncio
import pytest

from pyquotex._api._waits import SlotRegistry, WaitableSlot, wait_until


@pytest.mark.asyncio
async def test_slot_resolves_with_set_value():
    slot: WaitableSlot[int] = WaitableSlot()

    async def setter():
        await asyncio.sleep(0.01)
        slot.set(42)

    asyncio.create_task(setter())
    assert await slot.wait(timeout=1.0) == 42


@pytest.mark.asyncio
async def test_slot_times_out_when_never_set():
    slot: WaitableSlot[int] = WaitableSlot()
    with pytest.raises(asyncio.TimeoutError):
        await slot.wait(timeout=0.05)


@pytest.mark.asyncio
async def test_slot_can_be_cleared_and_reused():
    slot: WaitableSlot[str] = WaitableSlot()
    slot.set("first")
    assert await slot.wait(timeout=0.1) == "first"
    slot.clear()
    with pytest.raises(asyncio.TimeoutError):
        await slot.wait(timeout=0.05)
    slot.set("second")
    assert await slot.wait(timeout=0.1) == "second"


@pytest.mark.asyncio
async def test_slot_set_before_wait_resolves_immediately():
    slot: WaitableSlot[int] = WaitableSlot()
    slot.set(7)
    assert await slot.wait(timeout=0.1) == 7


@pytest.mark.asyncio
async def test_wait_until_resolves_when_predicate_true():
    counter = {"n": 0}

    async def increment():
        await asyncio.sleep(0.01)
        counter["n"] = 5

    asyncio.create_task(increment())
    await wait_until(lambda: counter["n"] >= 5, timeout=1.0)
    assert counter["n"] == 5


@pytest.mark.asyncio
async def test_wait_until_times_out():
    with pytest.raises(asyncio.TimeoutError):
        await wait_until(lambda: False, timeout=0.05)


def test_slot_registry_has_named_slots():
    reg = SlotRegistry()
    assert reg.balance is not None
    assert reg.balance_update is not None
    assert reg.candle_v2_ready is not None
    assert reg.historical_ready is not None
    assert reg.pending_confirm is not None
    assert reg.sold_option_confirm is not None
    assert reg.training_balance_edit is not None
    assert reg.auth_status is not None


def test_slot_registry_keyed_slots_create_on_access():
    reg = SlotRegistry()
    slot_a = reg.order_confirm("req-1")
    slot_b = reg.order_confirm("req-1")
    slot_c = reg.order_confirm("req-2")
    assert slot_a is slot_b  # same key returns same slot
    assert slot_a is not slot_c  # different key returns different slot


def test_slot_registry_keyed_slot_release():
    reg = SlotRegistry()
    slot = reg.order_confirm("req-1")
    slot.set({"id": 1})
    reg.release_order_confirm("req-1")
    new_slot = reg.order_confirm("req-1")
    assert new_slot is not slot


@pytest.mark.asyncio
async def test_slot_rejects_none():
    """set(None) is invalid — use clear() to reset."""
    slot: WaitableSlot[dict] = WaitableSlot()
    with pytest.raises(ValueError):
        slot.set(None)
    assert not slot.is_set()


@pytest.mark.asyncio
async def test_slot_double_set_uses_latest_value():
    """Second set replaces the first; wait returns the latest value."""
    slot: WaitableSlot[int] = WaitableSlot()
    slot.set(1)
    slot.set(2)
    assert await slot.wait(timeout=0.1) == 2


@pytest.mark.asyncio
async def test_slot_two_consumers_both_resolve():
    """Multiple awaiters on the same slot all receive the value."""
    slot: WaitableSlot[str] = WaitableSlot()

    async def consumer() -> str:
        return await slot.wait(timeout=1.0)

    t1 = asyncio.create_task(consumer())
    t2 = asyncio.create_task(consumer())
    await asyncio.sleep(0.01)  # ensure both are blocked on _event
    slot.set("hello")
    assert await t1 == "hello"
    assert await t2 == "hello"


def test_slot_registry_win_result_release():
    """release_win_result must drop the slot so a fresh one is created next."""
    reg = SlotRegistry()
    slot = reg.win_result("op-1")
    slot.set({"result": "win"})
    reg.release_win_result("op-1")
    new_slot = reg.win_result("op-1")
    assert new_slot is not slot
