import pathlib, re

base = pathlib.Path("framework")

checks = [
    ("scheduler/registry.py",      "in_catalog: bool = True"),
    ("scheduler/registry.py",      "trigger: Any = None"),
    ("scheduler/registry.py",      "TASK_CATALOG: dict"),
    ("scheduler/registry.py",      "CATALOG_METADATA"),
    ("scheduler/registry.py",      "API_ONLY_JOB_IDS"),
    ("scheduler/registry.py",      "_API_ONLY_TRIGGER"),
    ("scheduler/registry.py",      "next_run_time.*None"),
    ("container_runner/config.py", "trigger: Optional"),
    ("container_runner/config.py", "in_catalog: bool"),
    ("container_runner/config.py", "next_run_time.*None"),
    ("listeners/execution_logger.py", "API_ONLY_JOB_IDS"),
    ("listeners/execution_logger.py", "EVENT_JOB_EXECUTED"),
    ("listeners/execution_logger.py", "pause_job"),
    ("api/schemas/jobs.py",        "trigger: Optional\\[TriggerConfig\\] = None"),
    ("api/schemas/jobs.py",        "api_only: bool = False"),
    ("api/routers/jobs.py",        "API_ONLY_JOB_IDS"),
    ("api/routers/jobs.py",        "CATALOG_METADATA"),
    ("api/routers/jobs.py",        "api_only="),
    ("api/routers/jobs.py",        "trigger is None"),
    ("api/routers/jobs.py",        "IntervalTrigger.days=36500."),
]

all_ok = True
for path, pattern in checks:
    content = (base / path).read_text(encoding="utf-8")
    ok = bool(re.search(pattern, content))
    all_ok = all_ok and ok
    print(("  OK " if ok else "  ERR") + f"  [{path}]  {pattern!r}")

print()
print("Todos os checks passaram!" if all_ok else "ATENCAO: ha falhas.")
