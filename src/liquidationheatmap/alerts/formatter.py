"""Message formatters for different notification channels.

Provides formatting functions for:
- Discord embeds
- Telegram Markdown messages
- Email HTML content
"""

from decimal import Decimal

from .models import Alert, AlertSeverity

# Color mappings for Discord embeds
SEVERITY_COLORS = {
    AlertSeverity.CRITICAL: 0xFF0000,  # Red
    AlertSeverity.WARNING: 0xFFA500,  # Orange
    AlertSeverity.INFO: 0x00BFFF,  # Light blue
}

# Emoji mappings for text messages
SEVERITY_EMOJI = {
    AlertSeverity.CRITICAL: "🚨",
    AlertSeverity.WARNING: "⚠️",
    AlertSeverity.INFO: "ℹ️",
}


def format_discord_embed(alert: Alert) -> dict:
    """Format an alert as a Discord embed.

    Args:
        alert: The alert to format

    Returns:
        Discord embed dictionary ready for webhook payload
    """
    color = SEVERITY_COLORS.get(alert.severity, 0x808080)
    emoji = SEVERITY_EMOJI.get(alert.severity, "📢")

    title = f"{emoji} {alert.severity.value.upper()} Alert: {alert.symbol or 'BTC'}"

    fields = []

    if alert.current_price:
        fields.append(
            {
                "name": "Current Price",
                "value": f"${alert.current_price:,.2f}",
                "inline": True,
            }
        )

    if alert.zone_price:
        fields.append(
            {
                "name": "Zone Price",
                "value": f"${alert.zone_price:,.2f}",
                "inline": True,
            }
        )

    if alert.distance_pct is not None:
        fields.append(
            {
                "name": "Distance",
                "value": f"{alert.distance_pct:.2f}%",
                "inline": True,
            }
        )

    if alert.zone_density:
        # Format large numbers with M suffix
        density_m = alert.zone_density / Decimal("1000000")
        fields.append(
            {
                "name": "Zone Density",
                "value": f"${density_m:.1f}M",
                "inline": True,
            }
        )

    if alert.zone_side:
        side_emoji = "📈" if alert.zone_side == "long" else "📉"
        fields.append(
            {
                "name": "Zone Side",
                "value": f"{side_emoji} {alert.zone_side.upper()}",
                "inline": True,
            }
        )

    embed = {
        "title": title,
        "color": color,
        "fields": fields,
    }

    if alert.message:
        embed["description"] = alert.message

    return embed


def format_telegram_message(alert: Alert) -> str:
    """Format an alert as a Telegram Markdown message.

    Args:
        alert: The alert to format

    Returns:
        Markdown-formatted message string
    """
    emoji = SEVERITY_EMOJI.get(alert.severity, "📢")
    symbol = alert.symbol or "BTC"

    lines = [
        f"{emoji} *{alert.severity.value.upper()} Alert*",
        f"*Symbol:* {symbol}",
    ]

    if alert.current_price:
        lines.append(f"*Current Price:* ${alert.current_price:,.2f}")

    if alert.zone_price:
        lines.append(f"*Zone Price:* ${alert.zone_price:,.2f}")

    if alert.distance_pct is not None:
        lines.append(f"*Distance:* {alert.distance_pct:.2f}%")

    if alert.zone_density:
        density_m = alert.zone_density / Decimal("1000000")
        lines.append(f"*Zone Density:* ${density_m:.1f}M")

    if alert.zone_side:
        side_emoji = "📈" if alert.zone_side == "long" else "📉"
        lines.append(f"*Zone Side:* {side_emoji} {alert.zone_side.upper()}")

    if alert.message:
        lines.append(f"\n{alert.message}")

    return "\n".join(lines)


def format_email_html(alert: Alert) -> tuple[str, str]:
    """Format an alert as HTML email content.

    Args:
        alert: The alert to format

    Returns:
        Tuple of (subject, html_body)
    """
    symbol = alert.symbol or "BTC"
    subject = f"[{alert.severity.value.upper()}] Liquidation Alert: {symbol}"

    # Build HTML table rows
    rows = []

    if alert.current_price:
        rows.append(
            f"<tr><td><strong>Current Price</strong></td><td>${alert.current_price:,.2f}</td></tr>"
        )

    if alert.zone_price:
        rows.append(
            f"<tr><td><strong>Zone Price</strong></td><td>${alert.zone_price:,.2f}</td></tr>"
        )

    if alert.distance_pct is not None:
        rows.append(
            f"<tr><td><strong>Distance</strong></td><td>{alert.distance_pct:.2f}%</td></tr>"
        )

    if alert.zone_density:
        density_m = alert.zone_density / Decimal("1000000")
        rows.append(f"<tr><td><strong>Zone Density</strong></td><td>${density_m:.1f}M</td></tr>")

    if alert.zone_side:
        rows.append(
            f"<tr><td><strong>Zone Side</strong></td><td>{alert.zone_side.upper()}</td></tr>"
        )

    table_content = "\n".join(rows)

    # Severity color
    color_map = {
        AlertSeverity.CRITICAL: "#FF0000",
        AlertSeverity.WARNING: "#FFA500",
        AlertSeverity.INFO: "#00BFFF",
    }
    severity_color = color_map.get(alert.severity, "#808080")

    body = f"""<html>
<body>
<h2 style="color: {severity_color};">{alert.severity.value.upper()} Liquidation Alert</h2>
<table border="1" cellpadding="8" cellspacing="0">
{table_content}
</table>
{f"<p>{alert.message}</p>" if alert.message else ""}
</body>
</html>"""

    return subject, body
