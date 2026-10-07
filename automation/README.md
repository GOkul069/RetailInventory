# Automation

Small pieces that turn the project into something a team could run.

| File | What it does |
|---|---|
| `check_pbip.py` | Pre-deployment check: every JSON file parses, every report points at a real model, and every field a visual uses exists in the TMDL. Exit code = number of problems, so CI fails on any. |
| `deploy.py` | Publishes the project to a Fabric / Power BI workspace with Microsoft's `fabric-cicd` library, then starts an enhanced refresh of each semantic model through the Power BI REST API and waits for the result. |
| `../parameter.yml` | Per-environment find and replace that `fabric-cicd` applies while publishing. It swaps the local `C:\PowerBI-Portfolio\` data path for one the service can reach. |
| `github-workflow/deploy.yml` | GitHub Actions workflow: runs the check on every pull request, then publishes and refreshes on merge to main. |

## Setting it up

1. Create a service principal, give it Contributor on the target workspace, and turn on the tenant setting that lets service principals use Fabric APIs.
2. Put the CSVs somewhere the service can read (a SharePoint library, OneLake, or a file share behind an on-premises data gateway) and edit `parameter.yml`.
3. Add `AZURE_TENANT_ID`, `AZURE_CLIENT_ID` and `AZURE_CLIENT_SECRET` as repository secrets and `FABRIC_WORKSPACE_ID` as a variable.
4. Copy `github-workflow/deploy.yml` to `.github/workflows/`.

Run locally with:

```
python automation/check_pbip.py .
pip install fabric-cicd azure-identity requests
python automation/deploy.py --env DEV
```

