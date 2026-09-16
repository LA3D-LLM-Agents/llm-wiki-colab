{ pkgs, inputs, ... }:

let
  # The shipped hooks run under whatever the user's machine has, and stock
  # macOS ships bash 3.2.57 and Python 3.9. No current distribution packages
  # bash 3.2, so it is built from source here; Python 3.9 comes from the last
  # nixpkgs release that carried it, which cache.nixos.org still serves.
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
in
{
  packages = [
    pkgs.act
    pkgs.actionlint
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

  tasks."llm-wiki:test" = {
    exec = "bash ./tests/run.sh";
    before = [ "devenv:enterTest" ];
  };

  # The same suite with the floor interpreters first on PATH.
  tasks."llm-wiki:test-floor" = {
    exec = ''
      floor="$(mktemp -d)"
      trap 'rm -rf "$floor"' EXIT
      ln -s ${bash32}/bin/bash "$floor/bash"
      PATH="$floor:${python39}/bin:$PATH" bash ./tests/run.sh
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
