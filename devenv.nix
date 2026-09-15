{ pkgs, ... }:

{
  packages = [
    pkgs.act
    pkgs.actionlint
    pkgs.git
    pkgs.jq
    pkgs.jujutsu
    pkgs.python3
    pkgs.shellcheck
    pkgs.uv
  ];

  tasks."llm-wiki:lint-workflows" = {
    exec = "actionlint";
    before = [ "devenv:enterTest" ];
  };

  tasks."llm-wiki:test" = {
    exec = "bash ./tests/run.sh";
    before = [ "devenv:enterTest" ];
  };

  # Rehearse the GitHub workflow locally under act. The repo .actrc keeps the
  # Nix store in a named Docker volume so only the first run installs Nix.
  tasks."llm-wiki:ci" = {
    exec = "act push --workflows .github/workflows/ci.yml";
  };
}
