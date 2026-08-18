{ pkgs, ... }:

{
  packages = [
    pkgs.jq
    pkgs.shellcheck
    pkgs.uv
  ];
}
