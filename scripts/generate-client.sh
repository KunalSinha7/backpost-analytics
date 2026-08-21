#! /usr/bin/env bash

set -e
set -x

cd backend
uv run python -c "import app.main; import json; print(json.dumps(app.main.app.openapi()))" > ../openapi.json
cd ..
mv openapi.json frontend/
bun run --filter frontend generate-client
if [ -f frontend/src/client/core/bodySerializer.ts ]; then
  python3 -c "p='frontend/src/client/core/bodySerializer.ts'; s=open(p).read().replace('JSON.stringify(body, (key, value)', 'JSON.stringify(body, (_key, value)'); open(p,'w').write(s)"
fi
printf "\nexport * from '../services';\n" >> frontend/src/client/index.ts
bun run lint
