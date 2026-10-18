# FalkorDB Setup & Persistence Guide for SYNQ

This document details the persistent graph memory architecture using FalkorDB for SYNQ.

## 1. Overview
SYNQ uses FalkorDB (a high-performance Redis-based Graph Database engine) to persist knowledge graphs across AI tasks:
- **Node Types**: `Project`, `Task`, `Execution`, `Artifact`, `Decision`.
- **Relationships**: `HAS_TASK`, `DEPENDS_ON`, `EXECUTED_BY`, `PRODUCED`, `MADE_DECISION`.
- **Authoritative Operational Store**: SQLite (`synq.db`) retains transactional task state, user configurations, and provider records.
- **Graph Knowledge Store**: FalkorDB provides continuous knowledge graph persistence and cross-task context package retrieval.

## 2. Docker Compose Configuration
The repository includes a ready-to-run `docker-compose.yml` in the project root:

```yaml
version: "3.9"

services:
  falkordb:
    image: falkordb/falkordb:latest
    container_name: synq-falkordb
    ports:
      - "127.0.0.1:6379:6379"
    volumes:
      - falkordb-data:/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  falkordb-data:
    driver: local
```

### Persistence Guarantee
- The named volume `falkordb-data` maps to `/data` in the container.
- Redis snapshotting (`dump.rdb` / AOF) stores the graph data durably on the host filesystem managed by Docker.
- Graph data survives container stops, restarts, and image updates as long as the volume is retained.

## 3. Operational Procedures

### Starting FalkorDB (Requires User Approval)
To start FalkorDB when you have Docker Desktop running:
```bash
docker compose up -d falkordb
```

Verify health:
```bash
docker compose ps
```

### Verifying Graph Data in FalkorDB
Connect using `redis-cli`:
```bash
docker exec -it synq-falkordb redis-cli GRAPH.QUERY synq_proj_<project_id> "MATCH (n) RETURN n"
```

### Stopping FalkorDB
```bash
docker compose stop falkordb
```

### Backup Procedure
To snapshot and back up graph data:
1. Issue a Redis save:
   ```bash
   docker exec -it synq-falkordb redis-cli SAVE
   ```
2. Copy the database file from the container:
   ```bash
   docker cp synq-falkordb:/data/dump.rdb ./backups/falkordb_backup_$(date +%Y%m%d).rdb
   ```

### Restore Procedure
1. Stop the container:
   ```bash
   docker compose stop falkordb
   ```
2. Copy the backup file into the data directory/container:
   ```bash
   docker cp ./backups/falkordb_backup_<date>.rdb synq-falkordb:/data/dump.rdb
   ```
3. Restart the container:
   ```bash
   docker compose start falkordb
   ```

## 4. Disconnected State & Fallback Policy
- **Production Mode** (`falkordb_allow_in_memory_fallback=False`):
  If FalkorDB is offline, the backend explicitly reports `status: "disconnected"`, pauses graph writes, and preserves all operational data in SQLite. It **never** silently pretends graph writes succeeded in persistent memory.
- **Test Mode** (`falkordb_allow_in_memory_fallback=True`):
  Used strictly in automated pytest test suites, labeled clearly as `in_memory_test`.
