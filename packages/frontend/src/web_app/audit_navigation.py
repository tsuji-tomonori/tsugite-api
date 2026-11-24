# 監査画面への遷移先を組み立てる。
from portal_navigation import go
from portal_ui import ctx


async def trace_lookup(trace):
    ctx.update(audit_id=trace, audit_action="", audit_offset=0)
    await go("audit")
