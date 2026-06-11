import logging
import os
import shutil
import tempfile

from django.conf import settings
from django.db import transaction

logger = logging.getLogger(__name__)

try:
    from audit.middleware import get_current_request
    from audit.models import AuditLog
except ImportError:
    get_current_request = None
    AuditLog = None


class RollbackCleanup:
    def __init__(self, temp_path):
        self.temp_path = temp_path
        self.committed = False

    def __del__(self):
        if not self.committed and os.path.exists(self.temp_path):
            try:
                os.remove(self.temp_path)
                logger.debug(f"Rollback cleanup: removed staged file {self.temp_path}")
            except Exception as e:
                logger.error(f"Failed to cleanup staged file {self.temp_path}: {e}")


class UnifiedStorageAdapter:
    """
    A transaction-aware storage adapter that stages file writes in a temporary directory
    and only commits them to their final destination upon successful database transaction commit.
    If the transaction is rolled back, the staged files are automatically cleaned up.
    """

    def __init__(self, base_dir=None):
        if not base_dir:
            root_dir = str(getattr(settings, "ROOT_DIR", tempfile.gettempdir()))
            media_root = getattr(settings, "MEDIA_ROOT", os.path.join(root_dir, "media"))
            base_dir = media_root
        self.base_dir = str(base_dir)
        os.makedirs(self.base_dir, exist_ok=True)

    def save(self, name, content, namespace=""):
        """
        Stages file writing.
        `content` can be bytes, string, or a file-like object.
        Returns the relative path where the file WILL be after commit.
        """
        final_rel_path = os.path.join(namespace, name) if namespace else name
        final_abs_path = os.path.join(self.base_dir, final_rel_path)

        os.makedirs(os.path.dirname(final_abs_path), exist_ok=True)

        # Stage the file in a temp path
        temp_dir = getattr(settings, "FILE_STAGING_DIR", os.path.join(self.base_dir, ".staging"))
        os.makedirs(temp_dir, exist_ok=True)

        temp_fd, temp_path = tempfile.mkstemp(dir=temp_dir, prefix="stage_")
        with os.fdopen(temp_fd, "wb") as f:
            if isinstance(content, str):
                f.write(content.encode("utf-8"))
            elif isinstance(content, bytes):
                f.write(content)
            else:
                shutil.copyfileobj(content, f)

        # Register rollback cleanup
        cleaner = RollbackCleanup(temp_path)

        # Register commit hook
        def on_commit():
            cleaner.committed = True
            try:
                os.rename(temp_path, final_abs_path)
                logger.debug(f"Committed file {final_abs_path}")
            except OSError:
                # Fallback to copy/delete if cross-device or other OS error
                try:
                    shutil.copy2(temp_path, final_abs_path)
                    os.remove(temp_path)
                    logger.debug(f"Committed file {final_abs_path} (via copy)")
                except Exception as inner_e:
                    logger.error(f"Fallback commit failed for {final_abs_path}: {inner_e}")
            except Exception as e:
                logger.error(f"Failed to commit file {final_abs_path}: {e}")

        transaction.on_commit(on_commit)

        return final_rel_path

    def exists(self, path):
        # Support historical absolute paths
        if os.path.isabs(path):
            return os.path.exists(path)
        return os.path.exists(os.path.join(self.base_dir, path))

    def get_absolute_path(self, path):
        if os.path.isabs(path):
            return path
        return os.path.join(self.base_dir, path)

    def open(self, path, mode="rb"):
        full_path = self.get_absolute_path(path)
        return open(full_path, mode)  # noqa: SIM115


class ComplianceStorageProxy:
    def __init__(self, primary_adapter, baa_adapter):
        self.primary_adapter = primary_adapter
        self.baa_adapter = baa_adapter

    @property
    def base_dir(self):
        return self.primary_adapter.base_dir

    def _log_audit(self, action, path):
        logger.info(f"AUDIT LOG: PHI-tagged file operation ({action}) for {path}")
        if AuditLog and get_current_request:
            try:
                request = get_current_request()
                user = getattr(request, "user", None) if request else None
                if user and not user.is_authenticated:
                    user = None

                ip_address = None
                user_agent = None
                if request:
                    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
                    if x_forwarded_for:
                        ip_address = x_forwarded_for.split(",")[0]
                    else:
                        ip_address = request.META.get("REMOTE_ADDR")
                    user_agent = request.META.get("HTTP_USER_AGENT")

                AuditLog.objects.create(
                    action="SECURITY",
                    model_name="ComplianceStorage",
                    object_id=path,
                    changes={"file_operation": action},
                    user=user,
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
            except Exception as e:
                logger.error(f"Failed to create audit log for {path}: {e}")

    def save(self, name, content, namespace="", contains_phi=False):
        if contains_phi:
            self._log_audit("SAVE", os.path.join(namespace, name) if namespace else name)
            return self.baa_adapter.save(name, content, namespace)
        return self.primary_adapter.save(name, content, namespace)

    def exists(self, path, contains_phi=None):
        if contains_phi is True:
            return self.baa_adapter.exists(path)
        if contains_phi is False:
            return self.primary_adapter.exists(path)
        return self.baa_adapter.exists(path) or self.primary_adapter.exists(path)

    def get_absolute_path(self, path, contains_phi=None):
        if contains_phi is True or (contains_phi is None and self.baa_adapter.exists(path)):
            return self.baa_adapter.get_absolute_path(path)
        return self.primary_adapter.get_absolute_path(path)

    def open(self, path, mode="rb", contains_phi=None):
        if contains_phi is True or (contains_phi is None and self.baa_adapter.exists(path)):
            self._log_audit(f"OPEN({mode})", path)
            return self.baa_adapter.open(path, mode)
        return self.primary_adapter.open(path, mode)


root_dir = str(getattr(settings, "ROOT_DIR", tempfile.gettempdir()))
media_root = getattr(settings, "MEDIA_ROOT", os.path.join(root_dir, "media"))
baa_root = getattr(settings, "BAA_ROOT", os.path.join(root_dir, "baa_vault"))

_primary_adapter = UnifiedStorageAdapter(base_dir=media_root)
_baa_adapter = UnifiedStorageAdapter(base_dir=baa_root)

storage_adapter = ComplianceStorageProxy(_primary_adapter, _baa_adapter)

def get_storage_adapter():
    return storage_adapter
