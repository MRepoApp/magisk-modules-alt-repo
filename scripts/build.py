#!/usr/bin/env python3

import json
import os
from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path
from typing import Optional, List

import requests
from dateutil.parser import parse
from github import Github, Auth, UnknownObjectException
from github.Repository import Repository


class GitHubGraphQL:
    def __init__(self, token: str):
        self._token = token

    def graphql_query(self, query: str) -> Optional[dict]:
        query = {"query": query}

        response = requests.post(
            url="https://api.github.com/graphql",
            headers={
                "Authorization": f"bearer {self._token}",
                "Content-Type": "application/json",
            },
            json=query
        )

        if response.ok:
            return response.json()
        else:
            return None

    def query_repository(self, owner: str, name: str, query: str) -> Optional[dict]:
        params = "owner: \"{}\", name: \"{}\"".format(owner, name)
        _query = "query { repository(%s) { %s } }" % (params, query)
        result = self.graphql_query(_query)

        try:
            data = result.get("data")
            repository = data.get("repository")
            return repository
        except AttributeError:
            return None

    def get_sponsor_url(self, owner: str, name: str) -> List[str]:
        repository = self.query_repository(
            owner=owner,
            name=name,
            query="fundingLinks { platform url }"
        )
        if repository is None:
            return list()

        links = list()
        funding_links = repository["fundingLinks"]

        for item in funding_links:
            if item["platform"] == "GITHUB":
                name = item["url"].split("/")[-1]
                links.append(f"https://github.com/sponsors/{name}")
            else:
                links.append(item["url"])

        return links

    def get_homepage_url(self, owner: str, name: str) -> Optional[str]:
        repository = self.query_repository(
            owner=owner,
            name=name,
            query="homepageUrl"
        )
        if repository is None:
            return None

        homepage_url = repository["homepageUrl"]
        if homepage_url != "":
            return homepage_url
        else:
            return None

    def get_pushed_at(self, owner: str, name: str) -> Optional[datetime]:
        repository = self.query_repository(
            owner=owner,
            name=name,
            query="pushedAt"
        )
        if repository is None:
            return None

        try:
            return parse(repository["pushedAt"])
        except TypeError:
            return None


class GithubApi:
    def __init__(self, token: str):
        self._github = Github(auth=Auth.Token(token))
        self._graphql = GitHubGraphQL(token)

        self._config: dict = {
            "log": {},
            "repository": {},
            "modules": {}
        }

    def generate_module(self, repo: Repository) -> Optional[dict]:
        module_prop = self.get_module_prop(repo)
        if module_prop is None:
            return None

        if module_prop.get("updateJson"):
            provider = module_prop["updateJson"]
            changelog = ""
            kind = "update-json"
        else:
            provider = repo.ssh_url
            changelog = self.get_changelog(repo)
            kind = "git"

        if repo.has_issues:
            issues = f"{repo.html_url}/issues"
        else:
            issues = ""

        donate_urls = self._graphql.get_sponsor_url(
            owner=repo.owner.login,
            name=repo.name
        )
        if len(donate_urls) == 0:
            donate = ""
        else:
            donate = donate_urls[0]

        homepage = self._graphql.get_homepage_url(
            owner=repo.owner.login,
            name=repo.name
        )
        if homepage is None:
            homepage = ""

        print(f"id: {module_prop["id"]}")
        return {
            "id": module_prop["id"],
            "kind": kind,
            "provider": provider,
            "changelog": changelog,
            "metadata": {
                "license": self.get_license(repo),
                "homepage": homepage,
                "source": repo.clone_url,
                "donate": donate,
                "support": issues
            }
        }

    def generate_modules(self, user_name: str):
        modules = []
        user = self._github.get_user(user_name)
        for repo in user.get_repos():
            module = self.generate_module(repo)
            if module is not None:
                modules.append(module)

        self._config["modules"] = modules

    def write_to(self, path: Path):
        with open(path, "w") as f:
            json.dump(self._config, f, indent=2)

    @classmethod
    def get_license(cls, repo: Repository):
        spdx_id = ""
        try:
            spdx_id = repo.get_license().license.spdx_id
            if spdx_id == "NOASSERTION":
                spdx_id = ""
        except UnknownObjectException:
            pass

        return spdx_id

    @classmethod
    def get_changelog(cls, repo: Repository):
        changelog = ""
        try:
            changelog = repo.get_contents("changelog.md").download_url
        except UnknownObjectException:
            pass

        return changelog

    @classmethod
    def get_module_prop(cls, repo: Repository) -> Optional[dict]:
        module_prop = {}
        try:
            prop = repo.get_contents("module.prop").decoded_content.decode("utf-8")
            for line in prop.splitlines():
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                module_prop[key] = value

        except UnknownObjectException:
            return None

        return module_prop


class Main:
    @classmethod
    def generate_parser(cls) -> ArgumentParser:
        parser = ArgumentParser()
        parser.add_argument(
            "-t",
            "--token",
            dest="token",
            metavar="TOKEN",
            type=str,
            default=os.getenv("GITHUB_TOKEN"),
            help="set github token"
        )
        parser.add_argument(
            "-u",
            "--user",
            dest="user_name",
            metavar="NAME",
            type=str,
            required=True,
            help="set user-name or organization-name"
        )
        parser.add_argument(
            "-w",
            "--write",
            dest="config_path",
            metavar="PATH",
            type=str,
            required=True,
            help="write config to file"
        )

        return parser

    @classmethod
    def exec(cls):
        parser = cls.generate_parser()
        args = parser.parse_args()
        config_path = Path(args.config_path)

        api = GithubApi(args.token)
        api.generate_modules(args.user_name)
        api.write_to(config_path)


if __name__ == "__main__":
    Main.exec()
