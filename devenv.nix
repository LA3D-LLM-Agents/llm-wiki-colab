{ pkgs, ... }:

{
  packages = [
    pkgs.git
    pkgs.jq
    pkgs.python3
    pkgs.shellcheck
    pkgs.uv
  ];

  tasks."llm-wiki:test" = {
    exec = "bash ./tests/run.sh";
    before = [ "devenv:enterTest" ];
  };
}
