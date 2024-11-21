from hatchling.builders.hooks.plugin.interface import BuildHookInterface

class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        """Add agent package if not installing core-only."""
        if 'wheel' not in build_data:
            return

        for target in build_data.get('wheel', {}).get('targets', []):
            extras = target.get('options', {}).get('extras', [])
            packages = target.get('packages', [])
            
            if 'core' not in extras and 'commit0.optional.agent' not in packages:
                packages.append('commit0.optional.agent')
                target['packages'] = packages