# Have the Red Wings Been Eliminated Yet?

Every morning at about 8 AM ET during the season, sends a push
notification to your phone with the tweet written, e.g.:

    No. Magic number: 82.

    Lost 2-3 vs. Winnipeg

Tap **Post on X** in the notification and X opens with the text filled in.
Free: no X developer account needed.

## Setup
1. Install the free **ntfy** app (iPhone or Android). Tap + and subscribe to a
   topic with a hard-to-guess name, e.g. `wings-elim-k7x92q`. Anyone who knows
   the name can see the messages, so make it random.
2. Push this folder to a public GitHub repo (`bot.yml` goes in `.github/workflows/`).
3. Repo → Settings → Secrets and variables → Actions → New repository secret:
   name `NTFY_TOPIC`, value = your topic name.
4. Actions tab → "Wings elimination bot" → Run workflow with dry run
   **unchecked**. You should get today's tweet on your phone.
