import os

from fastmcp import FastMCP

app = FastMCP("mcp-dock")

_enabled = {s.strip() for s in os.getenv("ENABLED_SERVERS", "").split(",") if s.strip()}

if "trello" in _enabled:
    from servers.trello.server import trello
    app.mount("/trello", trello)

if "google-drive" in _enabled:
    from servers.google_drive.server import google_drive
    app.mount("/google-drive", google_drive)

if "github" in _enabled:
    from servers.github.server import github
    app.mount("/github", github)

if "gitlab" in _enabled:
    from servers.gitlab.server import gitlab
    app.mount("/gitlab", gitlab)

if "slack" in _enabled:
    from servers.slack.server import slack
    app.mount("/slack", slack)

if "notion" in _enabled:
    from servers.notion.server import notion
    app.mount("/notion", notion)

if "linear" in _enabled:
    from servers.linear.server import linear
    app.mount("/linear", linear)

if "jira" in _enabled:
    from servers.jira.server import jira
    app.mount("/jira", jira)

if "telegram" in _enabled:
    from servers.telegram.server import telegram
    app.mount("/telegram", telegram)

if "whatsapp" in _enabled:
    from servers.whatsapp.server import whatsapp
    app.mount("/whatsapp", whatsapp)
