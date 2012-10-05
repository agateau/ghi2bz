#!/usr/bin/env python
import argparse
import getpass
import json
import os
import urllib2

# From https://github.com/j4mie/micromodels
import micromodels

# From http://pypi.python.org/pypi/bugzillatools
from bzlib.bugzilla import Bugzilla
from bzlib.bug import Bug

DT_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

GITHUB_URL = "https://api.github.com"


class User(micromodels.Model):
    login = micromodels.CharField()


class Label(micromodels.Model):
    name = micromodels.CharField()


class Milestone(micromodels.Model):
    title = micromodels.CharField()

    def is_valid(self):
        return hasattr(self, "title")


class Issue(micromodels.Model):
    number = micromodels.IntegerField()
    title = micromodels.CharField()
    state = micromodels.CharField()
    body = micromodels.CharField()
    created_at = micromodels.DateTimeField(format=DT_FORMAT)
    updated_at = micromodels.DateTimeField(format=DT_FORMAT)
    closed_at = micromodels.DateTimeField(format=DT_FORMAT)
    labels = micromodels.ModelCollectionField(Label)
    user = micromodels.ModelField(User)
    comments = micromodels.IntegerField()
    milestone = micromodels.ModelField(Milestone)


class Comment(micromodels.Model):
    user = micromodels.ModelField(User)
    updated_at = micromodels.DateTimeField(format=DT_FORMAT)
    body = micromodels.CharField()


def download_if_necessary(url, dst):
    if os.path.exists(dst):
        return

    in_fl = urllib2.urlopen(url)
    with open(dst, "w") as out_fl:
        while True:
            data = in_fl.read(4096)
            if data:
                out_fl.write(data)
            else:
                return


def load_default_configuration():
    desc = "Export issues from a Github Issue Tracker to a Bugzilla instance"
    parser = argparse.ArgumentParser(description=desc)

    parser.add_argument("--dry-run",
        action="store_true", dest="dry_run", default=False,
        help="Print out issues, do not import them")

    parser.add_argument("--bz_url", required=True,
        action="store", dest="bz_url", default=None,
        help="Base url of Bugzilla server. Must end with '/'")

    parser.add_argument("--bz_user", metavar="USER",
        action="store", dest="bz_user", default=None,
        help="Bugzilla user name")

    parser.add_argument("--bz_product", required=True,
        action="store", dest="bz_product", default=None,
        help="Bugzilla product name")

    parser.add_argument("--bz_component", required=True,
        action="store", dest="bz_component", default=None,
        help="Bugzilla component name")

    parser.add_argument("repo", nargs="?", help="name of the github repo (in the form user/repo)")

    options = parser.parse_args()
    return options


def file_issue(bz, product, component, issue, body):
    data = {
        "product": product,
        "component": component,
        "summary": issue.title,
        "version": "unspecified",
        "description": body,
        "op_sys": "Linux",
        "platform": "Other",
        }
    if issue.milestone.is_valid():
        data["target_milestone"] = issue.milestone.title
    bug = Bug(bz, data)
    bug_id = bug.create()
    print "Created bug_id", bug_id


def format_time(in_time):
    return in_time.strftime("%Y-%m-%d %H:%M:%S")


def load_issue_comments(cnf, iss):
    filename = "%s-comments.json" % iss.number
    download_if_necessary(GITHUB_URL + "/%s/issues/%d/comments" % (cnf.repo, iss.number), filename)
    return [Comment.from_dict(x) for x in json.load(open(filename))]


def create_issue_body(conf, issue, comments):
    lst = []
    lst.append("[This bug has been imported. It was originally filed on %s]" % format_time(issue.created_at))
    lst.append("")
    lst.append(issue.body)

    for comment in comments:
        lst.append("")
        lst.append(40 * ".")
        lst.append("")
        lst.append("%s - %s" % (comment.user.login, format_time(comment.updated_at)))
        lst.append(comment.body)

    return "\n".join(lst)


def main(conf):
    if not conf.dry_run:
        bz = Bugzilla(conf.bz_url, conf.bz_user, getpass.getpass())

    filename = "issues.json"
    download_if_necessary(GITHUB_URL + "/%s/issues" % conf.repo, filename)

    issues = json.load(open(filename))
    for dct in issues:
        issue = Issue.from_dict(dct)
        if issue.state == "open":
            if issue.comments > 0:
                comments = load_issue_comments(conf, issue)
            else:
                comments = []

            body = create_issue_body(conf, issue, comments)

            if conf.dry_run:
                print 40 * "="
                print "#%d %s" % (issue.number, issue.title)
                if issue.milestone.is_valid():
                    print "Milestone:", issue.milestone.title
                print
                print body
            else:
                file_issue(bz, conf.bz_product, conf.bz_component, issue, body)


if __name__ == '__main__':
    config = load_default_configuration()
    main(config)
