#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
IMAGE_TAG="${1:-hubclock:latest}"

echo "[i] Building Docker image ${IMAGE_TAG}"
docker build -t "${IMAGE_TAG}" "${PROJECT_ROOT}"

cat <<MSG
[i] Docker image ${IMAGE_TAG} built successfully.
Run the container with:
  docker run --rm -p 8000:8000 \\
    -e MYSQL_HOST=your-mysql-host \\
    -e MYSQL_PORT=3306 \\
    -e MYSQL_USER=hubclock \\
    -e MYSQL_PASSWORD=hubclock \\
    -e MYSQL_DATABASE=hubclock \\
    ${IMAGE_TAG}
MSG
