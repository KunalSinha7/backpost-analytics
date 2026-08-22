#! /usr/bin/env bash

set -e
set -x

cd backend
uv run python -c "import app.main; import json; print(json.dumps(app.main.app.openapi()))" > ../openapi.json
cd ..
mv openapi.json frontend/
bun run --filter frontend generate-client
if ! grep -q "from '../services'" frontend/src/client/index.ts; then
  printf "\nexport * from '../services';\n" >> frontend/src/client/index.ts
fi
bun run lint
