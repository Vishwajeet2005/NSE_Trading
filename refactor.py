import os
import re

directories = ["backend", "legacy", "tests"]
files_to_process = ["main.py"]

for root_dir in directories:
    for dirpath, _, filenames in os.walk(root_dir):
        for f in filenames:
            if f.endswith(".py"):
                files_to_process.append(os.path.join(dirpath, f))

replacements = [
    (r'\bfrom api import', r'from backend.api.routes import'),
    (r'^import api\b', r'from backend.api import routes as api'),
    (r'\bfrom settings import', r'from backend.core.settings import'),
    (r'^import settings\b', r'from backend.core import settings'),
    (r'\bfrom database import', r'from backend.core.database import'),
    (r'^import database\b', r'from backend.core import database'),
    (r'\bfrom logger import', r'from backend.core.logger import'),
    (r'^import logger\b', r'from backend.core import logger'),
    (r'\bfrom notification import', r'from backend.core.notification import'),
    (r'^import notification\b', r'from backend.core import notification'),
    (r'\bfrom data_ingestion import', r'from backend.engine.data import'),
    (r'^import data_ingestion\b', r'from backend.engine import data as data_ingestion'),
    (r'\bfrom strategy_engine import', r'from backend.engine.strategy import'),
    (r'^import strategy_engine\b', r'from backend.engine import strategy as strategy_engine'),
    (r'\bfrom risk_management import', r'from backend.engine.risk import'),
    (r'^import risk_management\b', r'from backend.engine import risk as risk_management'),
    (r'\bfrom execution_bridge import', r'from backend.execution.bridge import'),
    (r'^import execution_bridge\b', r'from backend.execution import bridge as execution_bridge'),
    (r'\bfrom scanner import', r'from backend.modes.scanner import'),
    (r'^import scanner\b', r'from backend.modes import scanner'),
    (r'\bfrom screener import', r'from backend.modes.screener import'),
    (r'^import screener\b', r'from backend.modes import screener'),
    (r'\bfrom backtest import', r'from backend.modes.backtest import'),
    (r'^import backtest\b', r'from backend.modes import backtest'),
    (r'\bfrom portfolio import', r'from backend.modes.portfolio import'),
    (r'^import portfolio\b', r'from backend.modes import portfolio'),
]

for filepath in files_to_process:
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    new_content = content
    for pattern, repl in replacements:
        new_content = re.sub(pattern, repl, new_content, flags=re.MULTILINE)
        
    if new_content != content:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Updated {filepath}")
