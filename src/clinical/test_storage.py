import os

import pytest
from django.db import transaction

from clinical.storage import get_storage_adapter


@pytest.mark.django_db(transaction=True)
def test_storage_adapter_commit_and_rollback():
    adapter = get_storage_adapter()
    # Test successful commit
    with transaction.atomic():
        final_path = adapter.save("test_commit.txt", b"Hello", namespace="test")
        abs_path = adapter.get_absolute_path(final_path, contains_phi=False)
        # Should not exist yet, staged
        assert not os.path.exists(abs_path)

    # Transaction committed, should exist
    assert os.path.exists(abs_path)
    with adapter.open(final_path, "rb", contains_phi=False) as f:
        assert f.read() == b"Hello"

    # Clean up
    os.remove(abs_path)


@pytest.mark.django_db(transaction=True)
def test_storage_adapter_rollback():
    adapter = get_storage_adapter()
    abs_path = None
    try:
        with transaction.atomic():
            final_path = adapter.save("test_rollback.txt", b"Bad", namespace="test")
            abs_path = adapter.get_absolute_path(final_path, contains_phi=False)
            assert not os.path.exists(abs_path)
            raise ValueError("Rollback!")
    except ValueError:
        pass

    # Transaction rolled back, should not exist
    assert not os.path.exists(abs_path)

    # Staged file should also be cleaned up (RollbackCleanup GC)
    staging_dir = os.path.join(str(adapter.base_dir), ".staging")
    if os.path.exists(staging_dir):
        import gc

        gc.collect()
        # Verify it does not leave orphan stages
        assert len(os.listdir(staging_dir)) == 0


@pytest.mark.django_db(transaction=True)
def test_storage_adapter_compliance_routing():
    adapter = get_storage_adapter()

    with transaction.atomic():
        phi_path = adapter.save("phi_test.txt", b"PHI Data", namespace="phi", contains_phi=True)
        global_path = adapter.save("global_test.txt", b"Non PHI", namespace="global", contains_phi=False)

    phi_abs = adapter.get_absolute_path(phi_path, contains_phi=True)
    global_abs = adapter.get_absolute_path(global_path, contains_phi=False)

    # Assert PHI is NOT in primary
    assert not adapter.primary_adapter.exists(phi_path)
    # Assert PHI IS in BAA
    assert adapter.baa_adapter.exists(phi_path)

    # Assert global IS in primary
    assert adapter.primary_adapter.exists(global_path)
    # Assert global is NOT in BAA
    assert not adapter.baa_adapter.exists(global_path)

    os.remove(phi_abs)
    os.remove(global_abs)
