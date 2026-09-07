"""Synthetic plugin and skill state, independent of session execution."""

from dataclasses import dataclass, field
from pathlib import Path
import secrets

from .harness_support import write_json


@dataclass(frozen=True)
class PluginFixture:
    marketplace: Path
    path: Path

    @classmethod
    def create(cls, root, harness):
        marketplace = root / "fixture"
        plugin = marketplace / "metadata-fixture"
        write_json(plugin / f".{harness}-plugin/plugin.json", {
            "name": "metadata-fixture", "version": "0.0.1",
            "description": "Skill metadata capability fixture.",
        })
        if harness == "codex":
            write_json(marketplace / ".agents/plugins/marketplace.json", {
                "name": "metadata-market", "plugins": [{
                    "name": "metadata-fixture",
                    "source": {"source": "local", "path": "./metadata-fixture"},
                    "description": "Skill metadata capability fixture.",
                }],
            })
        return cls(marketplace, plugin)


@dataclass(frozen=True)
class SkillFixture:
    plugin: PluginFixture
    name: str = field(default_factory=lambda: "metadata-probe-" + secrets.token_hex(8))
    description_token: str = field(default_factory=lambda: "DESCRIPTION-" + secrets.token_hex(16))
    body_token: str = field(default_factory=lambda: "BODY-" + secrets.token_hex(16))

    @classmethod
    def create(cls, root, harness, body_text=""):
        skill = cls(PluginFixture.create(root, harness))
        skill.replace_body(body_text)
        return skill

    @property
    def directory(self) -> Path:
        return self.plugin.path / "skills" / self.name

    @property
    def description(self) -> str:
        return f"Inert capability fixture. Description marker {self.description_token}."

    @property
    def metadata(self) -> dict:
        # Body markers must not be exposed in pre-session reports.
        return {"name": self.name, "description": self.description}

    def replace_body(self, body_text):
        self.directory.mkdir(parents=True, exist_ok=True)
        (self.directory / "SKILL.md").write_text(
            f"---\nname: {self.name}\ndescription: {self.description}\n---\n{body_text}\n"
        )
