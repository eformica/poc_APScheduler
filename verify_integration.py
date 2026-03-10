import ast, pathlib, subprocess, sys

base = pathlib.Path("framework")

# 1. Python syntax
print("=== Python syntax ===")
errors = []
files = sorted(base.rglob("*.py"))
for f in files:
    try:
        ast.parse(f.read_text(encoding="utf-8"))
    except SyntaxError as e:
        errors.append((str(f.relative_to(base)), str(e)))
if errors:
    for name, err in errors:
        print("  ERR", name, err)
else:
    print(f"  OK  {len(files)} arquivos sem erros de sintaxe")

# 2. docker-compose.yml YAML parse
print("\n=== docker-compose.yml (YAML parse) ===")
try:
    import yaml
    data = yaml.safe_load((base / "docker-compose.yml").read_text(encoding="utf-8"))
    sched = data["services"]["scheduler"]
    print("  OK  servicos:", list(data["services"].keys()))
    print("  OK  ports   :", sched.get("ports", []))
    print("  OK  volumes :", sched.get("volumes", []))
    print("  OK  depends :", list(sched.get("depends_on", {}).keys()))
    print("  OK  restart :", sched.get("restart"))
except Exception as e:
    print("  ERR", e)

# 3. Integration chain checks
print("\n=== Integracao API <-> Scheduler ===")
checks = [
    ("api/main.py",          "app.state.scheduler = scheduler"),
    ("api/main.py",          "scheduler.start()"),
    ("api/main.py",          "scheduler.shutdown(wait=True)"),
    ("api/dependencies.py",  "request.app.state.scheduler"),
    ("api/routers/jobs.py",  "get_scheduler"),
    ("api/routers/jobs.py",  "TASK_CATALOG"),
    ("scheduler/engine.py",  "BackgroundScheduler"),
    ("scheduler/app.py",     "uvicorn.run"),
    ("scheduler/app.py",     "_create_admin_user"),
    ("scheduler/registry.py","TASK_CATALOG"),
    ("db/models.py",         "class User"),
    ("Dockerfile",           'CMD ["python", "-m", "scheduler.app"]'),
]
all_ok = True
for path, token in checks:
    content = (base / path).read_text(encoding="utf-8")
    ok = token in content
    all_ok = all_ok and ok
    status = "OK " if ok else "ERR"
    print(f"  {status}  [{path}]  '{token}'")

print("\n" + ("Todos os checks passaram!" if all_ok else "ATENCAO: ha checks falhando."))
