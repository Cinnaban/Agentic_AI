(.venv) bunnyhouse_mastercontrol@BunnyHouse-MasterControls-Mac-mini Agentic_AI % cd ~/Agentic_AI

python - <<'PY'
from configs.config import Config

for name in dir(Config):
    if any(
        term in name.upper()
        for term in [
            "STORAGE",
            "DIRECTORY",
            "JOB",
            "COMPLETED",
            "FAILED",
            "PENDING",
        ]
    ):
        print(
            name,
            "=",
            getattr(Config, name)
        )
PY
COMPLETED_JOB_RETENTION_DAYS = 30
DATA_DIRECTORY = ./data
ENABLE_STORAGE_CLEANUP = True
FAILED_JOB_RETENTION_DAYS = 30
JOB_ARCHIVE_DIRECTORY = /Volumes/AIProjects/hermes/archive
JOB_COMPLETED_DIRECTORY = /Volumes/AIProjects/hermes/completed
JOB_FAILED_DIRECTORY = /Volumes/AIProjects/hermes/failed
JOB_INCOMING_DIRECTORY = /Volumes/AIProjects/hermes/incoming
JOB_PROCESSING_DIRECTORY = /Volumes/AIProjects/hermes/processing
JOB_TEMP_DIRECTORY = /Volumes/AIProjects/hermes/temp
LOG_DIRECTORY = /Volumes/AIProjects/hermes/completed
RESULTS_DIRECTORY = ./results
SHARED_STORAGE_DIRECTORY = /Volumes/AIProjects/hermes
(.venv) bunnyhouse_mastercontrol@BunnyHouse-MasterControls-Mac-mini Agentic_AI % launchctl bootout \
gui/$(id -u) \
~/Library/LaunchAgents/com.bunnyhouse.stockagent.telegram.plist \
2>/dev/null || true
(.venv) bunnyhouse_mastercontrol@BunnyHouse-MasterControls-Mac-mini Agentic_AI % : > ~/Agentic_AI/logs/telegram_launchd.log
: > ~/Agentic_AI/logs/telegram_launchd_error.log
(.venv) bunnyhouse_mastercontrol@BunnyHouse-MasterControls-Mac-mini Agentic_AI % launchctl bootstrap \
gui/$(id -u) \
~/Library/LaunchAgents/com.bunnyhouse.stockagent.telegram.plist
(.venv) bunnyhouse_mastercontrol@BunnyHouse-MasterControls-Mac-mini Agentic_AI % cat ~/Agentic_AI/logs/telegram_launchd.log
========================================
TELEGRAM STOCK AGENT
START: Sun Sep 27 08:22:43 PDT 2026
PWD: /Users/bunnyhouse_mastercontrol/Agentic_AI
GIT: 6a824bb32a62843837193412e5d3d81500e7356d
PYTHON: /Users/bunnyhouse_mastercontrol/.venv/bin/python
========================================
========================================
LAUNCHD STORAGE CHECK
========================================
CHECK: /Volumes/AIProjects/hermes
touch: /Volumes/AIProjects/hermes/.telegram_launchd_write_test: Operation not permitted
WRITE: FAILED
CHECK: /Volumes/AIProjects/hermes/incoming
touch: /Volumes/AIProjects/hermes/incoming/.telegram_launchd_write_test: Operation not permitted
WRITE: FAILED
CHECK: /Volumes/AIProjects/hermes/processing
touch: /Volumes/AIProjects/hermes/processing/.telegram_launchd_write_test: Operation not permitted
WRITE: FAILED
CHECK: /Volumes/AIProjects/hermes/completed
touch: /Volumes/AIProjects/hermes/completed/.telegram_launchd_write_test: Operation not permitted
WRITE: FAILED
CHECK: /Volumes/AIProjects/hermes/failed
touch: /Volumes/AIProjects/hermes/failed/.telegram_launchd_write_test: Operation not permitted
WRITE: FAILED
CHECK: /Volumes/AIProjects/hermes/temp
touch: /Volumes/AIProjects/hermes/temp/.telegram_launchd_write_test: Operation not permitted
WRITE: FAILED
========================================
(.venv) bunnyhouse_mastercontrol@BunnyHouse-MasterControls-Mac-mini Agentic_AI % mkdir -p ~/Agentic_AI/runtime/hermes/incoming
mkdir -p ~/Agentic_AI/runtime/hermes/processing
mkdir -p ~/Agentic_AI/runtime/hermes/completed
mkdir -p ~/Agentic_AI/runtime/hermes/failed
mkdir -p ~/Agentic_AI/runtime/hermes/archive
mkdir -p ~/Agentic_AI/runtime/hermes/temp
(.venv) bunnyhouse_mastercontrol@BunnyHouse-MasterControls-Mac-mini Agentic_AI % find ~/Agentic_AI/runtime/hermes \
-maxdepth 1 \
-type d \
-print
/Users/bunnyhouse_mastercontrol/Agentic_AI/runtime/hermes
/Users/bunnyhouse_mastercontrol/Agentic_AI/runtime/hermes/completed
/Users/bunnyhouse_mastercontrol/Agentic_AI/runtime/hermes/temp
/Users/bunnyhouse_mastercontrol/Agentic_AI/runtime/hermes/archive
/Users/bunnyhouse_mastercontrol/Agentic_AI/runtime/hermes/processing
/Users/bunnyhouse_mastercontrol/Agentic_AI/runtime/hermes/failed
/Users/bunnyhouse_mastercontrol/Agentic_AI/runtime/hermes/incoming
(.venv) bunnyhouse_mastercontrol@BunnyHouse-MasterControls-Mac-mini Agentic_AI % python tests/test_amzn_route_trace.py
/Users/bunnyhouse_mastercontrol/.venv/lib/python3.9/site-packages/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl' module is compiled with 'LibreSSL 2.8.3'. See: https://github.com/urllib3/urllib3/issues/3020
  warnings.warn(
Traceback (most recent call last):
  File "/Users/bunnyhouse_mastercontrol/Agentic_AI/tests/test_amzn_route_trace.py", line 8, in <module>
    from orchestrator.hermes import Hermes
  File "/Users/bunnyhouse_mastercontrol/Agentic_AI/orchestrator/hermes.py", line 10, in <module>
    from agents.company_detection_agent import (CompanyDetectionAgent)
  File "/Users/bunnyhouse_mastercontrol/Agentic_AI/agents/company_detection_agent.py", line 4, in <module>
    from agents.ollama_client import OllamaClient
  File "/Users/bunnyhouse_mastercontrol/Agentic_AI/agents/ollama_client.py", line 10, in <module>
    from configs.config import Config
  File "/Users/bunnyhouse_mastercontrol/Agentic_AI/configs/config.py", line 3, in <module>
    class Config:
  File "/Users/bunnyhouse_mastercontrol/Agentic_AI/configs/config.py", line 92, in Config
    ROOT_DIR
NameError: name 'ROOT_DIR' is not defined
(.venv) bunnyhouse_mastercontrol@BunnyHouse-MasterControls-Mac-mini Agentic_AI % cd ~/Agentic_AI

python - <<'PY'
from configs.config import Config

paths = [
    Config.SHARED_STORAGE_DIRECTORY,
    Config.JOB_INCOMING_DIRECTORY,
    Config.JOB_PROCESSING_DIRECTORY,
    Config.JOB_COMPLETED_DIRECTORY,
    Config.JOB_FAILED_DIRECTORY,
    Config.JOB_ARCHIVE_DIRECTORY,
    Config.JOB_TEMP_DIRECTORY,
]

for path in paths:
    print(
        path,
        "exists:",
        path.exists()
    )
PY
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File "/Users/bunnyhouse_mastercontrol/Agentic_AI/configs/config.py", line 3, in <module>
    class Config:
  File "/Users/bunnyhouse_mastercontrol/Agentic_AI/configs/config.py", line 92, in Config
    ROOT_DIR
NameError: name 'ROOT_DIR' is not defined
(.venv) bunnyhouse_mastercontrol@BunnyHouse-MasterControls-Mac-mini Agentic_AI % python -m py_compile configs/config.py
(.venv) bunnyhouse_mastercontrol@BunnyHouse-MasterControls-Mac-mini Agentic_AI % python - <<'PY'
from shared_storage.storage_manager import StorageManager

storage = StorageManager()

job_id = "storage-test-company-request"

print(
    storage.create_job_record(
        job_id=job_id,
        data={
            "message":
                "storage test",

            "source":
                "diagnostic",

            "companies":
                [
                    {
                        "name": "Amazon",
                        "ticker": "AMZN"
                    }
                ],

            "required_agents":
                {}
        }
    )
)
PY
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File "/Users/bunnyhouse_mastercontrol/Agentic_AI/shared_storage/storage_manager.py", line 4, in <module>
    from configs.config import Config
  File "/Users/bunnyhouse_mastercontrol/Agentic_AI/configs/config.py", line 3, in <module>
    class Config:
  File "/Users/bunnyhouse_mastercontrol/Agentic_AI/configs/config.py", line 92, in Config
    ROOT_DIR
NameError: name 'ROOT_DIR' is not defined
(.venv) bunnyhouse_mastercontrol@BunnyHouse-MasterControls-Mac-mini Agentic_AI % 