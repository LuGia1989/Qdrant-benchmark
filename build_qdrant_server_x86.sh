#!/bin/bash
docker build --platform linux/amd64 --ulimit nofile=65536:65536 -f Dockerfile.qdrant.x86 -t qdrant-x86:v1.17.0 .
