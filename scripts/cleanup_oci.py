"""Stop this demo's writer and empty its unversioned bucket before destroy."""

import argparse
import time

import oci


def cleanup(compute, storage, instance_id, compartment_id, namespace, bucket, confirmation):
    if confirmation != bucket or not bucket.endswith("-json"):
        raise ValueError("Confirm the exact demo bucket ending in -json")
    metadata = storage.get_bucket(namespace, bucket).data
    if metadata.compartment_id != compartment_id or metadata.versioning != "Disabled":
        raise ValueError("Wrong compartment or versioned bucket: manual review required")
    instance = compute.get_instance(instance_id).data
    if instance.compartment_id != compartment_id:
        raise ValueError("Instance is outside the deployment compartment")
    if instance.lifecycle_state not in {"STOPPED", "TERMINATED"}:
        compute.instance_action(instance_id, "STOP")
        deadline = time.monotonic() + 600
        while compute.get_instance(instance_id).data.lifecycle_state != "STOPPED":
            if time.monotonic() >= deadline:
                raise TimeoutError("Instance did not stop; bucket preserved")
            time.sleep(10)
    # Read the first page again after deleting it, avoiding invalid pagination cursors.
    while True:
        objects = storage.list_objects(namespace, bucket, limit=100).data.objects
        if not objects:
            return
        for item in objects:
            storage.delete_object(namespace, bucket, item.name)


def main():
    parser = argparse.ArgumentParser()
    for name in ("instance-id", "compartment-id", "namespace", "bucket", "confirm"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    config = oci.config.from_file()
    cleanup(oci.core.ComputeClient(config), oci.object_storage.ObjectStorageClient(config),
            args.instance_id, args.compartment_id, args.namespace, args.bucket, args.confirm)
    print("Demo stopped; bucket emptied. Run terraform destroy to remove resources.")


if __name__ == "__main__":
    main()
