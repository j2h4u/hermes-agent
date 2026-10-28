"""Detached child liveness feeds the compact status display."""
import types

def test_heartbeat_relays_a_structural_progress_tick():
    from tools.delegate_tool_child_run import _Heartbeat

    relayed = []
    child = types.SimpleNamespace(
        tool_progress_callback=lambda event, *args, **kwargs: relayed.append((event, args, kwargs)),
        get_activity_summary=lambda: {
            "current_tool": None,
            "api_call_count": 1,
            "max_iterations": 50,
            "last_activity_desc": "waiting for model",
            "last_activity_ts": 1000.0,
        },
    )
    parent = types.SimpleNamespace(_touch_activity=lambda _desc: None)

    _Heartbeat(child, parent, 0).tick()

    assert relayed == [("subagent.heartbeat", (), {})]
