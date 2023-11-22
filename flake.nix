{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    poetry2nix = {
      url = "github:nix-community/poetry2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, poetry2nix }:
    let
      pkgs = nixpkgs.legacyPackages.x86_64-linux;
      inherit (poetry2nix.lib.mkPoetry2Nix { inherit pkgs; }) mkPoetryApplication mkPoetryEnv defaultPoetryOverrides;
      p2n-overrides = defaultPoetryOverrides.extend (self: super: {
        instagrapi = super.instagrapi.overridePythonAttrs
          (old: { buildInputs = (old.buildInputs or [ ]) ++ [ super.setuptools ]; });
      });
    in
    {
      packages.x86_64-linux.ig-story-fetcher = mkPoetryApplication {
        projectDir = self;
        python = pkgs.python311;
        overrides = p2n-overrides;
      };
      packages.x86_64-linux.default = self.packages.x86_64-linux.ig-story-fetcher;

      devShells.x86_64-linux.default = pkgs.mkShellNoCC {
        packages = with pkgs; [
          (mkPoetryEnv {
            projectDir = self;
            python = pkgs.python311;
            overrides = p2n-overrides;
          })
          poetry
          python311
        ];
      };

      nixosModules.ig-story-fetcher = import ./modules/ig-story-fetcher.nix;
      nixosModules.default = self.nixosModules.ig-story-fetcher;

      overlays.default = _: _: {
        ig-story-fetcher = self.packages.x86_64-linux.ig-story-fetcher;
      };
    };
}
