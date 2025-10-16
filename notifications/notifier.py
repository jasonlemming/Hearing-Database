"""
Notification System for Congressional Hearing Database

Provides pluggable notification backends for alerting on update failures,
errors, and system issues.

Supported notification types:
- Log: Write to application log (default, always enabled)
- Email: Send via SendGrid API
- Webhook: POST to Discord/Slack webhook URL
"""

import json
import requests
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime
from config.settings import settings
from config.logging_config import get_logger

logger = get_logger(__name__)


class Notifier(ABC):
    """Abstract base class for notification backends"""

    @abstractmethod
    def send(self, title: str, message: str, severity: str = "error", metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Send notification

        Args:
            title: Notification title
            message: Notification message body
            severity: Severity level (info, warning, error, critical)
            metadata: Additional context data

        Returns:
            True if notification sent successfully, False otherwise
        """
        pass


class LogNotifier(Notifier):
    """
    Log-based notifier (default).
    Writes notifications to application log.
    """

    def send(self, title: str, message: str, severity: str = "error", metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Log notification to application log"""
        log_msg = f"[NOTIFICATION] {title}: {message}"

        if metadata:
            log_msg += f" | Metadata: {json.dumps(metadata)}"

        # Map severity to log level
        if severity == "critical":
            logger.critical(log_msg)
        elif severity == "error":
            logger.error(log_msg)
        elif severity == "warning":
            logger.warning(log_msg)
        else:  # info
            logger.info(log_msg)

        return True


class EmailNotifier(Notifier):
    """
    Email notifier using SendGrid API.
    Requires SENDGRID_API_KEY and NOTIFICATION_EMAIL to be configured.
    """

    def __init__(self):
        self.api_key = settings.sendgrid_api_key
        self.to_email = settings.notification_email
        self.from_email = "noreply@hearing-database.app"

        if not self.api_key:
            logger.warning("SendGrid API key not configured, email notifications disabled")
        if not self.to_email:
            logger.warning("Notification email not configured, email notifications disabled")

    def send(self, title: str, message: str, severity: str = "error", metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Send email notification via SendGrid"""
        if not self.api_key or not self.to_email:
            logger.error("Email notifier not properly configured")
            return False

        try:
            # Build email body
            body = f"""
Congressional Hearing Database Update Notification

Title: {title}
Severity: {severity.upper()}
Timestamp: {datetime.now().isoformat()}

{message}
"""

            if metadata:
                body += f"\n\nAdditional Details:\n{json.dumps(metadata, indent=2)}"

            # SendGrid API v3 request
            url = "https://api.sendgrid.com/v3/mail/send"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "personalizations": [
                    {
                        "to": [{"email": self.to_email}],
                        "subject": f"[{severity.upper()}] {title}"
                    }
                ],
                "from": {"email": self.from_email, "name": "Hearing Database"},
                "content": [
                    {
                        "type": "text/plain",
                        "value": body
                    }
                ]
            }

            response = requests.post(url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()

            logger.info(f"Email notification sent to {self.to_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
            return False


class WebhookNotifier(Notifier):
    """
    Webhook notifier for Discord/Slack.
    Sends formatted messages to webhook URLs.
    """

    def __init__(self):
        self.webhook_url = settings.notification_webhook_url

        if not self.webhook_url:
            logger.warning("Webhook URL not configured, webhook notifications disabled")

    def send(self, title: str, message: str, severity: str = "error", metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Send notification to webhook"""
        if not self.webhook_url:
            logger.error("Webhook notifier not properly configured")
            return False

        try:
            # Determine if this is Discord or Slack based on URL
            if "discord.com" in self.webhook_url:
                payload = self._build_discord_payload(title, message, severity, metadata)
            elif "slack.com" in self.webhook_url:
                payload = self._build_slack_payload(title, message, severity, metadata)
            else:
                # Generic webhook payload
                payload = {
                    "title": title,
                    "message": message,
                    "severity": severity,
                    "timestamp": datetime.now().isoformat(),
                    "metadata": metadata
                }

            response = requests.post(self.webhook_url, json=payload, timeout=10)
            response.raise_for_status()

            logger.info(f"Webhook notification sent to {self.webhook_url[:50]}...")
            return True

        except Exception as e:
            logger.error(f"Failed to send webhook notification: {e}")
            return False

    def _build_discord_payload(self, title: str, message: str, severity: str, metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Build Discord webhook payload"""
        # Color codes: blue (info), yellow (warning), red (error), dark red (critical)
        color_map = {
            "info": 0x3498db,
            "warning": 0xf39c12,
            "error": 0xe74c3c,
            "critical": 0x992d22
        }

        embed = {
            "title": title,
            "description": message,
            "color": color_map.get(severity, 0xe74c3c),
            "timestamp": datetime.now().isoformat(),
            "footer": {
                "text": "Congressional Hearing Database"
            },
            "fields": [
                {
                    "name": "Severity",
                    "value": severity.upper(),
                    "inline": True
                }
            ]
        }

        if metadata:
            for key, value in metadata.items():
                embed["fields"].append({
                    "name": key.replace('_', ' ').title(),
                    "value": str(value),
                    "inline": True
                })

        return {"embeds": [embed]}

    def _build_slack_payload(self, title: str, message: str, severity: str, metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Build Slack webhook payload"""
        # Color codes for Slack attachments
        color_map = {
            "info": "#3498db",
            "warning": "#f39c12",
            "error": "#e74c3c",
            "critical": "#992d22"
        }

        fields = [
            {
                "title": "Severity",
                "value": severity.upper(),
                "short": True
            }
        ]

        if metadata:
            for key, value in metadata.items():
                fields.append({
                    "title": key.replace('_', ' ').title(),
                    "value": str(value),
                    "short": True
                })

        return {
            "attachments": [
                {
                    "color": color_map.get(severity, "#e74c3c"),
                    "title": title,
                    "text": message,
                    "fields": fields,
                    "footer": "Congressional Hearing Database",
                    "ts": int(datetime.now().timestamp())
                }
            ]
        }


class NotificationManager:
    """
    Manages multiple notification backends and sends to all enabled channels.
    """

    def __init__(self):
        """Initialize notification manager with configured backends"""
        self.notifiers: list[Notifier] = []

        # Always include log notifier as fallback
        self.notifiers.append(LogNotifier())

        # Add additional notifiers if enabled
        if settings.notification_enabled:
            notification_type = settings.notification_type.lower()

            if notification_type == "email":
                self.notifiers.append(EmailNotifier())
                logger.info("Email notifications enabled")
            elif notification_type == "webhook":
                self.notifiers.append(WebhookNotifier())
                logger.info("Webhook notifications enabled")
            elif notification_type != "log":
                logger.warning(f"Unknown notification type: {notification_type}, using log only")
        else:
            logger.info("Additional notifications disabled, using log only")

    def send(self, title: str, message: str, severity: str = "error", metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Send notification to all configured backends

        Args:
            title: Notification title
            message: Notification message
            severity: Severity level (info, warning, error, critical)
            metadata: Additional context data

        Returns:
            True if at least one notifier succeeded
        """
        success = False

        for notifier in self.notifiers:
            try:
                if notifier.send(title, message, severity, metadata):
                    success = True
            except Exception as e:
                logger.error(f"Notifier {notifier.__class__.__name__} failed: {e}")

        return success

    def notify_update_failure(self, error: str, metrics: Optional[Dict[str, Any]] = None):
        """Send notification for update failure"""
        self.send(
            title="Daily Update Failed",
            message=f"The daily update process failed with error: {error}",
            severity="error",
            metadata=metrics
        )

    def notify_high_error_rate(self, error_count: int, total_count: int):
        """Send notification for high error rate"""
        error_rate = (error_count / total_count * 100) if total_count > 0 else 0
        self.send(
            title="High Error Rate Detected",
            message=f"Update completed but had {error_count} errors out of {total_count} operations ({error_rate:.1f}%)",
            severity="warning",
            metadata={"error_count": error_count, "total_count": total_count, "error_rate_pct": round(error_rate, 2)}
        )

    def notify_circuit_breaker_open(self, circuit_name: str, stats: Dict[str, Any]):
        """Send notification when circuit breaker opens"""
        self.send(
            title=f"Circuit Breaker Opened: {circuit_name}",
            message=f"Circuit breaker '{circuit_name}' has opened due to repeated failures. API requests are temporarily blocked.",
            severity="critical",
            metadata=stats
        )

    def notify_rate_limit_exhausted(self, remaining: int, reset_time: float):
        """Send notification when rate limit is exhausted"""
        from datetime import datetime
        reset_datetime = datetime.fromtimestamp(reset_time)
        self.send(
            title="API Rate Limit Exhausted",
            message=f"Congress.gov API rate limit exhausted. {remaining} requests remaining. Resets at {reset_datetime.strftime('%Y-%m-%d %H:%M:%S')}",
            severity="warning",
            metadata={"remaining_requests": remaining, "reset_time": reset_datetime.isoformat()}
        )


# Global notification manager instance
_notification_manager: Optional[NotificationManager] = None


def get_notifier() -> NotificationManager:
    """Get global notification manager instance (singleton)"""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager()
    return _notification_manager
