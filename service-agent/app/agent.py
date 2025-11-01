import os
import logging
from typing import TypedDict, Annotated
from dotenv import load_dotenv
import google.generativeai as genai
from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)

# --- 1. Load API Key and Configure AI Client ---
load_dotenv() # Loads the .env file
API_KEY = os.getenv("GOOGLE_API_KEY")

if not API_KEY:
    logger.error("GOOGLE_API_KEY not found. Please set it in the .env file.")
    raise ValueError("GOOGLE_API_KEY is not set.")

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

# --- 2. Define the Graph's "State" ---
# This is the data that flows through our agent
class AgentState(TypedDict):
    pod_name: str
    namespace: str
    trigger_reason: str
    logs: str
    events: str
    summary: str # This is where we'll put the output

# --- 3. Define the Prompt Template ---
PROMPT_TEMPLATE = """
You are a Senior Site Reliability Engineer (SRE).
Analyze the following Kubernetes pod logs and provide a developer-focused summary.

Your Response Must Include:

Root Cause: Clearly state the main issue causing the pod failure.

Impact: Briefly describe how it affects the pod or application.

Fix Recommendation: Suggest the most likely fix or next debugging step.

Keep your answer concise (max 5–6 lines) and developer-understandable — no generic explanations or redundant details.

Trigger:
The pod failure was first detected because of: {trigger_reason}

Logs:
{logs}
"""

# --- 4. Define the Graph Nodes ---
def summarize_node(state: AgentState) -> dict:
    """
    The one and only node in our graph.
    It takes the collected data, formats the prompt, and calls the AI.
    """
    logger.info(f"Agent: Summarizing for {state['namespace']}/{state['pod_name']}")
    print("trigger_reason:", state['trigger_reason'])
    # Format the prompt with the data from the state
    prompt = PROMPT_TEMPLATE.format(
        trigger_reason=state['trigger_reason'],
        logs=state['logs'],
        events=state['events']
    )
    
    try:
        # Call the Gemini API
        response = model.generate_content(prompt)
        
        # The summary will include the pod name/status, let's just grab the whole text
        # We can clean this up later if needed
        summary_text = response.text
        
        logger.info(f"Agent: Summary generated:\n{summary_text}")
        
        return {"summary": summary_text}
        
    except Exception as e:
        logger.error(f"Agent: Error calling GenerativeModel: {e}", exc_info=True)
        error_summary = (
            f"**Pod:** `{state['namespace']}/{state['pod_name']}`\n"
            f"**Status:** `{state['trigger_reason']}`\n"
            f"**Root Cause:** AI summarization failed.\n"
            f"**Details:** The agent could not connect to the AI model or the model returned an error.\n"
            f"**Error:** {str(e)}"
        )
        return {"summary": error_summary}

# --- 5. Build the Graph ---
def create_graph() -> StateGraph:
    """
    Creates and compiles the LangGraph agent.
    """
    workflow = StateGraph(AgentState)
    
    # Add our one and only node
    workflow.add_node("summarize", summarize_node)
    
    # The "summarize" node is both the beginning and the end
    workflow.set_entry_point("summarize")
    workflow.add_edge("summarize", END)
    
    # Compile the graph into a runnable app
    return workflow.compile()

# We create the graph app once on startup
graph_app = create_graph()

# --- 6. Main Entrypoint for our App ---
def run_analysis(data: dict) -> str:
    """
    The main function that main.py will call.
    It invokes the graph and returns the summary.
    """
    # The 'data' dict comes from collector.py
    # We pass it in as the initial state for our graph
    state = {
        "pod_name": data.get("pod_name"),
        "namespace": data.get("namespace"),
        "trigger_reason": data.get("trigger_reason"),
        "logs": data.get("logs"),
        "events": data.get("events"),
        "summary": "" # Start with an empty summary
    }
    
    # Run the graph
    final_state = graph_app.invoke(state)
    
    # Return the final summary
    return final_state['summary']