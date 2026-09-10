from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict[str, object]) -> None:
        frontend = Path(self.root) / "web" / "dist"
        if version != "editable" and not (frontend / "index.html").is_file():
            raise RuntimeError("Build the frontend in web/ before building a release artifact")
        if frontend.is_dir():
            destination = "orqalis/web" if self.target_name == "wheel" else "web/dist"
            build_data["force_include"] = {str(frontend): destination}
