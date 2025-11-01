"""
Alerter module for sending notifications to Slack.
"""

import logging
import os
from typing import Dict, Any
import requests

logger = logging.getLogger(__name__)


class SlackAlerter:
    """
    Alerter for sending messages to Slack.
    """

    def __init__(self):
        """Initialize the Slack alerter."""
        self.webhook_url = os.getenv("SLACK_WEBHOOK_URL")
        if not self.webhook_url:
            logger.warning("SLACK_WEBHOOK_URL not set. Slack notifications disabled.")
        else:
            logger.info("Slack alerter initialized")

    def send_alert(self, message: Dict[str, Any]) -> bool:
        """
        Send an alert message to Slack.

        Args:
            message: Dictionary containing alert information

        Returns:
            True if successful, False otherwise
        """
        if not self.webhook_url:
            logger.warning("Cannot send Slack alert: webhook URL not configured")
            return False

        try:
            # Format the message for Slack
            slack_message = self._format_message(message)
            
            response = requests.post(
                self.webhook_url,
                json=slack_message,
                timeout=10
            )

            if response.status_code == 200:
                logger.info("Successfully sent Slack alert")
                return True
            else:
                logger.error(f"Failed to send Slack alert: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Error sending Slack alert: {e}")
            return False

    def _format_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format the message for Slack.

        Args:
            message: Raw message dictionary

        Returns:
            Formatted Slack message
        """
        pod_name = message.get("pod_name", "Unknown")
        namespace = message.get("namespace", "Unknown")
        event_type = message.get("event_type", "Unknown")
        analysis = message.get("analysis", "No analysis available")
        severity = message.get("severity", "info")

        # Map severity to emoji
        emoji_map = {
            "critical": "🚨",
            "error": "❌",
            "warning": "⚠️",
            "info": "ℹ️",
        }
        emoji = emoji_map.get(severity, "📝")

        slack_message = {
            "text": f"{emoji} Pod Event: {namespace}/{pod_name}",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"{emoji} Pod Event Alert"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Pod:*\n{pod_name}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Namespace:*\n{namespace}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Event Type:*\n{event_type}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Severity:*\n{severity}"
                        }
                    ]
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Analysis:*\n{analysis}"
                    }
                }
            ]
        }

        recommendations = message.get("recommendations", [])
        if recommendations:
            slack_message["blocks"].append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Recommendations:*\n" + "\n".join(f"• {r}" for r in recommendations)
                }
            })

        return slack_message
