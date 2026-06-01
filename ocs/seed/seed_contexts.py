"""Seed Vibe Check contexts into OCS participant data.

Run from the OCS repo directory (NOT pasted into the interactive shell):

    uv run python manage.py shell < "/Users/barrytandy/Dev/Afrolabs/Vibe Check/ocs/seed/seed_contexts.py"

Piping the file in makes Django exec it as one script, so blank lines and loops work
(unlike pasting into the >>> REPL). Re-run any time after editing the values below.
"""

from apps.experiments.models import Experiment, ExperimentSession, ParticipantData
from apps.teams.models import Team

# --- edit these for your setup ---
TEAM_SLUG = "afrolabs"
CHATBOT_ID = 22  # from the chatbot URL: /chatbots/<ID>/

CONTEXTS = {
    "contexts": [
        {"slug": "ocs", "name": "OCS",
         "github": {"repos": ["dimagi/open-chat-studio"], "author_handle": "barry47products"}},
        {"slug": "mulligans-law", "name": "Mulligans Law",
         "github": {"repos": ["barry47products/mulligans-law-monorepo"],
                    "author_handle": "barry47products"}},
        {"slug": "chatterbridge", "name": "ChatterBridge",
         "github": {"repos": ["barry47products/chatterbridge"], "author_handle": "barry47products"}},
    ],
    "active_context": "ocs",
    "current_intent": None,
}
# --- end edits ---

team = Team.objects.get(slug=TEAM_SLUG)
experiment = Experiment.objects.get(id=CHATBOT_ID).get_working_version()

participants = {
    session.participant
    for session in ExperimentSession.objects.filter(team=team).select_related("participant")
}

if not participants:
    print("No sessions yet - send one message in the preview chat, then re-run this.")

for participant in participants:
    ParticipantData.objects.update_or_create(
        participant=participant,
        experiment=experiment,
        defaults={"team": team, "data": CONTEXTS},
    )
    print("seeded:", participant.platform, "|", participant.identifier)
