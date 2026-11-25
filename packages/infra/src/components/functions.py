# Lambda関数と実行権限を構成する。
from pathlib import Path

from aws_cdk import Duration
from aws_cdk import aws_lambda as fn
from aws_cdk import aws_logs as logs

ROOT = Path(__file__).resolve().parents[4]
EVENT_PYTHON = fn.Runtime.PYTHON_3_15


def catalog_function(scope, name, handler, env, code, dependencies, execution_role=None):
    group = logs.LogGroup(scope, name + "Logs", retention=logs.RetentionDays.ONE_MONTH)
    f = fn.Function(
        scope,
        name,
        runtime=EVENT_PYTHON,
        handler=handler,
        code=code,
        layers=[dependencies],
        environment=env,
        role=execution_role,
        timeout=Duration.seconds(60),
        memory_size=768,
        log_group=group,
    )
    group.grant_write(f)
    return f
