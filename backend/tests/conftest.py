import os

os.environ.setdefault("DEMO_CLOCK", "fixed")
os.environ.setdefault("DEMO_OFFLINE", "1")
os.environ["AUTH_ENFORCE"] = "0"
os.environ.pop("ENV", None)

def pytest_addoption(parser):
    parser.addoption("--update-snapshots", action="store_true", default=False,
                     help="перезаписать снимки золотого сценария (только с комментарием в коммите «почему изменились числа»)")
