# FastAPI Project - Development

## Docker Compose

* Start the local stack with Docker Compose:

```bash
docker compose watch
```

* Now you can open your browser and interact with these URLs:

Application, with the frontend and API served by FastAPI: <http://localhost:8000>

Automatic interactive documentation with Swagger UI (from the OpenAPI backend): <http://localhost:8000/docs>

Adminer, database web administration: <http://localhost:8080>

Traefik UI, to see how the routes are being handled by the proxy: <http://localhost:8090>

Mailpit, to read the emails sent during local development: <http://localhost:8025>

**Note**: If a rebuild ever leaves `db` or `prestart` in the `Created` state (DB-backed
endpoints return 500 while the backend still reports healthy), run `docker compose up -d`
to start them. This is [docker/compose#13717](https://github.com/docker/compose/issues/13717),
triggered when a file Compose reads for configuration changes while `watch` is running.

**Note**: The first time you start your stack, it might take a minute for it to be ready. While the backend waits for the database to be ready and configures everything. You can check the logs to monitor it.

To check the logs, run (in another terminal):

```bash
docker compose logs
```

To check the logs of a specific service, add the name of the service, e.g.:

```bash
docker compose logs backend
```

## Mailpit

[Mailpit](https://mailpit.axllent.org) captures emails sent during local development instead of delivering them. The local backend connects to it at `localhost:1025`, and the Compose backend connects to the `mailpit` service. Captured emails are available at <http://localhost:8025>.

## Local Development

The Docker Compose files are configured so that each of the services is available in a different port in `localhost`.

The frontend is built into `backend/app/frontend` and served by FastAPI, so the whole application is at `http://localhost:8000`. There is no separate frontend container.

The backend uses the same port that would be used by its local development server, so you could turn off a Docker Compose service and start its local development service, and everything would keep working.

For frontend work, run the Vite development server instead, which has live reload and talks to the backend at `http://localhost:8000`:

```bash
# First time only — create frontend/.env to point at the local backend:
echo "VITE_API_URL=http://localhost:8000" > frontend/.env
bun run dev
```

The Vite development server is at <http://localhost:5173>. This is also the URL that `FRONTEND_HOST` points at by default, so links in emails (such as password recovery) are generated for it. If you are using the Compose stack at `http://localhost:8000` instead, set `FRONTEND_HOST` to match, or those links will not resolve.

Or you could stop the `backend` Docker Compose service:

```bash
docker compose stop backend
```

And then you can run the local development server for the backend:

```bash
cd backend
uv run fastapi dev app/main.py
```

## Docker Compose files and env vars

There is a main `compose.yml` file with all the configurations that apply to the whole stack, it is used automatically by `docker compose`.

And there's also a `compose.override.yml` with overrides for development, for example to mount the source code as a volume. It is used automatically by `docker compose` to apply overrides on top of `compose.yml`.

These Docker Compose files use the `.env` file containing configurations to be injected as environment variables in the containers.

They also use some additional configurations taken from environment variables set in the scripts before calling the `docker compose` command.

After changing variables, make sure you restart the stack:

```bash
docker compose watch
```

## The .env files

Both `.env` files are gitignored and must be created locally before running the app. Example files are provided as starting points:

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env
```

The root `.env` contains all Docker Compose and backend configuration (database credentials, secret key, SMTP, etc.). The `frontend/.env` is only needed when running the frontend outside of Docker — it points the API client at the local backend (`VITE_API_URL=http://localhost:8000`).

Depending on your workflow, you could want to set up environment variables in your CI/CD system instead of committing an `.env` file, and update `compose.yml` to read from those variables directly.

## Pre-commits and code linting

we are using a tool called [prek](https://prek.j178.dev/) (modern alternative to [Pre-commit](https://pre-commit.com/)) for code linting and formatting.

When you install it, it runs right before making a commit in git. This way it ensures that the code is consistent and formatted even before it is committed.

You can find a file `.pre-commit-config.yaml` with configurations at the root of the project.

#### Install prek to run automatically

`prek` is already part of the dependencies of the project.

After having the `prek` tool installed and available, you need to "install" it in the local repository, so that it runs automatically before each commit.

Using `uv`, you could do it with (make sure you are inside `backend` folder):

```bash
❯ uv run prek install -f
prek installed at `../.git/hooks/pre-commit`
```

The `-f` flag forces the installation, in case there was already a `pre-commit` hook previously installed.

Now whenever you try to commit, e.g. with:

```bash
git commit
```

...prek will run and check and format the code you are about to commit, and will ask you to add that code (stage it) with git again before committing.

Then you can `git add` the modified/fixed files again and now you can commit.

#### Running prek hooks manually

you can also run `prek` manually on all the files, you can do it using `uv` with:

```bash
❯ uv run prek run --all-files
check for added large files..............................................Passed
check toml...............................................................Passed
check yaml...............................................................Passed
fix end of files.........................................................Passed
trim trailing whitespace.................................................Passed
ruff.....................................................................Passed
ruff-format..............................................................Passed
biome check..............................................................Passed
```

## URLs

The production or staging URLs would use these same paths, but with your own domain.

### Development URLs

Development URLs, for local development.

Application (frontend and API served by FastAPI): <http://localhost:8000>

Vite development server, when running `bun run dev`: <http://localhost:5173>

Automatic Interactive Docs (Swagger UI): <http://localhost:8000/docs>

Automatic Alternative Docs (ReDoc): <http://localhost:8000/redoc>

Adminer: <http://localhost:8080>

Traefik UI: <http://localhost:8090>

Mailpit: <http://localhost:8025>
