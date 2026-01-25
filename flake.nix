{
  description = "Sync Gradescope assignments and Canvas Planner tasks to CalDAV";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";
    flake-utils.url = "github:numtide/flake-utils";
    gradescope-api.url = "github:nyuoss/gradescope-api";
    gradescope-api.flake = false;
  };

  outputs = { self, nixpkgs, flake-utils, gradescope-api }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        gradescopeapi = pkgs.python3Packages.buildPythonPackage {
          version = "0.0.1";
          pname = "gradescopeapi";
          pyproject = true;
          src = gradescope-api;
          build-system = with pkgs.python3Packages; [
            hatchling
          ];
          dependencies = with pkgs.python3Packages; [
            beautifulsoup4
            fastapi
            pytest
            python-dateutil
            python-dotenv
            requests-toolbelt
            requests
            tzdata
          ];
        };
        python = pkgs.python3.withPackages (p: [
          gradescopeapi
          p.caldav
          p.icalendar
        ]);
        pkg = pkgs.writeShellScriptBin "caldav-canvas-gradescope" ''
          ${python.interpreter} ${toString ./.}/main.py "$@"
        '';
      in {
        devShells.default = pkgs.mkShell {
          packages = [ python ];
        };

        packages.default = pkg;

        apps.default = {
          type = "app";
          program = "${pkg}/bin/caldav-canvas-gradescope";
        };
      }
    );
}
