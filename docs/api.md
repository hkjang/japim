# API

## Endpoints

- `GET /health`
- `GET /`
- `POST /api/v1/jobs`
- `GET /api/v1/jobs/{job_id}`
- `GET /api/v1/jobs/{job_id}/download/masked-pdf`
- `GET /api/v1/jobs/{job_id}/download/detections-csv`
- `GET /api/v1/jobs/{job_id}/download/detections-jsonl`
- `GET /api/v1/jobs/{job_id}/download/job-summary`

## Upload example

```bash
curl -F "file=@sample.pdf" http://localhost:8000/api/v1/jobs
```
