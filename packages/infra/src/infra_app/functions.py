from pathlib import Path

from aws_cdk import Duration
from aws_cdk import aws_lambda as fn
from aws_cdk import aws_logs as logs

ROOT = Path(__file__).resolve().parents[4]
EVENT_PYTHON = fn.Runtime("python3.15", fn.RuntimeFamily.PYTHON)


def catalog_function(scope, name, handler, env, code, execution_role=None):
    group = logs.LogGroup(scope, name + "Logs", retention=logs.RetentionDays.ONE_MONTH)
    f = fn.Function(
        scope,
        name,
        runtime=EVENT_PYTHON,
        handler=handler,
        code=code,
        environment=env,
        role=execution_role,
        timeout=Duration.seconds(60),
        memory_size=768,
        log_group=group,
    )
    group.grant_write(f)
    return f
