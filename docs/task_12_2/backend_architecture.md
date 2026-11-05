# SmartAdvisor Backend Architecture

## System Architecture Diagram

```mermaid
flowchart TD
    A["React Frontend<br/>TypeScript + Vite"]
    B["FastAPI Backend<br/>backend/api.py"]
    C["Section Retriever"]
    D["Overlap Detector"]
    E["Alternative Section Search"]
    F["Course Compatibility Engine"]
    G["Conversational Services"]
    H[("FAU_Courses.xlsx")]
    I[("Compatibility Excel Datasets")]
    J["Supabase Cloud Database<br/>Prepared / Inactive"]

    A <-->|"HTTP Requests / JSON Responses"| B

    B --> C
    B --> D
    B --> E
    B --> F
    B --> G

    C --> H
    E --> C
    E --> D
    F --> I

    J -.-|"Not connected to active runtime"| B
```

## Component Summary

- **Frontend:** React 19, TypeScript, and Vite provide course search, scheduling, and conversational interfaces.
- **API Layer:** FastAPI receives HTTP requests, validates inputs, and returns JSON responses.
- **Section Retriever:** Loads and filters FAU course-section information from Excel.
- **Overlap Detector:** Identifies scheduling conflicts using meeting days and times.
- **Alternative Section Search:** Searches for available replacement sections that avoid conflicts.
- **Course Compatibility Engine:** Evaluates student workload and course combination risks using compatibility datasets.
- **Conversational Services:** Classify student requests, extract course information, and route requests to supported backend functions.
- **Data Storage:** Excel files are the active runtime data sources. Supabase database integration is prepared but inactive.

## Architecture Notes

The currently documented application uses a file-backed backend. Schedule selections and chat history are maintained in React client-side state. The local PostgreSQL demo database used for reliability testing is separate from the active Excel-backed course API.

Source: `docs/architecture.md`
