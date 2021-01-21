from idf_component_tools.manifest import SolvedComponent, SolvedManifest


class VersionSolver(object):
    """
    The version solver that finds a set of package versions
    that satisfy the root package's dependencies.
    """
    def __init__(self, manifest, locked=None):
        """Expects project manifest and optional dict of locked components"""
        self._manifest = manifest
        self.locked = locked

    @property
    def manifest(self):
        return self._manifest

    def solve(self):
        # TODO: implement real solving, now it will fail on any collision
        # TODO: solve recursively
        def best_version(component):
            cmp_with_versions = component.source.versions(name=component.name, spec=component.version_spec)
            version = max(cmp_with_versions.versions)
            return SolvedComponent(
                name=component.name, source=component.source, version=version, component_hash=version.component_hash)

        solved_components = [best_version(dependency) for dependency in self.manifest.dependencies]
        return SolvedManifest(self.manifest, solved_components)
