 OPTIMIZATION for ARM64:
All 4 changes are applied:                                                                                                                                                               
                                                                                                                                                                                           
  ┌─────┬─────────────────────────┬──────────────────────────────────────────────┬─────────────────────────────────────────────────────────────────────────────────┐                       
  │  #  │         Change          │                     File                     │                                      What                                       │                       
  ├─────┼─────────────────────────┼──────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────┤                       
  │ 1   │ target-cpu=native       │ Dockerfile.qdrant:17-18                      │ RUSTFLAGS="-C target-cpu=native" — unlocks full NEON/SVE/LSE for the build host │                       
  ├─────┼─────────────────────────┼──────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────┤                       
  │ 2   │ Custom image in compose │ docker-compose.yaml:3                        │ qdrant-64k:v1.17.0 instead of qdrant/qdrant:latest                              │                       
  ├─────┼─────────────────────────┼──────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────┤                       
  │ 3   │ gRPC everywhere         │ sweep_ef.py:200,282 + qdrant_local.py:80,105 │ prefer_grpc=True on all QdrantClient calls                                      │                       
  ├─────┼─────────────────────────┼──────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────┤                       
  │ 4   │ Batch size 100→500      │ qdrant_local.py:33                           │ QDRANT_BATCH_SIZE = 500 (matches sweep_ef.py)                                   │                     
  └─────┴─────────────────────────┴──────────────────────────────────────────────┴─────────────────────────────────────────────────────────────────────────────────┘                       
                                                                                                                                                                                         
  Note: after rebuilding the Docker image (docker build -f Dockerfile.qdrant -t qdrant-64k:v1.17.0 .), the compose file will pick up both the jemalloc 64KB page fix and the new           
  target-cpu=native optimization.                                                                            


----------------------------------------------
Filtering768D1M1P is not a valid case type. Even with the patch, you need to use the correct case name. The 1% filter cases are:

  ┌────────────────────────┬────────────────────────────────┐                                                                                                                       
  │       Case Type        │          Description           │
  ├────────────────────────┼────────────────────────────────┤                                                                                                                       
  │ Performance768D1M1P    │ 768D, 1M vectors, 1% filter    │                                                                                                                     
  ├────────────────────────┼────────────────────────────────┤                                                                                                                       
  │ Performance1536D500K1P │ 1536D, 500K vectors, 1% filter │                                                                                                                       
  └────────────────────────┴────────────────────────────────┘                                                                                                                       
                                                                                                                                                                                    
  Update your script to use:                                                                                                                                                        
                                                                                                                                                                                  
  docker exec vdbbench vectordbbench QdrantLocal \                                                                                                                                  
      --url http://<NODE2_IP>:6333 \                                                                                                                                              
      --case-type Performance768D1M1P \                                                                                                                                             
      --m 16 --ef-construct 200 --hnsw-ef 128 \                                                                                                                                     
      --num-concurrency 1,10,50,100 \                                                                                                                                               
      --db-label "qdrant-filter-1pct"                                                                                                                                               
                                                                                                                                                                                    
  There is no Filtering prefix — all cases use the Performance prefix with 1P/99P suffix for filter selectivity. 
-----------------------------------
where is the patched file and its contents?                                                                                                                                       
                                              
● The patched file only exists inside the running container. To view it:                                                                                                            
                                                                                                                                                                                  
  docker exec vdbbench cat /usr/local/lib/python3.11/site-packages/vectordb_bench/backend/clients/qdrant_local/qdrant_local.py                                                      
                                                                                                                                                                                    
  To copy it out to your host for safekeeping:                                                                                                                                      
                                                                                                                                                                                    
  docker cp vdbbench:/usr/local/lib/python3.11/site-packages/vectordb_bench/backend/clients/qdrant_local/qdrant_local.py ./qdrant_local_patched.py        
------------------------------------
There's no Filtering case type. The available filter-related cases are:                                                                                                           
                                                                                                                                                                                  
  ┌─────────────────────────────┬───────────────────────────────────────┐                                                                                                           
  │          Case Type          │              Description              │
  ├─────────────────────────────┼───────────────────────────────────────┤                                                                                                           
  │ Performance768D1M1P         │ 768D, 1M vectors, 1% filter match     │                                                                                                         
  ├─────────────────────────────┼───────────────────────────────────────┤
  │ Performance768D1M99P        │ 768D, 1M vectors, 99% filter match    │                                                                                                           
  ├─────────────────────────────┼───────────────────────────────────────┤                                                                                                           
  │ Performance768D10M1P        │ 768D, 10M vectors, 1% filter match    │                                                                                                           
  ├─────────────────────────────┼───────────────────────────────────────┤                                                                                                           
  │ Performance768D10M99P       │ 768D, 10M vectors, 99% filter match   │                                                                                                         
  ├─────────────────────────────┼───────────────────────────────────────┤                                                                                                           
  │ Performance1536D500K1P      │ 1536D, 500K vectors, 1% filter match  │                                                                                                         
  ├─────────────────────────────┼───────────────────────────────────────┤                                                                                                           
  │ Performance1536D500K99P     │ 1536D, 500K vectors, 99% filter match │                                                                                                         
  ├─────────────────────────────┼───────────────────────────────────────┤                                                                                                           
  │ Performance1536D5M1P        │ 1536D, 5M vectors, 1% filter match    │                                                                                                         
  ├─────────────────────────────┼───────────────────────────────────────┤                                                                                                           
  │ Performance1536D5M99P       │ 1536D, 5M vectors, 99% filter match   │                                                                                                         
  ├─────────────────────────────┼───────────────────────────────────────┤                                                                                                           
  │ LabelFilterPerformanceCase  │ Label-based filtering                 │                                                                                                         
  ├─────────────────────────────┼───────────────────────────────────────┤                                                                                                           
  │ NewIntFilterPerformanceCase │ Integer filter                        │                                                                                                         
  └─────────────────────────────┴───────────────────────────────────────┘                                                                                                           
                                                                                                                                                                                  
  The 1P / 99P suffix means the filter selectivity — 1P = highly selective (1% match), 99P = low selectivity (99% match).                                                           
                                                                                                                                                                                  
  Which filter scenario did you want to test?                                                                                    
----------------------------------
Qdrant Benchmark Plan — Two-Node / Docker / 10 Gbps                                                                                                                                                                      
  Prerequisites                                                                                                                                                                                                            
  ┌─────────┬─────────────────────────┬─────────────────────────┐                                                                                                                                                          
  │         │  Node 1 (Bench Client)  │ Node 2 (Qdrant Server)  │                                                                                                                                                        
  ├─────────┼─────────────────────────┼─────────────────────────┤
  │ Role    │ VectorDBBench           │ Qdrant                  │
  ├─────────┼─────────────────────────┼─────────────────────────┤
  │ Docker  │ Docker + Docker Compose │ Docker + Docker Compose │
  ├─────────┼─────────────────────────┼─────────────────────────┤
  │ Network │ 10 Gbps to Node 2       │ 10 Gbps to Node 1       │
  ├─────────┼─────────────────────────┼─────────────────────────┤
  │ Disk    │ Minimal (results only)  │ SSD, 100GB+ free        │
  ├─────────┼─────────────────────────┼─────────────────────────┤
  │ RAM     │ 8GB+                    │ 32GB+ recommended       │
  ├─────────┼─────────────────────────┼─────────────────────────┤
  │ CPU     │ 4+ cores                │ 8+ cores recommended    │
  └─────────┴─────────────────────────┴─────────────────────────┘

  ---
  Step 1 — Validate Network (Both Nodes)

  # Node 2
  docker run -d --rm --name iperf3 -p 5201:5201 networkstatic/iperf3 -s

  # Node 1
  docker run --rm networkstatic/iperf3 -c <NODE2_IP> -t 10
  # Expect: ~9.4 Gbps

  ---
  Step 2 — Deploy Qdrant (Node 2)

  mkdir -p ~/qdrant-benchmark/qdrant-server/qdrant_storage
  cd ~/qdrant-benchmark/qdrant-server

  docker-compose.yml
  services:
    qdrant:
      image: qdrant/qdrant:latest
      container_name: qdrant-server
      ports:
        - "6333:6333"
        - "6334:6334"
      volumes:
        - ./qdrant_storage:/qdrant/storage
      deploy:
        resources:
          limits:
            memory: 32g
      restart: unless-stopped

  docker compose up -d
  curl http://localhost:6333/healthz   # expect {"title":"qdrant..."}

  ---
  Step 3 — Deploy VectorDBBench (Node 1)

  mkdir -p ~/qdrant-benchmark/bench-client/{results,config}
  cd ~/qdrant-benchmark/bench-client

  Dockerfile
  FROM python:3.11-slim
  RUN pip install --no-cache-dir 'vectordb-bench[qdrant]'
  WORKDIR /bench
  VOLUME /bench/results
  ENTRYPOINT ["sleep", "infinity"]

  docker-compose.yml
  services:
    bench:
      build: .
      container_name: vdbbench
      volumes:
        - ./results:/bench/results
        - ./config:/bench/config
      environment:
        - RESULTS_LOCAL_DIR=/bench/results
      restart: unless-stopped

  docker compose up -d --build

  ---
  Step 4 — Verify Connectivity (Node 1 → Node 2)

  docker exec vdbbench python -c "
  from qdrant_client import QdrantClient
  c = QdrantClient(url='http://<NODE2_IP>:6333')
  print(c.get_collections())
  "

  ---
  Step 5 — Run Benchmarks

  Run in this order — smallest to largest, to validate setup before long runs:

  Round 1: Smoke Test (~5 min)

  docker exec vdbbench vectordbbench QdrantLocal \
    --url http://<NODE2_IP>:6333 \
    --case-type Performance1536D50K \
    --m 16 --ef-construct 200 --hnsw-ef 128 \
    --num-concurrency 1,10 \
    --db-label "qdrant-smoke"

  Round 2: Baseline Performance (~15 min)

  docker exec vdbbench vectordbbench QdrantLocal \
    --url http://<NODE2_IP>:6333 \
    --case-type Performance768D1M \
    --m 16 --ef-construct 200 --hnsw-ef 128 \
    --num-concurrency 1,10,50,100 \
    --db-label "qdrant-1M-768d"

  Round 3: High-Dimensional (~15 min)

  docker exec vdbbench vectordbbench QdrantLocal \
    --url http://<NODE2_IP>:6333 \
    --case-type Performance1536D500K \
    --m 16 --ef-construct 200 --hnsw-ef 128 \
    --num-concurrency 1,10,50,100 \
    --db-label "qdrant-500K-1536d"

  Round 4: Filtered Search (~20 min)

  # 1% filter rate
  docker exec vdbbench vectordbbench QdrantLocal \
    --url http://<NODE2_IP>:6333 \
    --case-type Filtering768D1M1P \
    --m 16 --ef-construct 200 --hnsw-ef 128 \
    --num-concurrency 1,10,50,100 \
    --db-label "qdrant-filter-1pct"

  # 99% filter rate
  docker exec vdbbench vectordbbench QdrantLocal \
    --url http://<NODE2_IP>:6333 \
    --case-type Filtering768D1M99P \
    --m 16 --ef-construct 200 --hnsw-ef 128 \
    --num-concurrency 1,10,50,100 \
    --db-label "qdrant-filter-99pct"

  Round 5: Scale Test (~1-2 hours)

  docker exec vdbbench vectordbbench QdrantLocal \
    --url http://<NODE2_IP>:6333 \
    --case-type Performance768D10M \
    --m 16 --ef-construct 200 --hnsw-ef 128 \
    --num-concurrency 1,10,50,100 \
    --db-label "qdrant-10M-768d"

  Round 6: Capacity Test (~30 min)

  docker exec vdbbench vectordbbench QdrantLocal \
    --url http://<NODE2_IP>:6333 \
    --case-type CapacityDim128 \
    --m 16 --ef-construct 200 \
    --db-label "qdrant-capacity-128d"

  ---
  Step 6 — Monitor During Benchmarks (Node 2)

  # Terminal 1: container resource usage
  docker stats qdrant-server

  # Terminal 2: Qdrant telemetry
  watch -n 5 'curl -s http://localhost:6333/telemetry | python3 -m json.tool | head -50'

  ---
  Step 7 — Collect Results (Node 1)

  # Results are in the mounted volume
  ls ~/qdrant-benchmark/bench-client/results/

  # Copy off for analysis
  tar czf qdrant-benchmark-results.tar.gz -C ~/qdrant-benchmark/bench-client results/

  ---
  Summary Timeline

  ┌───────┬───────────────┬───────────────┐
  │ Round │     Case      │ Est. Duration │
  ├───────┼───────────────┼───────────────┤
  │ 1     │ Smoke (50K)   │ ~5 min        │
  ├───────┼───────────────┼───────────────┤
  │ 2     │ 1M / 768d     │ ~15 min       │
  ├───────┼───────────────┼───────────────┤
  │ 3     │ 500K / 1536d  │ ~15 min       │
  ├───────┼───────────────┼───────────────┤
  │ 4     │ Filtered (×2) │ ~40 min       │
  ├───────┼───────────────┼───────────────┤
  │ 5     │ 10M / 768d    │ ~1-2 hrs      │
  ├───────┼───────────────┼───────────────┤
  │ 6     │ Capacity      │ ~30 min       │
  ├───────┼───────────────┼───────────────┤
  │ Total │               │ ~3-4 hours    │
  └───────┴───────────────┴───────────────┘

  ---
  Cleanup (After Benchmarks)

  # Node 1
  cd ~/qdrant-benchmark/bench-client && docker compose down

  # Node 2
  cd ~/qdrant-benchmark/qdrant-server && docker compose down -v

  Want me to create these files in the project directory?

✻ Cooked for 32s                    
