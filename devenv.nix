{ pkgs, ... }:

{
  packages = [
    pkgs.git
    pkgs.jq
    pkgs.python3
    pkgs.shellcheck
    pkgs.uv
  ];

  enterTest = ''
    bash tests/run.sh
  '';
}
