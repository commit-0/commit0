from hatchling.builders.hooks.plugin.interface import BuildHookInterface

class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        """Add agent package if not installing core-only."""
        target = build_data['wheel']['targets'][0]
        extras = target.get('options', {}).get('extras', [])
        
        if 'core' not in extras:
            target['packages'].append('commit0.optional.agent')