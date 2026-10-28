# Submission checklist

The candidate records and submits the video personally. The application does not send email and no recording link has been fabricated.

## Screen recording

Record 3 to 5 minutes, narrating in English or Hindi. Have Ollama and Docker running. Show the repository clone and the documented demo command. A cold first run can exceed the video length on this laptop: show the actual command and result, explain any waiting or cuts honestly, and state the measured duration from VALIDATION.md rather than implying instant processing.

Show a pending draft with `python -m relay show --tenant northwind NW-T02`. Read it before approving. Then run `python -m relay approve --tenant northwind NW-T02 --by Suhani` and show the outbox. Do not approve a ticket merely to satisfy a recording if the text is wrong; reject it instead and explain why.

Show one clinical escalation, one injection flag, and docs/EVAL.md including its errors. Explain that all models run locally and that no real email or financial transaction is performed.

## Submission email contents

- Repository: https://github.com/suhani954/nmg_task
- Tag: submission; obtain exact SHA with `git rev-parse submission`.
- Start: 2026-10-28 13:53:29 IST.
- End: the final tagged commit timestamp, available with `git show -s --format=%cI submission`.
- Hardware: HP 14q-cs0xxx, Intel Core i3-8130U, 7.9 GB RAM, Windows/WSL2, Docker Desktop, local Ollama.
- Recording link: supply the actual uploaded recording URL.

The coding assistant must not send the invitation reply without explicit authorization. Review every line you submit and practice explaining the code before the live walkthrough.
