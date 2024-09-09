from ghapi.all import GhApi
import os

organization = "commit-0"
gh_token = os.getenv("GITHUB_TOKEN")
api = GhApi(token=gh_token)


def list_repos(org):
    """List all repositories in the given organization."""
    repos = api.repos.list_for_org(org=org, per_page=100)
    return repos


def delete_repo(owner, repo_name) -> None:
    try:
        api.repos.delete(owner=owner, repo=repo_name)
        print(f"Successfully deleted repository: {owner}/{repo_name}")
    except Exception as e:
        print(f"Failed to delete repository: {owner}/{repo_name}. Error: {e}")


def main() -> None:
    repos = list_repos(organization)

    for repo in repos:
        if ".github.io" in repo["name"] or "commit0" in repo["name"]:
            continue
        else:
            repo_name = repo["name"]
            delete_repo(organization, repo_name)


if __name__ == "__main__":
    main()
