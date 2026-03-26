docker build --ulimit nofile=65536:65536 -f /mnt/raid1/dev/qdrant-benchmark/Dockerfile.qdrant -t qdrant-64k:v1.17.0 /mnt/raid1/dev/qdrant-benchmark
