# CHINA 2035 — Frontier Observatory 1.1

A research-dashboard prototype and **working candidate-feed ingestion pipeline**. It preserves the original 26 curated dossiers, Frontier Atlas, Technology Race and 2035 Simulator.

## What works now

- Research inbox with search, category filters, review state, links and per-browser project linking.
- Two separately labelled **manually curated initial examples** (16–18 October 2026); not presented as automatically collected.
- Python RSS/Atom reader that identifies new candidates, classifies 12 research domains, removes duplicate links and closely matched titles, ignores old/future-dated items, records failed sources, and stores ingestion history.
- Offline HTML application for reading and exporting research. An HTTP-served copy additionally reads new `intelligence.json` after clicking “Recargar datos” and whenever the page loads.
- Scheduled GitHub Actions workflow for running collector at 13:15 and 23:15 UTC daily and committing refreshed feed JSON. Activation requires a GitHub repository with Actions and write permissions. GitHub Actions scheduled jobs can be delayed/skipped by the provider.

Run `python build_ui.py` to rebuild the standalone app from `templates/base_v1.html` and bundled JSON.

## How to run locally

1. Download or unzip the project and open `docs/index.html` or `China2035_Observatory_v1_1_offline.html` in a browser. The HTML works as an offline snapshot.
2. To test the engine without internet: `python -m unittest discover -s tests -v` (uses fixtures only).
3. To collect real candidates with internet: `python engine/collect.py`. On a machine without DNS/network, all sources will show as errors and the command exits nonzero, **without pretending to have found live updates**.
4. Serve the directory: `cd docs && python -m http.server 8765`, then open `http://localhost:8765`. The UI loads the latest collected JSON.

## GitHub Pages automatic publication

1. Create a private or public GitHub repository, as appropriate for your data, and upload the entire project (including `.github/workflows/update-intelligence.yml`). This package **does not** create or publish a repository on your behalf.
2. GitHub Settings → Actions → General: confirm `Read and write permissions` for workflows. Enable Actions and manually run the `China 2035 Intelligence Feed` workflow once.
3. For a public repository, GitHub Settings → Pages → Build and deployment → Deploy from a branch → select default branch `/docs`. If using a private repository, check your plan's Pages eligibility and whether publishing would make the site publicly accessible.
4. Inspect the **Source status** in the UI after a successful workflow. RSS endpoints can be blocked/changed; “Sources OK” means the XML was fetched and parsed, **not** that its scientific claims are true.

### Editorial safeguards

- No automated updates to maturity, project milestones, comparisons, or national goals.
- Classification is based on keywords and metadata: misclassification and missed stories are expected. It is a triage system, not a fact-checker.
- One news story is one candidate, not one independently corroborated breakthrough. Google News RSS is a discovery channel and may link to intermediate pages; verify the origin before using it as evidence.
- “Revisada”, “descartada” and linking projects in the UI are browser-local until an editor exports the decisions and runs `python engine/apply_reviews.py path/to/china2035_revision_editorial.json` on the repository. This produces versioned `docs/editorial_reviews.json` and `docs/review_log.json`. Committing those two files lets another device read the shared decisions. Editing is never silently automatic.
- Project statuses and dossier evidence are not silently edited by the collector. This isolates reliable research from hype.
- Official 15th Five-Year Plan goals belong to **China 2035 Master Tracker**; news belongs to the Weekly Tracker; this app's inbox tracks *technical project signals*.

### Limitations

Automatic source ingestion is **not turned on by merely downloading this file**. It needs an environment with network access and a recurring execution service; the included GitHub Actions workflow is a deployment option, not an active service. The ChatGPT environment used to build the package cannot reach RSS hosts via DNS, so real-world network collection was not tested here. Tests with controlled RSS/Atom fixtures passed. The dashboard's initial inbox has two human-curated sourced examples.

Sources are configured in `sources.json`, with 12 thematic discovery searches, 7 site-filtered discovery searches (including MIIT, CAS, CGTN, CCTV and Reuters), and 4 independent RSS endpoint candidates. Change/disable endpoints as needed. Additional official Chinese feeds, academic API integration, deeper semantic deduplication, evidence extraction, full Knowledge Graph, durable cross-device moderation and verified dossier versioning remain next-phase work.

## Existing parallel trackers (not automatically synchronized)

This version does **not** claim to read the user’s private Google Sheets. An existing Monday China Weekly Frontier Tracker and monthly Atlas/Innovation monitors are already scheduled separately. A future authorized connector can import verified rows; ingestion should not duplicate their scheduled runs.

## Merge editorial review exports safely

After reviewing items in the application, press **Exportar revisión**. Run `python engine/apply_reviews.py /path/to/china2035_revision_editorial.json` at the project root, inspect `docs/review_log.json`, and commit the resulting files. It refuses unknown project and candidate IDs, invalid review status, and never promotes maturity. The dashboard reads published editorial review state on page load, while local choices take precedence within the current browser.
