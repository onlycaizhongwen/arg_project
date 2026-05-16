# MinIO local bucket

The MVP uses `rag-documents` as the default object bucket.

Docker Compose starts MinIO, but bucket creation is intentionally left to the
application or a later bootstrap script so the first skeleton stays simple.

Local console:

```text
http://localhost:9001
```

Default local credentials are defined in `.env.example`.
