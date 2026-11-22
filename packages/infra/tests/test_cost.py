from collections import Counter

from aws_cdk import App, Environment
from aws_cdk.assertions import Match, Template
from src.infra_app.stack import CatalogStack


def test_cost_drivers_are_bounded(tmp_path):
    """常時稼働の構成を置かず、Lambdaの実行枠とログ保存期間を制限する。"""
    stack = CatalogStack(
        App(outdir=str(tmp_path / "out")),
        "TsugiteApi",
        env=Environment(account="111111111111", region="ap-northeast-1"),
    )
    template = Template.from_stack(stack)
    for kind in ("AWS::EC2::NatGateway", "AWS::EC2::Instance", "AWS::RDS::DBInstance"):
        template.resource_count_is(kind, 0)
    template.resource_count_is("AWS::DSQL::Cluster", 1)
    for alias in template.find_resources("AWS::Lambda::Alias").values():
        assert "ProvisionedConcurrencyConfig" not in alias["Properties"]

    for handler in ("app.main.handler", "app.authorizer.handler", "app.migrate.handler"):
        template.has_resource_properties(
            "AWS::Lambda::Function",
            {"Handler": handler, "MemorySize": 768, "Timeout": 60, "LoggingConfig": Match.any_value()},
        )
    groups = template.find_resources("AWS::Logs::LogGroup")
    retention = Counter(group.get("Properties", {}).get("RetentionInDays") for group in groups.values())
    assert retention == {30: 3, 90: 1}
