from security.stop_e1 import stop


def test_stop_is_idempotent_and_preserves_other_services(tmp_path):
    shared=tmp_path/'shared-service';shared.write_text('running')
    marker=stop(tmp_path);first=marker.read_bytes()
    assert stop(tmp_path).read_bytes()==first
    assert shared.read_text()=='running'
