docker run -d --name qdrant-server -p 6333:6333 -p 6334:6334 -v /mnt/qdrant-benchmark/qdrant_storage:/qdrant/storage qdrant-64k:v1.17.0
