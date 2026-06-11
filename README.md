# iMedBest

Python dependencies are managed with `uv`.

```bash
uv sync --dev
uv run python src/manage.py check
uv run python src/manage.py runserver
```

## Compliance & BAA Isolation

To comply with HIPAA Business Associate Agreements (BAAs), this application abstracts its storage interface to physically isolate Protected Health Information (PHI) from non-PHI clinical metadata.
- **Entity Tagging:** All clinical entities support a `contains_phi` boolean flag.
- **Storage Routing:** The `ComplianceStorageProxy` acts as the global storage interface. If `contains_phi` is True, files are transparently written to the BAA-bound vault (e.g., `BAA_ROOT`), completely isolated from the standard global storage directory.
- **Audit Logging:** Any file operations (saves, opens) involving PHI-tagged entities automatically generate security audit logs tracking access in real-time.
