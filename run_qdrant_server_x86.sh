#!/bin/bash
docker run -d --name qdrant-server-x86 -p 6333:6333 -p 6334:6334 -v ./qdrant_storage:/qdrant/storage qdrant-x86:v1.17.0
