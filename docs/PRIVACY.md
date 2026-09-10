# Data and privacy

The application runs on your host, but generation and publishing call external APIs.

| Data | Stored locally | Sent externally |
| --- | --- | --- |
| Writing profile, optional previous post | `data/*.md` | OpenAI as generation context |
| Drafts, approved posts, summaries, optional notes | `data/journal.sqlite3` | Relevant context to OpenAI; approved post text to LinkedIn |
| OpenAI and LinkedIn credentials | `.env`, `data/linkedin_tokens.json` | Respective provider for authentication |
| Dashboard session | Signed browser cookie | Your own dashboard server |

OpenAI requests use `store=False`. That flag is not a promise of zero provider
retention; consult the provider's applicable data controls and account terms.
The app adds no analytics or telemetry. CSS, JavaScript and HTML are served locally, without
third-party fonts or scripts. No browser push, email, or chat notifications are implemented.

Records are kept until the owner removes them. Back up while services are stopped.
Deleting local records removes memory and duplicate checks; it does not delete posts
already published on LinkedIn or data retained by API providers. Treat backups and
logs with the same care as the live data directory.
