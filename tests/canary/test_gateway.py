import pytest

from deploy.canary.gateway import render


@pytest.mark.parametrize("stage", [0, 10, 50, 100])
def test_split_routes_and_private_preview(stage):
    text = render(stage, "k" * 32)
    assert f"Generated stage {stage}" in text
    assert '"1:true" canary' in text
    assert '"1:baseline" stable' in text
    assert "if ($authorized = 0) { return 403; }" in text
    assert "proxy_next_upstream off" in text
    assert "map_hash_bucket_size 256" in text
    if stage == 0:
        assert "* stable;" in text
        assert "0%" not in text
    if stage == 100:
        assert "* canary;" in text


@pytest.mark.parametrize("stage,key", [(5, "k" * 32), (True, "k" * 32), (10, 'x"; evil;'), (0, "")])
def test_invalid_stage_or_config_injection(stage, key):
    with pytest.raises(ValueError):
        render(stage, key)
