from recoveryos.domain.models import RecoveryCase
from recoveryos.engine.state import CaseStore


def test_state_store_round_trip_and_order_map(tmp_path):
    store = CaseStore(str(tmp_path / "state.sqlite3"))
    case = RecoveryCase("pay_1", 100.0, "TIMEOUT", .8, .1, 2, 1, 3)
    case.actions_attempted.append("retry_now")
    store.put_case(case)
    loaded = store.get_case("pay_1")
    assert loaded.actions_attempted == ["retry_now"]
    store.map_order("order_1", "pay_1")
    assert store.case_id_for_order("order_1") == "pay_1"
    assert not store.has_event("evt_1")
    store.mark_event("evt_1", "payment.failed")
    assert store.has_event("evt_1")
