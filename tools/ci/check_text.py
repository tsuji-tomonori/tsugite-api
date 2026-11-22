"""Check Git index blobs, respecting binary attributes and partial staging."""

import argparse
import os
import subprocess
import sys


def git(*args, data=None):
    return subprocess.check_output(["git", *args], input=data)


def violations(data):
    if data.startswith(b"\xef\xbb\xbf"):
        yield "UTF-8 BOMを削除"
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        yield "UTF-8で保存"
    if b"\0" in data:
        yield "テキストにNUL文字を含めない"
    if b"\r" in data:
        yield "改行をLFに統一"
    if data and (not data.endswith(b"\n") or data.endswith(b"\n\n")):
        yield "末尾改行を1つに統一"


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--staged", action="store_true")
    mode.add_argument("--base", help="Check files changed since the PR merge base")
    args = parser.parse_args()
    staged = args.staged
    if staged and git("branch", "--show-current").strip() in {b"main", b"master"}:
        sys.exit("作業ブランチを作成してからコミットしてください。")
    if staged:
        names = git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z")
    elif args.base:
        names = git("diff", "--name-only", "--diff-filter=ACMRT", "-z", f"{args.base}...HEAD", "--")
    else:
        names = git("ls-files", "-z")
    attrs = git("check-attr", "--cached", "-z", "--stdin", "text", data=names).split(b"\0")
    failed = False
    for path, attr in zip(attrs[0::3], attrs[2::3]):
        if attr == b"unset":
            continue
        file = os.fsdecode(path)
        data = git("show", ":" + file)
        if attr in {b"auto", b"unspecified"} and b"\0" in data[:8000]:
            continue
        for reason in violations(data):
            print(f"{file}: {reason}", file=sys.stderr)
            failed = True
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
