"""Keep Airflow away from the developer's home: a throwaway AIRFLOW_HOME, no examples.

Set before any test module imports Airflow, which reads its configuration on import.
No test needs a metadata database or a running Airflow.
"""

import os
import tempfile
from pathlib import Path

os.environ["AIRFLOW_HOME"] = str(Path(tempfile.gettempdir()) / "yieldlens-orchestration-tests")
os.environ["AIRFLOW__CORE__LOAD_EXAMPLES"] = "False"
