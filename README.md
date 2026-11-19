# PIU Chart Atlas

A small static site for PIU Single and Double charts at level **20 and above**.

- Sort by the average of the highest **X** scores (X = 1–300).
- Sort by **Perfect Game count**, independent of X.
- Filter by chart level and mode; search by title; reverse the order.
- Share filters in the URL. Top-X averages automatically exclude charts with fewer than X scores.
- Keep credentials off the website and out of Git.

## Current data status

The committed snapshot is **partial: two real chart leaderboards**, not the full catalog. Browser sign-in and leaderboard structure were verified on PIU on November 19, 2026. The full authenticated command-line scrape could not be run in the build environment because credential input was blocked by automatic approval. Run the exporter below to replace the partial snapshot.

## Run locally

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/scrape.py
python3 -m http.server 4173 --directory docs
```

The exporter prompts for your PIU email/password; the password is hidden. It keeps the session in memory. It exports only chart metadata and numeric scores, with no player names or account profile data. Never commit a password, cookie, `.env`, or session file.

Alternatively supply `PIU_COOKIE` through your own secret manager/environment. `PIU_EMAIL` and `PIU_PASSWORD` environment variables are also supported. A session can expire; rerun with a fresh sign-in. Do not put credentials into the browser frontend.

The scraper walks the source's actual listing pages, reads chart levels/modes from stepball assets, skips CO-OP and charts below 20, and waits between requests. It retries transient failures and only replaces `docs/data.json` after a successful export. `--limit 3` makes an explicitly partial smoke-test snapshot. Default runs export the whole eligible catalog. Run from the repository root.

After a refresh, publish it:

```sh
git add docs/data.json
git commit -m "Refresh PIU leaderboard snapshot"
git push
```

## Metrics and limits

PIU displays **TOP 300** per chart. X cannot exceed 300. Charts with fewer than X leaderboard entries are automatically excluded from average sorting. PG-count sorting includes them.

A PG is a score of **1,000,000**. This counts leaderboard entries, not repeat PG plays by the same person. When all 300 entries are PGs, show **300+**: the source cannot establish the actual total. No missing score is treated as zero.

## Validation

```sh
npm test
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
npm run build
```

No JavaScript dependencies or server backend are required. `docs/` is ready for GitHub Pages. `npm run build` copies it into `dist/` for static hosting. A manual GitHub Actions workflow refreshes the snapshot with repository secrets; scheduled scraping is intentionally not enabled.

Unofficial fan tool. Leaderboard data comes from https://piugame.com/leaderboard/over_ranking.php. This project is not affiliated with Andamiro.

## Hosting status

The repository is private. GitHub rejected Pages setup because the current plan does not support Pages for this repository. A local preview works; no public deployment has been made.

The scraper uses the operating system certificate store via `truststore` and checks HTTPS before prompting for credentials. Python 3.10+ is required.

## Scoreability evidence (default)

This is a descriptive heuristic for finding charts with broadly demonstrated high scores, not a probability, difficulty estimate, or statistical correction for selection bias.

For target T (default 990,000), sort scores descending and take at most 100. Each contributes `clamp((score - (T - 20000)) / 20000, 0, 1)`. Sum the contributions for a 0–100 evidence index. Five PGs alone produce 5; eighty scores at target produce at least 80. Missing entries contribute no evidence, not inferred failures. Target is configurable from 900,000 through 1,000,000. Original top-X average and PG sorts remain available.

The fixed 100-entry depth avoids different denominators and operates below the source’s top-300 cap. It does not remove popularity or chart-age effects. The depth and ramp width are transparent, uncalibrated design choices. Clear-only, best-score leaderboards do not provide attempts, failures, exposure, or matched player skills; therefore true scoring difficulty is not identifiable from this snapshot. Compare charts within level and mode. Sparse charts are uncertain rather than necessarily hard. No Wilson/binomial confidence interval is applied because these entries are not random trials.

A stronger future model needs shared anonymous player identifiers for skill-adjusted chart comparisons, plus attempt/failure data to estimate unconditional success. The current exporter intentionally keeps only numeric scores.
