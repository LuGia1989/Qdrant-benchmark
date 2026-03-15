Both scripts are ready. The files are mounted into the container at /bench/. Here's how to run them:

  Step 1 — Run the ef sweep (loads data once, then sweeps all ef values):                                                                                                           
  docker exec vdbbench python3 /bench/sweep_ef.py \
      --url http://10.80.120.102:6333 \                                                                                                                                             
      --dataset 1536d500k \                                                                                                                                                         
      --ef-values 16,32,64,128,256,512 \                                                                                                                                            
      --concurrency 1,10,50,100 \                                                                                                                                                   
      --m 16 --ef-construct 200                                                                                                                                                     
                                                                                                                                                                                    
  Step 2 — Generate plots:                                                                                                                                                          
  docker exec vdbbench python3 /bench/plot_sweep.py                                                                                                                                 
                                                                                                                                                                                    
  Step 3 — Copy plots to host:                                                                                                                                                      
  docker cp vdbbench:/bench/results/qps_vs_recall_pareto.png ./results/                                                                                                             
  docker cp vdbbench:/bench/results/latency_vs_recall.png ./results/                                                                                                                
  docker cp vdbbench:/bench/results/ef_impact.png ./results/                                                                                                                        
                                                                                                                                                                                    
  The sweep will:                                                                                                                                                                   
  1. Load 500K vectors once (~30-50 min)                                                                                                                                            
  2. Wait for HNSW index to build                                                                                                                                                   
  3. For each ef value (16→512): run serial search (recall + latency) then concurrent search (QPS)                                                                                  
  4. Output a summary table and save JSON results                                                                                                                                   
                                                                                                                                                                                    
  If you already have data loaded from a previous run, add --skip-load to skip straight to the search sweep.          
