"""リソースの所有者と既存の論理IDを維持する。"""

import json
from pathlib import Path

from aws_cdk import CfnResource, DefaultStackSynthesizer, TagManager


def preserve_logical_ids(stack):
    """Keep existing physical resources when moving their constructs under new parents."""
    ids = json.loads(Path(__file__).with_name("legacy_ids.json").read_text())
    for resource in stack.node.find_all():
        if isinstance(resource, CfnResource):
            relative = resource.node.path.removeprefix(stack.node.path + "/")
            if relative in ids:
                resource.override_logical_id(ids[relative])


class CatalogSynthesizer(DefaultStackSynthesizer):
    """Apply ownership after CDK has created its deployment helpers and metadata."""

    def reusable_bind(self, stack):
        # CatalogStack creates a dedicated synthesizer for each stack.
        self.bind(stack)
        return self

    def synthesize(self, session):
        stack = self._bound_stack
        for resource in stack.node.find_all():
            if not isinstance(resource, CfnResource):
                continue
            component = resource.node.path.removeprefix(stack.node.path + "/").split("/")[0]
            if component.startswith("Custom::CDKBucketDeployment"):
                component = "Portal"
            elif component == "CDKMetadata":
                component = "Stack"
            tags = {"Application": "TsugiteAPI", "ManagedBy": "AWS-CDK", "Component": component}
            manager = TagManager.of(resource)
            if manager is not None:
                for key, value in tags.items():
                    manager.set_tag(key, value)
            resource.add_metadata("Tsugite", tags)
        super().synthesize(session)
