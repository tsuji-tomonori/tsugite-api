"""Write the CDK security review to the CI artifacts directory."""

import shutil
import sys
from pathlib import Path

from aws_cdk import App, Aspects
from cdk_nag import AwsSolutionsChecks

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "infra"))


def main():
    from src.infra_app.stack import CatalogStack

    target = ROOT / "build/security-synth"
    app = App(outdir=str(target))
    CatalogStack(app, "TsugiteApi")
    Aspects.of(app).add(AwsSolutionsChecks(verbose=True))
    app.synth()
    out = ROOT / "artifacts"
    out.mkdir(exist_ok=True)
    report = next(target.glob("*NagReport.csv"))
    shutil.copyfile(report, out / "cdk-nag.csv")


if __name__ == "__main__":
    main()
