import asyncio
from pathlib import Path
import sys

import git

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server


def run(coro):
    return asyncio.run(coro)


def setup_git_identity(repo: git.Repo):
    with repo.config_writer() as cw:
        cw.set_value("user", "name", "RemoDash Test")
        cw.set_value("user", "email", "remodash-test@example.com")


def create_remote_and_local(tmp_path: Path):
    remote_bare = tmp_path / "remote.git"
    seed = tmp_path / "seed"
    local = tmp_path / "local"

    seed_repo = git.Repo.init(seed)
    setup_git_identity(seed_repo)
    (seed / "README.md").write_text("hello\n", encoding="utf-8")
    seed_repo.git.add(A=True)
    seed_repo.index.commit("initial")

    git.Repo.init(remote_bare, bare=True)
    seed_repo.create_remote("origin", str(remote_bare))
    seed_repo.git.push("-u", "origin", "master")

    local_repo = git.Repo.clone_from(str(remote_bare), str(local))
    setup_git_identity(local_repo)
    return remote_bare, local, local_repo


def make_settings(tmp_path: Path):
    server.settings_manager.settings = {
        "filesystem_mode": "open",
        "git_repos": [],
        "git_root_mode": "manual",
        "git_root_path": str(tmp_path / "repos"),
    }
    server.settings_manager.save_settings = lambda: None


def test_git_manager_button_runtime_flow(tmp_path):
    make_settings(tmp_path)
    remote_bare, local_path, local_repo = create_remote_and_local(tmp_path)

    # Sidebar buttons: add/refresh repos
    add_res = run(server.add_git_repo(server.GitRepoRequest(path=str(local_path))))
    assert add_res["success"] is True
    repos = run(server.list_git_repos())
    assert any(r["path"] == str(local_path) for r in repos)

    # Repo selection + status refresh
    status = run(server.get_git_status(str(local_path)))
    assert status["branch"] in {"master", "main"}

    # Diff + commit button
    changed_file = local_path / "README.md"
    changed_file.write_text("hello\nchange\n", encoding="utf-8")
    diff = run(server.get_git_diff(str(local_path), "README.md"))
    assert "diff --git" in diff["diff"]

    commit_res = run(
        server.git_commit(
            server.GitRepoRequest(
                path=str(local_path),
                message="update readme",
                files=["README.md"],
            )
        )
    )
    assert commit_res["success"] is True

    # Stash + stash pop buttons
    notes = local_path / "notes.txt"
    notes.write_text("baseline\n", encoding="utf-8")
    run(
        server.git_commit(
            server.GitRepoRequest(
                path=str(local_path), message="add notes", files=["notes.txt"]
            )
        )
    )
    notes.write_text("stash me\n", encoding="utf-8")
    stash_res = run(server.git_stash(server.GitRepoRequest(path=str(local_path), message="test stash")))
    assert stash_res["success"] is True
    pop_res = run(server.git_stash_pop(server.GitRepoRequest(path=str(local_path))))
    assert pop_res["success"] is True
    run(
        server.git_commit(
            server.GitRepoRequest(
                path=str(local_path), message="apply stashed notes", files=["notes.txt"]
            )
        )
    )

    # Discard button
    changed_file.write_text("discard this\n", encoding="utf-8")
    discard_res = run(
        server.git_discard(server.GitRepoRequest(path=str(local_path), files=["README.md"]))
    )
    assert discard_res["success"] is True

    # Branch manager: list/create/checkout/delete
    branch_state = run(server.git_list_branches(str(local_path)))
    assert branch_state["local"]

    create_branch = run(
        server.git_create_branch(
            server.GitBranchCreateRequest(path=str(local_path), branch="feature/ui")
        )
    )
    assert create_branch["success"] is True

    checkout_branch = run(
        server.git_checkout_branch(
            server.GitBranchCheckoutRequest(path=str(local_path), branch="feature/ui")
        )
    )
    assert checkout_branch["success"] is True

    back_to_main = run(
        server.git_checkout_branch(
            server.GitBranchCheckoutRequest(path=str(local_path), branch="master")
        )
    )
    assert back_to_main["success"] is True

    delete_branch = run(
        server.git_delete_branch(
            server.GitBranchDeleteRequest(path=str(local_path), branch="feature/ui")
        )
    )
    assert delete_branch["success"] is True

    # Fetch + remote checkout + push + pull buttons
    contributor_path = tmp_path / "contributor"
    contributor_repo = git.Repo.clone_from(str(remote_bare), str(contributor_path))
    setup_git_identity(contributor_repo)

    contributor_repo.git.checkout("-b", "feature/remote-sync")
    (contributor_path / "remote.txt").write_text("remote branch\n", encoding="utf-8")
    contributor_repo.git.add(A=True)
    contributor_repo.index.commit("remote branch commit")
    contributor_repo.git.push("-u", "origin", "feature/remote-sync")

    fetch_res = run(server.git_fetch(server.GitRepoRequest(path=str(local_path))))
    assert fetch_res["success"] is True

    checkout_remote = run(
        server.git_checkout_branch(
            server.GitBranchCheckoutRequest(
                path=str(local_path),
                branch="origin/feature/remote-sync",
                track_remote=True,
            )
        )
    )
    assert checkout_remote["success"] is True

    run(server.git_checkout_branch(server.GitBranchCheckoutRequest(path=str(local_path), branch="master")))

    (local_path / "push.txt").write_text("push content\n", encoding="utf-8")
    run(
        server.git_commit(
            server.GitRepoRequest(
                path=str(local_path), message="push commit", files=["push.txt"]
            )
        )
    )
    push_res = run(server.git_push(server.GitRepoRequest(path=str(local_path))))
    assert push_res["success"] is True

    contributor_repo.git.checkout("master")
    contributor_repo.git.pull("origin", "master")
    (contributor_path / "pull.txt").write_text("pull content\n", encoding="utf-8")
    contributor_repo.git.add(A=True)
    contributor_repo.index.commit("pull commit")
    contributor_repo.git.push("origin", "master")

    pull_res = run(server.git_pull(server.GitRepoRequest(path=str(local_path))))
    assert pull_res["success"] is True

    # Credentials/settings + remove repo + ssh status
    save_creds = run(
        server.save_git_credentials(
            server.GitCredentialsRequest(
                username="git-user",
                token="secret-token",
                git_name="RemoDash",
                git_email="remodash@example.com",
            )
        )
    )
    assert save_creds["success"] is True

    creds = run(server.get_git_credentials())
    assert creds["username"] == "git-user"
    assert creds["token"] == "********"

    ssh_info = run(server.get_ssh_key())
    assert "exists" in ssh_info

    remove_res = run(server.remove_git_repo(server.GitRepoRequest(path=str(local_path))))
    assert remove_res["success"] is True


def test_git_clone_endpoint_runtime_flow(tmp_path):
    make_settings(tmp_path)
    remote_bare, _, _ = create_remote_and_local(tmp_path)

    clone_dest = tmp_path / "cloned-via-endpoint"
    clone_res = run(
        server.git_clone(
            server.GitCloneRequest(url=str(remote_bare), path=str(clone_dest))
        )
    )
    assert clone_res["success"] is True
    assert (clone_dest / ".git").exists()

    repos = run(server.list_git_repos())
    assert any(r["path"] == str(clone_dest) for r in repos)
