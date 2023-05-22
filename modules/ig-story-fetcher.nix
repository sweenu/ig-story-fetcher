{ config, lib, pkgs, ... }:

with lib;

let
  cfg = config.services.ig-story-fetcher;
in
{
  options.services.ig-story-fetcher = {
    enable = mkEnableOption "ig-story-fetcher";

    settingsPath = mkOption {
      type = types.path;
    };
    schedule = mkOption {
      type = types.str;
      default = "12h";
      example = "Mon, 00:00:00";
    };
    randomizedDelaySec = mkOption {
      default = "0";
      example = "45min";
      type = types.str;
      description = mdDoc ''
        Add a randomized delay before each run.
        The delay will be chosen between zero and this value.
        This value must be a time span in the format specified by
        {manpage}`systemd.time(7)`
      '';
    };
    persistent = mkOption {
      default = true;
      type = types.bool;
      example = false;
      description = mdDoc ''
        Takes a boolean argument. If true, the time when the service
        unit was last triggered is stored on disk. When the timer is
        activated, the service unit is triggered immediately if it
        would have been triggered at least once during the time when
        the timer was inactive. Such triggering is nonetheless
        subject to the delay imposed by RandomizedDelaySec=. This is
        useful to catch up on missed runs of the service when the
        system was powered down.
      '';
    };
  };

  config = mkIf cfg.enable {
    systemd.services.ig-story-fetcher = {
      path = [ pkgs.ffmpeg_5 ];
      serviceConfig = {
        ExecStart = "${pkgs.ig-story-fetcher}/bin/ig-story-fetcher ${cfg.settingsPath}";
      };
      startAt = cfg.schedule;
    };
    systemd.timers.ig-story-fetcher = {
      timerConfig = {
        RandomizedDelaySec = cfg.randomizedDelaySec;
        Persistent = cfg.persistent;
      };
    };
  };
}
