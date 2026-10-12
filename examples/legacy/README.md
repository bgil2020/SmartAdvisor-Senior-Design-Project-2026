# Historical Prototypes and Legacy Examples

This directory contains standalone prototypes, exploratory scripts, and sample workbooks developed during the early stages of SmartAdvisor.

> [!NOTE]
> **Active Application vs. Historical Prototypes:**
> The authoritative application code lives in `backend/` (FastAPI backend and compatibility engine) and `frontend/` (React/Vite single-page application).
> The files in this folder are preserved for reference, prototype demonstration, and historical provenance. They are **not** part of the production application runtime.

---

## Contents

| File / Folder | Description |
| :--- | :--- |
| `course_compatibility_engine.py` | Standalone prototype of the course compatibility logic that reads directly from local Excel workbooks. |
| `smartadvisor_personalized_prototype_v5.py` | Earlier version 5 prototype of the personalized course recommendation logic. |
| `smartadvisor.py` | Command-line interface prototype demonstrating alternative section search for schedule conflicts. |
| `test_compatability_api.py` | Standalone smoke script invoking `course_compatibility_engine.py` with synthetic student inputs. |
| `Course Combinations.xlsx` | Sample workbook of historical course pairing heuristics. |
| `Synthetic Profiles.xlsx` | Synthetic test profiles used by the legacy prototype engines. |
| `Final_FAU_CS_CE_EE_Undergraduate_Courses_Revised(Sheet1).xlsx` | Course catalog dataset used by the legacy prototype scripts. |
| `Course Compatibility Examples/` | Historical test data and example notes. |

---

## How to Run

These scripts run standalone using Python and require `openpyxl`:

```bash
# Activate the project virtual environment
source .venv/bin/activate  # macOS / Linux
# or: .venv\Scripts\activate  # Windows

# Run the standalone compatibility prototype test
python examples/legacy/test_compatability_api.py

# Run the interactive CLI alternative search prototype
python examples/legacy/smartadvisor.py
```
