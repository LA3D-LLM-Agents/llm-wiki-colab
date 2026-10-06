{ pkgs, inputs, ... }:

let
  # The shipped hooks run under whatever the user's machine has, and stock
  # macOS ships bash 3.2.57 and Python 3.9. No current distribution packages
  # bash 3.2, so it is built from source here; Python 3.9 comes from the last
  # nixpkgs release that carried it, which cache.nixos.org still serves.
  # Apple's Command Line Tools stayed on git 2.39 for years; nixos-22.11
  # carries 2.38.5, the nearest release at or below that.
  bash32 = pkgs.stdenv.mkDerivation {
    pname = "bash";
    version = "3.2.57";
    src = pkgs.fetchurl {
      url = "mirror://gnu/bash/bash-3.2.57.tar.gz";
      hash = "sha256-P6na+F6/NQaPCQzlEoPd7rPHXrW8cLGkp8sFhov+BqQ=";
    };
    nativeBuildInputs = [ pkgs.bison ];
    # Pre-C99 code: modern GCC rejects it under the default warnings and the
    # nixpkgs hardening flags.
    env.NIX_CFLAGS_COMPILE = "-std=gnu89 -Wno-implicit-function-declaration -Wno-implicit-int -Wno-incompatible-pointer-types";
    hardeningDisable = [ "all" ];
    configureFlags = [ "--without-bash-malloc" ];
  };
  python39 = inputs.nixpkgs-py39.legacyPackages.${pkgs.stdenv.system}.python39;
  gitFloor = inputs.nixpkgs-git-floor.legacyPackages.${pkgs.stdenv.system}.git;
  # Everything the suite may run under the floor. PATH is replaced with this,
  # not prepended to, so a tool missing here is missing for the run.
  floorPath = pkgs.lib.makeBinPath [
    bash32
    python39
    gitFloor
    pkgs.coreutils
    pkgs.curl
    pkgs.diffutils
    pkgs.file
    pkgs.findutils
    pkgs.gawk
    pkgs.git-cliff
    pkgs.gnugrep
    pkgs.gnused
    pkgs.jq
    pkgs.jujutsu
    pkgs.shellcheck
    pkgs.tmux
    pkgs.util-linux
    pkgs.uv
  ];
in
{
  packages = [
    pkgs.act
    pkgs.actionlint
    pkgs.basedpyright
    pkgs.git
    pkgs.git-cliff
    pkgs.jq
    pkgs.jujutsu
    pkgs.python3
    pkgs.shellcheck
    # The Codex hook-trust probe drives the TUI through tmux and skips without it.
    pkgs.tmux
    pkgs.uv
  ];

  # CI exports this closure to its cache so the bash build runs once per lock.
  env.LLM_WIKI_BASH32 = "${bash32}";

  tasks."llm-wiki:lint-workflows" = {
    exec = "actionlint";
    before = [ "devenv:enterTest" ];
  };

  # The shipped scripts are checked once per platform a user may run them on,
  # so an API missing on one of them is an error here. The floor Python and
  # the rule set live in pyrightconfig.json.
  tasks."llm-wiki:lint-python" = {
    exec = ''
      status=0
      for platform in Windows Darwin Linux; do
        echo "===== basedpyright: $platform ====="
        basedpyright --pythonplatform "$platform" || status=1
      done
      exit "$status"
    '';
    before = [ "devenv:enterTest" ];
  };

  tasks."llm-wiki:test" = {
    exec = "bash ./tests/run.sh";
    before = [ "devenv:enterTest" ];
  };

  # The same suite with the floor interpreters and git as the whole PATH.
  tasks."llm-wiki:test-floor" = {
    exec = ''
      PATH="${floorPath}" bash ./tests/run.sh
    '';
    before = [ "devenv:enterTest" ];
  };

  # Rehearse the GitHub workflow locally under act. The repo .actrc reuses the
  # job container between runs so only the first run installs Nix and builds
  # the floor interpreters.
  tasks."llm-wiki:ci" = {
    exec = "act push --workflows .github/workflows/ci.yml";
  };
}
