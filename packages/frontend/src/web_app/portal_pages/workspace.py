import client
import workspace_views
from portal_navigation import load
from portal_ui import btn, ctx, field
from screen_registry import Screen


async def load_workspace(_page):
    ctx["workspace"] = await client.api("/workspace")


SCREENS = (
    Screen(
        "workspace",
        "組織・プロジェクト",
        lambda: workspace_views.workspace_view(ctx, field, btn, load),
        load_workspace,
        group="ワークスペース",
        order=60,
    ),
)
