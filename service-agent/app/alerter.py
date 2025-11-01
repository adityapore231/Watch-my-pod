import os
import httpx
import logging

logger = logging.getLogger(__name__)

# Get the webhook URL from the environment
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

if not SLACK_WEBHOOK_URL:
    logger.warning("SLACK_WEBHOOK_URL is not set. Slack alerts will be disabled.")
    logger.warning("Please add it to your .env file.")

# We use a persistent client for performance
client = httpx.Client()

def send_slack_alert(summary_text: str):
    """
    Formats the AI summary and sends it to the configured Slack channel.
    """
    if not SLACK_WEBHOOK_URL:
        logger.error("Attempted to send Slack alert, but SLACK_WEBHOOK_URL is not configured.")
        return

    # We use Slack's "Blocks" format to make the message look professional.
    # The AI's summary is already in Markdown, so this works perfectly.
    payload = {
        "text": "K8s Pod Failure Alert", # Fallback text for notifications
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": ":rotating_light: K8s Pod Failure Alert :rotating_light:",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": summary_text # The AI-generated summary
                }
            },
            {
                "type": "divider"
            }
        ]
    }

    try:
        response = client.post(SLACK_WEBHOOK_URL, json=payload)
        
        # Raise an error if Slack didn't return a 200 OK
        response.raise_for_status() 
        
        logger.info(f"Successfully sent alert to Slack. Response: {response.text}")

    except httpx.RequestError as e:
        logger.error(f"Error sending Slack alert: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred sending to Slack: {e}", exc_info=True)