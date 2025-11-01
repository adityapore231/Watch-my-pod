import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app import collector 
from app import agent
from app import alerter  

# --- Configuration ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="K8s Log Summarizer Agent",
    description="Receives pod crash info, collects data, summarizes with AI, and alerts Slack."
)

# --- Models ---
class PodInfo(BaseModel):
    """Pydantic model for the incoming request body from the Go monitor."""
    namespace: str
    pod_name: str
    reason: str  # <--- ADD THIS LINE

# --- API Endpoints ---
@app.post("/summarize-pod")
def handle_pod_crash(pod_info: PodInfo):
    """
    This is the main endpoint that the Go monitor will call.
    It kicks off the entire collection, analysis, and alerting workflow.
    """
    logger.info(
        f"Received event for: {pod_info.namespace}/{pod_info.pod_name} "
        f"(Reason: {pod_info.reason})"
    )
    
    try:
        # --- Step 2: Call the Collector ---
        logger.info("Step 2: Collecting logs and events...")
        data = collector.collect_pod_data(
            pod_info.namespace, 
            pod_info.pod_name, 
            pod_info.reason
        )
        
        # Add the other info the agent needs
        data["trigger_reason"] = pod_info.reason
        data["namespace"] = pod_info.namespace
        data["pod_name"] = pod_info.pod_name
        
        # --- Step 3: Run the AI Agent (LangGraph) ---
        logger.info("Step 3: Running analysis with AI agent...")
        summary = agent.run_analysis(data)
        
        logger.info("--- AI Summary ---")
        logger.info(summary)
        
        # --- Step 4: Send to Slack (THE NEW LINE) ---
        logger.info("Step 4: Sending summary to Slack...")
        alerter.send_slack_alert(summary) # <-- 2. CALL THE ALERTER
        
        # Return the summary to the Go monitor
        return {
            "status": "alert_sent",
            "pod": f"{pod_info.namespace}/{pod_info.pod_name}",
            "summary": summary
        }
        
    except Exception as e:
        logger.error(f"Error processing pod {pod_info.namespace}/{pod_info.pod_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    """Simple health check endpoint."""
    return {"status": "ok"}

# --- Main entrypoint for Uvicorn ---
if __name__ == "__main__":
    import uvicorn
    # Note: We need to point to the `main:app` object
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)