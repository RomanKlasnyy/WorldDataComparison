import os
import sys

if "--native" not in sys.argv:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QThreadPool  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from worlddata.config import load_config  # noqa: E402
from worlddata.db import open_repository  # noqa: E402
from worlddata.paths import get_paths  # noqa: E402
from worlddata.ui.context import AppContext  # noqa: E402
from worlddata.ui.main_window import CommandPalette, MainWindow  # noqa: E402
from worlddata.ui.settings import Settings  # noqa: E402
from worlddata.ui.theme import apply_qt_palette, qss, set_current_theme  # noqa: E402

paths = get_paths()
config = load_config(paths)
repo = open_repository(paths)
settings = Settings()
set_current_theme("dark")
app = QApplication(sys.argv)
app.setStyleSheet(qss("dark"))
apply_qt_palette(app, "dark")
ctx = AppContext(paths, config, repo, repo.manifest, settings)
window = MainWindow(ctx)
window.resize(1500, 950)
window.show()
app.processEvents()


def shot(name):
    for _ in range(20):
        app.processEvents()
    window.grab().save(f"data/ui_{name}.png")


for key in ["dashboard", "countries", "rankings", "correlations", "groups", "quality", "about"]:
    window.navigate(key)
    if key == "correlations":
        QThreadPool.globalInstance().waitForDone(120000)
    shot(key)
    print(key, "ok", type(window._pages[key]).__name__)

window.navigate("countries")
countries = window._pages["countries"]
countries.tabs.setCurrentIndex(1)
shot("compare")
countries.tabs.setCurrentIndex(0)

window.navigate("groups")
groups = window._pages["groups"]
groups.tabs.setCurrentIndex(1)
shot("group_tests")
groups.tabs.setCurrentIndex(2)
shot("group_members")
groups.tabs.setCurrentIndex(0)

window.navigate("quality")
quality = window._pages["quality"]
quality.tabs.setCurrentIndex(1)
shot("quality_missing")
quality.tabs.setCurrentIndex(4)
shot("quality_settings")
quality.cutoff.setValue(2020)
quality._apply_settings()
print("cutoff after apply:", ctx.dataset().cutoff)
assert ctx.dataset().cutoff == 2020
quality.cutoff.setValue(2015)
quality._apply_settings()
assert ctx.dataset().cutoff == 2015

window.toggle_theme()
window.navigate("dashboard")
shot("dashboard_light")
window.toggle_theme()

palette = CommandPalette(window)
palette.input.setText("gdp per")
print("palette results:", palette.results.count())
assert palette.results.count() > 0
palette.close()

print("saved screenshots")
repo.close()
