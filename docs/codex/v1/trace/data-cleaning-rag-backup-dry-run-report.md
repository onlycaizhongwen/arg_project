# Data Cleaning RAG Backup Dry Run Report

- Generated at: 2026-05-18T07:15:08.5948163Z
- Compose file: `infra/docker-compose.yml`
- Output dir: `backups/poc`

## PostgreSQL

- Backup file: `backups\poc\rag_cleaning_20260518-151506.sql`
- Size bytes: 1269830
- Status: ok

## MinIO

- Status: ok
- Bucket: `rag-documents`
- Total objects: 238
- Total size: 112 KiB

## Qdrant

- Status: ok

```json
{
    "result":  {
                   "collections":  [
                                       {
                                           "name":  "rag_chunks"
                                       }
                                   ]
               },
    "status":  "ok",
    "time":  5.5E-06
}
```

## Notes

- This script is a non-destructive dry run.
- PostgreSQL restore must be performed in an isolated environment before production use.
- MinIO and Qdrant production backup should use customer-approved object storage snapshots or Qdrant snapshots.
