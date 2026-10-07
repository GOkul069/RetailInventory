"""
Publish the portfolio to a Fabric / Power BI workspace and refresh every model.

Uses Microsoft's fabric-cicd library to publish the PBIP folders as they sit in
the repo, then the Power BI REST API to start an enhanced refresh of each
semantic model and wait for it to finish.

    pip install fabric-cicd azure-identity requests
    set FABRIC_WORKSPACE_ID, AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET
    python deploy.py --env PROD

The service principal needs Contributor (or higher) on the workspace, and the
tenant setting "Service principals can use Fabric APIs" must be on.

Before the first refresh in the service, point the DataFolder parameter at a
location the service can reach (a SharePoint library, OneLake, or a folder
behind an on-premises data gateway). ../parameter.yml does that per environment.
"""
import argparse, os, sys, time
import requests
from azure.identity import ClientSecretCredential
from fabric_cicd import FabricWorkspace, publish_all_items

PBI = "https://api.powerbi.com/v1.0/myorg"
SCOPE = "https://analysis.windows.net/powerbi/api/.default"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default="PROD", help="environment key used in parameter.yml")
    ap.add_argument("--no-refresh", action="store_true")
    args = ap.parse_args()

    workspace_id = os.environ["FABRIC_WORKSPACE_ID"]
    cred = ClientSecretCredential(os.environ["AZURE_TENANT_ID"], os.environ["AZURE_CLIENT_ID"], os.environ["AZURE_CLIENT_SECRET"])
    repo = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    ws = FabricWorkspace(workspace_id=workspace_id, environment=args.env, repository_directory=repo,
                         item_type_in_scope=["SemanticModel", "Report"], token_credential=cred)
    publish_all_items(ws)
    if args.no_refresh:
        return 0

    headers = {"Authorization": f"Bearer {cred.get_token(SCOPE).token}"}
    models = {d["name"]: d["id"] for d in requests.get(f"{PBI}/groups/{workspace_id}/datasets", headers=headers).json()["value"]}
    wanted = sorted(f[:-5] for d, _, fs in os.walk(repo) for f in fs if f.endswith(".pbip"))
    started = {}
    for name in wanted:
        if name not in models:
            print(f"{name}: not found in the workspace after publishing")
            continue
        r = requests.post(f"{PBI}/groups/{workspace_id}/datasets/{models[name]}/refreshes", headers=headers,
                          json={"type": "full", "commitMode": "transactional", "retryCount": 1})
        r.raise_for_status()
        started[name] = models[name]
        print(f"{name}: refresh started")

    failed = 0
    pending = dict(started)
    while pending:
        time.sleep(30)
        for name, ds in list(pending.items()):
            last = requests.get(f"{PBI}/groups/{workspace_id}/datasets/{ds}/refreshes?$top=1", headers=headers).json()["value"][0]
            if last["status"] in ("Completed", "Failed", "Disabled", "Cancelled"):
                print(f"{name}: {last['status']}")
                failed += last["status"] != "Completed"
                del pending[name]
    return failed


if __name__ == "__main__":
    sys.exit(main())
