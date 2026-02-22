# Operations Runbook

## Backup / Restore

### Backup

```bash
cd backend
chmod +x scripts/backup_postgres.sh
DATABASE_URL=postgresql://user:pass@host:5432/db ./scripts/backup_postgres.sh
```

Recommended: run hourly during active contest windows and daily otherwise.

### Restore Verification

1. Create an empty restore database.
2. Restore a recent dump:

```bash
cd backend
chmod +x scripts/restore_postgres.sh
./scripts/restore_postgres.sh ./backups/codeclash_YYYYMMDD_HHMMSS.dump localhost postgres code_restore
```

3. Start API against restore DB and call `/health`.
4. Verify leaderboard and submission rows.

## Queue and Worker

- API enqueues submissions with status `queued`.
- Worker transitions: `queued -> running -> completed|failed|timeout`.
- Health endpoint includes worker status and queue depth.

## Monitoring

- Scrape `/metrics` with Prometheus.
- Key metrics:
  - `codeclash_http_requests_total`
  - `codeclash_http_request_duration_seconds`
  - `codeclash_submission_queue_depth`
  - `codeclash_worker_up`

## Load Testing

Use k6:

```bash
k6 run backend/scripts/load_test_contest.js -e BASE_URL=http://localhost:8000/api/v1 -e USERNAME=participant1 -e PASSWORD=participant1@123
```

Target SLO baseline:
- `test-run` p95 < 2s
- queue wait p95 < 5s (at target concurrency)
- API error rate < 1%
