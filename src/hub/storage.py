from django.core.files.storage import FileSystemStorage

class CommerceStorageEngine(FileSystemStorage):
    """
    Standard commerce storage engine replacing the legacy HIPAA-compliant ComplianceStorageProxy.
    """
    pass
