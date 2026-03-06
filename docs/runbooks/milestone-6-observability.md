# Milestone 6 Observability Runbook

## Purpose
This document provides operators with guidance on observing CodeKnowl indexing throughput, failures, and job lag using the Loki + Prometheus/Grafana observability stack.

## Components

### 1. Metrics Export (Prometheus)
- **Endpoint**: `/metrics`
- **Format**: Prometheus text format
- **Key Metrics**:
  - `codeknowl_http_requests_total` - HTTP request volume by method, endpoint, status
  - `codeknowl_index_operations_total` - Indexing operations by status
  - `codeknowl_index_duration_seconds` - Indexing duration histogram
  - `codeknowl_update_operations_total` - Update operations by status
  - `codeknowl_update_duration_seconds` - Update duration histogram
  - `codeknowl_jobs_queued_total` - Jobs submitted to queue by type
  - `codeknowl_jobs_completed_total` - Job completions by type and status
  - `codeknowl_qa_requests_total` - QA requests by type and status

### 2. Structured Logging (Loki)
- **Format**: JSON with timestamp, level, and structured fields
- **Key Fields**:
  - `timestamp` - ISO 8601 timestamp
  - `level` - Log level (INFO, WARNING, ERROR)
  - `logger` - Logger name
  - `message` - Log message
  - `module` - Python module
  - `function` - Function name
  - `line` - Line number
  - `audit` - Audit event context (when present)

### 3. Health Endpoint
- **Endpoint**: `/health`
- **Purpose**: Basic health check for load balancers
- **Response**: JSON with status and system details

## Monitoring Dashboards

### 1. Indexing Throughput
**Prometheus Queries**:
```promql
# Indexing operations per minute
rate(codeknowl_index_operations_total[1m])

# Indexing success rate
rate(codeknowl_index_operations_total{status="succeeded"}[1m]) / 
rate(codeknowl_index_operations_total[1m])

# Average indexing duration
histogram_quantile(0.95, rate(codeknowl_index_duration_seconds_bucket[5m]))
```

### 2. Job Queue Health
**Prometheus Queries**:
```promql
# Jobs queued vs completed
rate(codeknowl_jobs_queued_total[1m])
rate(codeknowl_jobs_completed_total[1m])

# Job failure rate
rate(codeknowl_jobs_completed_total{status="failed"}[1m]) / 
rate(codeknowl_jobs_completed_total[1m])

# Job queue lag (approximate)
increase(codeknowl_jobs_queued_total[1m]) - increase(codeknowl_jobs_completed_total[1m])
```

### 3. HTTP Performance
**Prometheus Queries**:
```promql
# HTTP request rate by endpoint
rate(codeknowl_http_requests_total[1m])

# HTTP error rate
rate(codeknowl_http_requests_total{status!~"2.."}[1m]) / 
rate(codeknowl_http_requests_total[1m])

# 95th percentile response time
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
```

## Log Analysis (Loki)

### 1. Error Detection
**LogQL Queries**:
```logql
{level="ERROR"} |= "Error" |="Exception" |="Failed"

# Recent indexing errors
{level="ERROR"} |= "index" |="Index"

# Authentication failures
{audit="http.unauthorized"}
```

### 2. Performance Analysis
**LogQL Queries**:
```logql
# Slow indexing operations
{level="INFO"} |= "index" |="completed" |="duration" |="seconds" > 300

# High volume requests
{level="INFO"} |= "HTTP" |="request" |="POST" |="index"
```

## Alerting Rules

### 1. Critical Alerts
- **Indexing failure rate > 10%** for 5 minutes
- **Job queue lag > 100 jobs** for 10 minutes
- **HTTP error rate > 5%** for 5 minutes
- **Health endpoint down** for 1 minute

### 2. Warning Alerts
- **Indexing duration > 10 minutes** (95th percentile)
- **Job queue lag > 50 jobs** for 10 minutes
- **HTTP error rate > 2%** for 5 minutes

## Troubleshooting

### 1. High Job Queue Lag
**Symptoms**: Jobs queued faster than completed
**Checks**:
1. Check worker logs for errors
2. Verify Redis connectivity
3. Monitor system resources (CPU, memory)
4. Check for long-running jobs

### 2. Indexing Failures
**Symptoms**: High indexing error rate
**Checks**:
1. Review error logs for specific failure reasons
2. Verify repository accessibility
3. Check available disk space
4. Validate repository state

### 3. HTTP Errors
**Symptoms**: High HTTP error rate
**Checks**:
1. Review specific endpoint error logs
2. Check authentication/authorization issues
3. Verify request payload format
4. Monitor upstream dependencies

## Grafana Dashboard Configuration

### Dashboard Variables
- `instance`: CodeKnowl instance name
- `job_type`: Filter by job type (index, update)

### Panel Configuration
1. **Indexing Throughput**: Time series graph of indexing operations
2. **Job Queue Health**: Stacked area chart of queued vs completed jobs
3. **Error Rate**: Single stat panel showing error percentage
4. **Recent Errors**: Log panel showing recent error messages
5. **Response Times**: Heatmap of response times by endpoint

## Maintenance

### Daily Checks
- Review indexing success rate
- Check job queue backlog
- Monitor system resource usage
- Verify log volume and retention

### Weekly Checks
- Review alerting thresholds
- Update dashboard configurations
- Check log retention policies
- Validate metric collection health

### Monthly Checks
- Review performance trends
- Update capacity planning
- Review alerting effectiveness
- Check observability stack version compatibility
