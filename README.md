# Market Data and Risk Assessment System: Python skeleton

This repository is the Python skeleton for the Market Data and Risk Assessment System. Every module and REST route exists, but no business logic is implemented yet. Each function raises `NotImplementedError`, and each route returns HTTP 501 with this body:

```json
{"error": "not_implemented", "message": "DashboardApi.<method> is not implemented"}
```

The acceptance tests are written against the contracts. Most of them fail until the implementation exists. See "Expected test results" below.

## Repository layout

```
risk-skeleton/
  app/                      Python modules, one per architecture module
    dashboard_api.py        REST routes (FastAPI app: app.dashboard_api:app)
    access_control.py       Authentication and roles
    alert_service.py        Alert lifecycle and streaming
    ...                     (one file per module in architecture.md)
  tests/
    fakes.py                Fake collaborators used by the tests
    test_acceptance.py      Acceptance tests AT-01 to AT-10, AT-12
  spec.md / architecture.md / contracts.md / test_plan.md
  requirements.txt          Runtime dependencies
  requirements-dev.txt      Runtime and test dependencies
  README.md
```

## Requirements

- Python 3.9 or later. The code is written to run on 3.9.
- pip
- A terminal (macOS or Linux shell, or Windows PowerShell or Command Prompt)

## 1. Get the code

```bash
git clone <your-repository-url>
cd risk-skeleton
```

## 2. Create and activate a virtual environment

macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
```

Windows Command Prompt:

```bat
py -3 -m venv .venv
.venv\Scripts\activate.bat
```

Your prompt should now start with `(.venv)`. Keep this terminal open, or activate the environment again in each new terminal.

## 3. Install the dependencies

To run the server only:

```bash
python -m pip install -r requirements.txt
```

To run the server and the tests (recommended):

```bash
python -m pip install -r requirements-dev.txt
```

## 4. Start the application

Run this from the `risk-skeleton` folder, with the virtual environment active:

```bash
python -m uvicorn app.dashboard_api:app --reload --port 8000
```

You should see `Uvicorn running on http://127.0.0.1:8000`.

If the server stops right after starting, check the terminal for a traceback. The most common causes are running the command from the wrong folder, or an environment that is not active.

## 5. Check the server

Leave the server running, and open a second terminal. Activate the environment there too if you need to run Python.

```bash
curl -i http://localhost:8000/health/live
```

Expected: `HTTP/1.1 501 Not Implemented` and the JSON error body shown above. The 501 is correct for this stage.

Interactive API documentation, with every route listed, is at:

```
http://localhost:8000/docs
```

Stop the server with `Ctrl+C`.

## 6. Run the tests

Run this from the `risk-skeleton` folder, with the virtual environment active:

```bash
python -m pytest tests/ -v
```

For a shorter failure output:

```bash
python -m pytest tests/ -v --tb=line
```

Use `python -m pytest` rather than plain `pytest`. The module form makes sure the tests can import the `app` package from this folder.

### Expected test results

At this stage the expected result is:

```
22 failed, 1 skipped
```

Every failure comes from the unimplemented skeleton, not from a test bug:

- 18 tests fail with `NotImplementedError` from the module under test.
- 4 tests fail on a status-code assertion, because the stub returns 501 where the test expects 200 or 401.
- 1 test is skipped on purpose. It checks the dashboard refresh interval, which is UI behavior and out of scope for the REST-only build.

When the implementation is written, these failures should change to real assertion results. Any test that still fails then will show the behavior that is missing.

## Test design notes

- Test names follow the test plan IDs: `test_AT01_...` to `test_AT12_...`. AT-11 is retired because AC-011 was dropped from the plan.
- Collaborators are replaced by fakes in `tests/fakes.py`. The modules under test are the real skeleton modules.
- HTTP status codes come from the proposed error mapping in `contracts.md`, section 3, because the spec does not define them.
- Rejection checks use a helper (`assert_rejected`) that re-raises `NotImplementedError`, so an unimplemented module cannot pass a test as a rejection.

## Configuration

The application reads two environment variables. Both have defaults for local development.

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql://localhost:5432/risk` | Database connection (not used until the store is implemented) |
| `JWT_SIGNING_KEY` | `dev-only-change-me` | Token signing key. Set your own value outside local development. |

Example:

```bash
export JWT_SIGNING_KEY="a-long-random-value"    # macOS or Linux
$env:JWT_SIGNING_KEY = "a-long-random-value"    # Windows PowerShell
```

Do not commit a real signing key to the repository.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `TypeError: unsupported operand type(s) for |` | You are running Python 3.9 with an older copy of the code. Pull the latest version, which uses `Optional[...]`. |
| `Could not import module "app.dashboard_api"` | Run the command from the `risk-skeleton` folder, the one that contains `app/`. |
| `uvicorn: command not found` or `pytest: command not found` | Activate the virtual environment, or use `python -m uvicorn ...` and `python -m pytest ...`. |
| `ModuleNotFoundError: No module named 'httpx'` when running tests | Install the dev requirements: `python -m pip install -r requirements-dev.txt`. |
| `curl` fails with "connection refused" | The server is not running. Start it in another terminal, and keep that terminal open. |
| Port 8000 is already in use | Start on another port, for example `--port 8001`, and use that port in `curl`. |

## Documents

- `spec.md`: requirements (FR, NFR, AC) and the domain model
- `architecture.md`: modules, request flow, and design decisions
- `contracts.md`: module functions, REST routes, and the error mapping
- `test_plan.md`: acceptance cases, limits, and spec gaps
