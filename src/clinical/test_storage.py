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
        abs_path = adapter.get_absolute_path(final_path)
        # Should not exist yet, staged
        assert not os.path.exists(abs_path)
        
    # Transaction committed, should exist
    assert os.path.exists(abs_path)
    with adapter.open(final_path, 'rb') as f:
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
            abs_path = adapter.get_absolute_path(final_path)
            assert not os.path.exists(abs_path)
            raise ValueError("Rollback!")
    except ValueError:
        pass
        
    # Transaction rolled back, should not exist
    assert not os.path.exists(abs_path)
    
    # Staged file should also be cleaned up (RollbackCleanup GC)
    staging_dir = os.path.join(str(adapter.base_dir), '.staging')
    if os.path.exists(staging_dir):
        import gc
        gc.collect()
        # Verify it does not leave orphan stages
        assert len(os.listdir(staging_dir)) == 0
