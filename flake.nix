{
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
  inputs.flake-utils.url = "github:numtide/flake-utils";

  outputs = { self, nixpkgs, flake-utils }:
    let
      localOverlay = final: prev: {
        ig-story-fetcher = prev.poetry2nix.mkPoetryApplication {
          projectDir = self;
          python = prev.python311;
          overrides = prev.poetry2nix.defaultPoetryOverrides.extend (self: super: {
            instagrapi = super.instagrapi.overridePythonAttrs
              (old: { buildInputs = (old.buildInputs or [ ]) ++ [ super.setuptools ]; });
          });
        };
      };

      pkgsForSystem = system: import nixpkgs {
        inherit system;
        overlays = [ localOverlay ];
      };
    in
    flake-utils.lib.eachDefaultSystem
      (system: rec
      {
        legacyPackages = pkgsForSystem system;

        packages = rec {
          inherit (legacyPackages) ig-story-fetcher;
          default = ig-story-fetcher;
        };

        devShells.default = legacyPackages.mkShell {
          packages = with legacyPackages; [
            poetry
            python311
          ];
        };

        apps.ig-story-fetcher = flake-utils.lib.mkApp { drv = packages.ig-story-fetcher; };
      }) // rec {
      nixosModules.ig-story-fetcher = import ./modules/ig-story-fetcher.nix;
      nixosModules.default = nixosModules.ig-story-fetcher;

      overlays.default = localOverlay;
    };
}
