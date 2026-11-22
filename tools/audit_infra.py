"""Write the CDK security review to the CI artifacts directory."""

import shutil
import sys
from pathlib import Path

from aws_cdk import App, Aspects
from cdk_nag import AwsSolutionsChecks

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/infra"))


def synthesize_report(target: Path) -> Path:
    from src.infra_app.stack import CatalogStack

    app = App(outdir=str(target))
    CatalogStack(app, "TsugiteApi")
    Aspects.of(app).add(AwsSolutionsChecks(verbose=True))
    app.synth()
    return next(target.glob("*NagReport.csv"))


def main():
    report = synthesize_report(ROOT / "build/security-synth")
    out = ROOT / "artifacts"
    out.mkdir(exist_ok=True)
    shutil.copyfile(report, out / "cdk-nag.csv")


if __name__ == "__main__":
    main()
