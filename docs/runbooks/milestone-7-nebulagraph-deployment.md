# Milestone 7: NebulaGraph Deployment and Operations Runbook

## Purpose
This document provides operational guidance for deploying and maintaining NebulaGraph for CodeKnowl's relationship store (Milestone 7).

## Architecture Overview

### Components
- **NebulaGraph Cluster**: Graph database for storing code relationships
- **CodeKnowl Backend**: Application that ingests and queries the graph
- **Redis**: Job queue for async indexing operations
- **Optional**: Monitoring stack (Prometheus + Grafana)

## Deployment

### Prerequisites
- Docker or Kubernetes cluster
- Minimum 4GB RAM per NebulaGraph service
- Persistent storage for graph data
- Network connectivity between components

### Option 1: Docker Compose (Development)

```yaml
version: '3.8'
services:
  nebula-metad:
    image: vesoft/nebula-metad:v3.8.0
    environment:
      USER: root
    command:
      - --meta_server_addrs=nebula-metad:9559
      - --local_ip=nebula-metad
      - --ws_ip=nebula-metad
    healthcheck:
      test: ["CMD", "curl", "-f", "http://nebula-metad:19559/status"]
      interval: 30s
      timeout: 10s
      retries: 3
    ports:
      - "9559:9559"
      - "19559:19559"
      - "19659:19659"
    volumes:
      - ./nebula-data/meta:/data/meta
    networks:
      - codeknowl-network

  nebula-storaged:
    image: vesoft/nebula-storaged:v3.8.0
    environment:
      USER: root
    command:
      - --meta_server_addrs=nebula-metad:9559
      - --local_ip=nebula-storaged
      - --ws_ip=nebula-storaged
      - --port=9779
      - --ws_http_port=9778
    healthcheck:
      test: ["CMD", "curl", "-f", "http://nebula-storaged:19779/status"]
      interval: 30s
      timeout: 10s
      retries: 3
    ports:
      - "9779:9779"
      - "9778:9778"
      - "19779:19779"
      - "19778:19778"
    volumes:
      - ./nebula-data/storage:/data/storage
    depends_on:
      - nebula-metad
    networks:
      - codeknowl-network

  nebula-graphd:
    image: vesoft/nebula-graphd:v3.8.0
    environment:
      USER: root
    command:
      - --meta_server_addrs=nebula-metad:9559
      - --local_ip=nebula-graphd
      - --ws_ip=nebula-graphd
    healthcheck:
      test: ["CMD", "curl", "-f", "http://nebula-graphd:19669/status"]
      interval: 30s
      timeout: 10s
      retries: 3
    ports:
      - "9669:9669"
      - "19669:19669"
    depends_on:
      - nebula-metad
      - nebula-storaged
    networks:
      - codeknowl-network

  codeknowl-backend:
    build: ../backend
    environment:
      CODEKNOWL_NEBULA_HOSTS: "nebula-graphd"
      CODEKNOWL_NEBULA_PORT: "9669"
      CODEKNOWL_NEBULA_USERNAME: "root"
      CODEKNOWL_NEBULA_PASSWORD: "nebula"
      CODEKNOWL_NEBULA_SPACE: "codeknowl"
    depends_on:
      - nebula-graphd
    networks:
      - codeknowl-network

networks:
  codeknowl-network:
    driver: bridge

volumes:
  nebula-data/meta:
  nebula-data/storage:
```

### Option 2: Kubernetes (Production)

#### Namespace and Storage
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: codeknowl
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: nebula-meta-pvc
  namespace: codeknowl
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: nebula-storage-pvc
  namespace: codeknowl
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 100Gi
```

#### NebulaGraph Services
```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: nebula-metad
  namespace: codeknowl
spec:
  serviceName: nebula-metad
  replicas: 1
  selector:
    matchLabels:
      app: nebula-metad
  template:
    metadata:
      labels:
        app: nebula-metad
    spec:
      containers:
      - name: nebula-metad
        image: vesoft/nebula-metad:v3.8.0
        ports:
        - containerPort: 9559
        - containerPort: 19559
        - containerPort: 19659
        env:
        - name: USER
          value: "root"
        command:
        - --meta_server_addrs=nebula-metad:9559
        - --local_ip=$(POD_NAME).nebula-metad.codeknowl.svc.cluster.local
        - --ws_ip=$(POD_NAME).nebula-metad.codeknowl.svc.cluster.local
        volumeMounts:
        - name: meta-storage
          mountPath: /data/meta
  volumeClaimTemplates:
  - metadata:
      name: meta-storage
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 10Gi
---
apiVersion: v1
kind: Service
metadata:
  name: nebula-metad
  namespace: codeknowl
spec:
  selector:
    app: nebula-metad
  ports:
  - name: meta
    port: 9559
    targetPort: 9559
  - name: meta-http
    port: 19559
    targetPort: 19559
  - name: meta-ws
    port: 19659
    targetPort: 19659
```

## Configuration

### Environment Variables
```bash
# NebulaGraph Connection
CODEKNOWL_NEBULA_HOSTS="nebula-graphd:9669"
CODEKNOWL_NEBULA_PORT="9669"
CODEKNOWL_NEBULA_USERNAME="root"
CODEKNOWL_NEBULA_PASSWORD="nebula"
CODEKNOWL_NEBULA_SPACE="codeknowl"

# Optional: Multiple hosts for HA
CODEKNOWL_NEBULA_HOSTS="nebula-graphd-1:9669,nebula-graphd-2:9669,nebula-graphd-3:9669"
```

### Graph Space Initialization
The CodeKnowl backend automatically initializes the graph space and schema on first run. Manual initialization:

```bash
# Connect to NebulaGraph console
docker exec -it codeknowl-nebula-graphd-1 /usr/local/bin/nebula-console -addr nebula-graphd-1:9669 -u root -p nebula

# Create space (if needed)
CREATE SPACE codeknowl (partition_num=10, replica_factor=1);
USE codeknowl;

# Verify schema
SHOW TAGS;
SHOW EDGES;
```

## Operations

### Health Checks
```bash
# Check NebulaGraph services
curl http://localhost:19669/status

# Check CodeKnowl backend
curl http://localhost:8000/health

# Check graph connectivity
curl http://localhost:8000/metrics | grep graph
```

### Backup and Restore

#### Backup
```bash
# Method 1: NebulaGraph snapshot
docker exec nebula-graphd-1 /usr/local/bin/nebula-snapshot create -s codeknowl

# Method 2: Volume backup
kubectl exec -it nebula-metad-0 -- tar czf /tmp/meta-backup.tar.gz /data/meta
kubectl exec -it nebula-storaged-0 -- tar czf /tmp/storage-backup.tar.gz /data/storage
```

#### Restore
```bash
# Stop services
kubectl scale statefulset nebula-graphd --replicas=0
kubectl scale statefulset nebula-storaged --replicas=0
kubectl scale statefulset nebula-metad --replicas=0

# Restore data
kubectl exec -i nebula-metad-0 -- tar xzf /tmp/meta-backup.tar.gz -C /
kubectl exec -i nebula-storaged-0 -- tar xzf /tmp/storage-backup.tar.gz -C /

# Start services
kubectl scale statefulset nebula-metad --replicas=1
kubectl scale statefulset nebula-storaged --replicas=1
kubectl scale statefulset nebula-graphd --replicas=1
```

### Scaling

#### Horizontal Scaling
```yaml
# Increase graphd replicas
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: nebula-graphd
spec:
  replicas: 3  # Increase for read scalability
```

#### Vertical Scaling
```yaml
# Increase resources
resources:
  requests:
    memory: "8Gi"
    cpu: "2"
  limits:
    memory: "16Gi"
    cpu: "4"
```

### Monitoring

#### Prometheus Metrics
```yaml
# Prometheus configuration
scrape_configs:
  - job_name: 'nebula-graph'
    static_configs:
      - targets: ['nebula-graphd:19669']
    metrics_path: /stats
    scrape_interval: 15s
```

#### Key Metrics
- `nebula_graphd_qps` - Queries per second
- `nebula_graphd_latency` - Query latency
- `nebula_graphd_connections` - Active connections
- `nebula_graphd_storage` - Disk usage

### Troubleshooting

#### Common Issues

**Connection Refused**
```bash
# Check if services are running
kubectl get pods -n codeknowl

# Check service endpoints
kubectl get svc -n codeknowl

# Test connectivity
telnet nebula-graphd 9669
```

**Schema Not Found**
```bash
# Check if space exists
nebula-console -addr localhost:9669 -u root -p nebula
> SHOW SPACES;

# Re-initialize if needed
> CREATE SPACE codeknowl;
```

**Performance Issues**
```bash
# Check resource usage
kubectl top pods -n codeknowl

# Check graph statistics
nebula-console -addr localhost:9669 -u root -p nebula
USE codeknowl;
> SHOW STATS;
```

#### Log Analysis
```bash
# NebulaGraph logs
kubectl logs nebula-graphd-0 -n codeknowl

# CodeKnowl backend logs
kubectl logs codeknowl-backend-xxx -n codeknowl

# Search for errors
kubectl logs nebula-graphd-0 -n codeknowl | grep ERROR
```

## Security

### Authentication
- Change default password: `nebula-console -addr localhost:9669 -u root -p nebula`
- Create dedicated user: `CREATE USER codeknowl WITH PASSWORD 'secure_password';`
- Grant permissions: `GRANT ROLE ADMIN ON SPACE codeknowl TO codeknowl;`

### Network Security
- Use TLS for production deployments
- Restrict access to NebulaGraph ports
- Implement network policies in Kubernetes

### Data Encryption
- Enable encryption at rest for persistent volumes
- Use TLS for client connections
- Consider field-level encryption for sensitive data

## Maintenance

### Regular Tasks
- **Daily**: Check health metrics and log errors
- **Weekly**: Review storage usage and performance
- **Monthly**: Apply security patches and updates
- **Quarterly**: Review scaling needs and capacity planning

### Maintenance Windows
- Schedule during low-usage periods
- Communicate maintenance to users
- Have rollback procedures ready

### Version Upgrades
1. Backup data
2. Stop CodeKnowl backend
3. Upgrade NebulaGraph services
4. Verify connectivity
5. Start CodeKnowl backend
6. Validate functionality

## Disaster Recovery

### Failure Scenarios

**Single Node Failure**
- Automatic failover to remaining nodes
- Monitor degraded performance
- Replace failed node

**Cluster Failure**
- Restore from latest backup
- Verify data integrity
- Restart services

**Data Corruption**
- Identify corrupted data
- Restore from clean backup
- Re-index affected repositories

### Recovery Procedures
1. Assess impact and scope
2. Isolate affected components
3. Restore from backups
4. Validate data integrity
5. Resume normal operations
6. Document incident and improvements

## Performance Tuning

### Graph Schema Optimization
- Use appropriate vertex/edge types
- Add indexes for frequently queried properties
- Monitor query performance

### Query Optimization
- Use LIMIT for large result sets
- Optimize traversal depth
- Cache frequently accessed data

### Resource Optimization
- Monitor memory usage
- Tune connection pool sizes
- Optimize batch processing

## Integration Testing

### Connectivity Tests
```bash
# Test NebulaGraph connection
python -c "
from codeknowl.graph_store import create_graph_store
store = create_graph_store()
print('Connection successful')
"
```

### End-to-End Tests
```bash
# Test repository ingestion
curl -X POST http://localhost:8000/repos \
  -H "Content-Type: application/json" \
  -d '{"local_path": "/path/to/repo", "accepted_branch": "main"}'

# Test relationship queries
curl http://localhost:8000/repos/{repo_id}/relationships
```

This runbook provides comprehensive operational guidance for NebulaGraph deployment and maintenance as required by ITD-05 and the Definition of Done.
