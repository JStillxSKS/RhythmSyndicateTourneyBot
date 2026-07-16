"""Render Discord developer setup checklist PDF for RS Tournament Bot."""
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

OUT = Path(r"C:\Users\JStillxSKS\Desktop\Rhythm_Syndicate_Tourney_Bot_Discord_Setup.pdf")
# Also copy into project
OUT2 = Path(r"C:\Users\JStillxSKS\Desktop\RhythmSyndicateTourneyBot\DISCORD_SETUP.pdf")

PURPLE = HexColor("#E10600")  # RS red
DARK = HexColor("#1E1B2E")
MUTED = HexColor("#4B5563")


def main() -> None:
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "T",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=15,
        textColor=PURPLE,
        alignment=TA_LEFT,
        spaceAfter=4,
        leading=18,
    )
    sub = ParagraphStyle(
        "S",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        textColor=MUTED,
        spaceAfter=12,
        leading=12,
    )
    h = ParagraphStyle(
        "H",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=DARK,
        spaceBefore=10,
        spaceAfter=3,
        leading=14,
    )
    b = ParagraphStyle(
        "B",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        textColor=DARK,
        leading=12.5,
        leftIndent=12,
        spaceAfter=1,
    )
    note = ParagraphStyle(
        "N",
        parent=b,
        leftIndent=0,
        fontSize=8.5,
        textColor=MUTED,
        spaceBefore=10,
        leading=11,
    )

    def section(heading: str, items: list[str]) -> list:
        out = [Paragraph(heading, h)]
        for item in items:
            out.append(Paragraph(f"•  {item}", b))
        return out

    story: list = []
    story.append(Paragraph("Rhythm Syndicate Tournament Bot", title))
    story.append(
        Paragraph(
            "Discord Developer Portal — what to create, enable, and copy (Windows setup)",
            sub,
        )
    )

    story.extend(
        section(
            "1. Create the application",
            [
                "Go to: <b>https://discord.com/developers/applications</b>",
                "Click <b>New Application</b>",
                "Name suggestion: <b>RS Tourney</b> or <b>Rhythm Syndicate Tourney</b> (your call)",
                "Create → open the app",
            ],
        )
    )

    story.extend(
        section(
            "2. Bot user + token",
            [
                "Left sidebar → <b>Bot</b>",
                "Click <b>Add Bot</b> / Reset Token if needed",
                "Click <b>Reset Token</b> → <b>Copy</b> the token",
                "Paste into local <b>.env</b> as: <b>DISCORD_TOKEN=…</b>",
                "<b>Never</b> paste the token into chat, GitHub, or GROK_BRIDGE",
                "Optional: set bot username / avatar (use RS logo if you want)",
            ],
        )
    )

    story.extend(
        section(
            "3. Privileged Gateway Intents (Bot page)",
            [
                "<b>MESSAGE CONTENT INTENT</b> → <b>ON</b> (required to read Smash Drums score embeds)",
                "Server Members Intent → <b>OFF</b> (not required for this bot)",
                "Presence Intent → <b>OFF</b>",
                "Save Changes",
            ],
        )
    )

    story.extend(
        section(
            "4. OAuth2 invite URL (get the bot into the server)",
            [
                "Left sidebar → <b>OAuth2</b> → <b>URL Generator</b>",
                "Scopes (check both):",
                "  ☑ <b>bot</b>",
                "  ☑ <b>applications.commands</b>  (slash commands: /tourney and /rs)",
                "Bot Permissions (check these):",
                "  ☑ View Channels",
                "  ☑ Send Messages",
                "  ☑ Send Messages in Threads (if you use threads later)",
                "  ☑ Embed Links",
                "  ☑ Attach Files  (logo / future images)",
                "  ☑ Read Message History",
                "  ☑ Add Reactions  (✅ verified / ⏳ pending)",
                "  ☑ Use External Emojis (optional)",
                "  ☐ Administrator — <b>not</b> required (avoid unless you insist)",
                "Copy the generated URL at the bottom → open in browser → pick <b>Rhythm Syndicate</b> (or a test server) → Authorize",
            ],
        )
    )

    story.extend(
        section(
            "5. Server-side channel permissions",
            [
                "In the tourney channel (or category), ensure the <b>bot’s role</b> can:",
                "  View Channel · Send Messages · Embed Links · Attach Files · Read History · Add Reactions",
                "If the channel is private, explicitly allow the bot role (or @everyone already can see it)",
                "Staff who run <b>/rs</b> need <b>Manage Server</b> <i>or</i> a role whose ID you put in env (below)",
            ],
        )
    )

    story.extend(
        section(
            "6. IDs to copy (Developer Mode on Discord)",
            [
                "Discord Settings → App Settings → Advanced → <b>Developer Mode ON</b>",
                "Right-click the <b>server name</b> → Copy Server ID → <b>RS_GUILD_ID</b>",
                "Right-click the <b>tourney channel</b> → Copy Channel ID → <b>RS_CHANNEL_ID</b>",
                "Optional: separate submit channel → <b>RS_SUBMIT_CHANNEL_ID</b> (else same as channel)",
                "Right-click each <b>staff role</b> that should run /rs → Copy Role ID",
                "  Put them comma-separated in <b>RS_ADMIN_ROLE_IDS</b> (example: 111,222)",
                "Anyone with <b>Manage Server</b> can also use /rs even without those roles",
            ],
        )
    )

    story.extend(
        section(
            "7. .env file (what the bot reads)",
            [
                "On the PC, in folder: <b>Desktop\\RhythmSyndicateTourneyBot\\</b>",
                "Copy <b>.env.example</b> → <b>.env</b>",
                "Fill:",
                "  DISCORD_TOKEN=…",
                "  RS_GUILD_ID=…",
                "  RS_CHANNEL_ID=…",
                "  RS_ADMIN_ROLE_IDS=…",
                "  # optional: RS_SUBMIT_CHANNEL_ID=…",
            ],
        )
    )

    story.extend(
        section(
            "8. After invite — quick prove list (when bot is running)",
            [
                "Bot shows online in the member list",
                "Slash commands appear: type <b>/tourney</b> and <b>/rs</b>",
                "<b>/tourney help</b> shows build string (e.g. foundation-v1)",
                "Staff: <b>/rs dashboard post</b> in the tourney channel",
                "If slash commands missing: wait a minute, or re-invite with <b>applications.commands</b> scope",
            ],
        )
    )

    story.extend(
        section(
            "9. What you do NOT need for Season 1 foundation",
            [
                "No webhook (this is a full bot, not Larry-style webhook)",
                "No privileged Members intent",
                "No Gemini / OCR key for v1 (game score embeds only for now)",
                "No connection to Surprise Attack or Indies bots (separate app + token)",
            ],
        )
    )

    story.append(Spacer(1, 8))
    story.append(
        Paragraph(
            "Project path: Desktop\\RhythmSyndicateTourneyBot\\ · Run later: python bot\\main.py · "
            "Docs: SETUP.md · OPERATOR_GUIDE.md · RENDER.md",
            note,
        )
    )

    import shutil

    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=letter,
        leftMargin=0.65 * inch,
        rightMargin=0.65 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
        title="RS Tourney Bot — Discord Setup",
        author="Grok Lesnar",
    )
    doc.build(story)
    shutil.copyfile(OUT, OUT2)
    print(OUT, OUT.stat().st_size)
    print(OUT2, OUT2.stat().st_size)


if __name__ == "__main__":
    main()
