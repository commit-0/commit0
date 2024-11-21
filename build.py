from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict) -> None:
        """Add agent package if not installing core-only."""
        # Handle both wheel and editable builds
        for build_type in ["wheel", "editable"]:
            if build_type not in build_data:
                continue

            for target in build_data[build_type].get("targets", []):
                extras = target.get("options", {}).get("extras", [])
                packages = target.get("packages", [])

                if "core" not in extras and "commit0.optional.agent" not in packages:
                    packages.append("commit0.optional.agent")
                    target["packages"] = packages
