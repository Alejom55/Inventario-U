from unittest.mock import Mock

import pytest

from scripts.cleanup_oci import cleanup


def clients():
    compute, storage = Mock(), Mock()
    compute.get_instance.return_value.data = Mock(compartment_id="project", lifecycle_state="STOPPED")
    storage.get_bucket.return_value.data = Mock(compartment_id="project", versioning="Disabled")
    return compute, storage


@pytest.mark.parametrize("bucket,confirmation", [("state", "state"), ("demo-json", "wrong")])
def test_requires_exact_confirmation_before_access(bucket, confirmation):
    compute, storage = clients()
    with pytest.raises(ValueError):
        cleanup(compute, storage, "vm", "project", "ns", bucket, confirmation)
    storage.get_bucket.assert_not_called()


def test_rejects_other_compartments():
    compute, storage = clients()
    storage.get_bucket.return_value.data.compartment_id = "someone-else"
    with pytest.raises(ValueError):
        cleanup(compute, storage, "vm", "project", "ns", "demo-json", "demo-json")
    compute.instance_action.assert_not_called()
    storage.delete_object.assert_not_called()


def test_rejects_versioned_bucket():
    compute, storage = clients()
    storage.get_bucket.return_value.data.versioning = "Enabled"
    with pytest.raises(ValueError):
        cleanup(compute, storage, "vm", "project", "ns", "demo-json", "demo-json")
    storage.delete_object.assert_not_called()


def test_stops_writer_then_deletes_all_pages():
    compute, storage = clients()
    compute.get_instance.side_effect = [
        Mock(data=Mock(compartment_id="project", lifecycle_state="RUNNING")),
        Mock(data=Mock(lifecycle_state="STOPPED")),
    ]
    storage.list_objects.side_effect = [
        Mock(data=Mock(objects=[Mock(**{"name": "one"})])),
        Mock(data=Mock(objects=[Mock(**{"name": "two"})])),
        Mock(data=Mock(objects=[])),
    ]
    cleanup(compute, storage, "vm", "project", "ns", "demo-json", "demo-json")
    compute.instance_action.assert_called_once_with("vm", "STOP")
    assert storage.delete_object.call_count == 2
