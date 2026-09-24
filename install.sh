#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
set -euo pipefail

PREFIX="${XDG_DATA_HOME:-$HOME/.local/share}/flydigi-apex4"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
ENV_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/environment.d"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/flydigi-apex4"
RULE_SRC="udev/72-apex4-ds5.rules"
RULE_DST="/etc/udev/rules.d/72-apex4-ds5.rules"
SELF="$(cd "$(dirname "$0")" && pwd)"

hide_pad=1
desktop=0
check_only=0
uninstall=0
force=0
for arg in "$@"; do
  case "$arg" in
    --hide-pad) hide_pad=1 ;;
    --no-hide-pad) hide_pad=0 ;;
    --desktop) desktop=1 ;;
    --check) check_only=1 ;;
    --force) force=1 ;;
    --uninstall) uninstall=1 ;;
    -h|--help)
      cat <<EOF
usage: ./install.sh [--check] [--no-hide-pad] [--desktop] [--force] [--uninstall]

  --check      run the self-test and change nothing
  --force      install even if the self-test fails -- for setting a machine up
               before the pad is plugged in
  --desktop    also drop two launchers on the desktop: one to turn the
               boot-time autostart on or off, one to start and stop the relay
               right now. Needs a Desktop directory; harmless if there is none
  --no-hide-pad
               leave the physical pad visible to SDL. By default it is hidden, so
               Steam offers only the virtual controller and Steam Input can stay
               on. The hiding is why the autostart unit is enabled: with the pad
               hidden and the relay stopped there is no controller at all.
  --uninstall  remove everything this script installs, including the settings
               file, and put the machine back as it was
EOF
      exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

command -v python3 >/dev/null || { echo "python3 is required" >&2; exit 1; }

unit_active() {
  local unit="$1" state rc
  if state="$(systemctl --user is-active "$unit" 2>/dev/null)"; then
    if [ "$state" = active ]; then
      return 0
    fi
    echo "could not verify $unit state: $state" >&2
    return 2
  else
    rc=$?
  fi
  case "$state:$rc" in
    inactive:3|inactive:4|failed:3|unknown:3|unknown:4) return 1 ;;
    *)
      echo "could not verify $unit state" >&2
      return 2
      ;;
  esac
}

wait_stopped() {
  local unit="$1" i rc
  for i in $(seq 1 20); do
    if unit_active "$unit"; then
      sleep 0.25
      continue
    else
      rc=$?
    fi
    case "$rc" in
      1) return 0 ;;
      *) return 1 ;;
    esac
  done
  echo "$unit did not stop within 5 seconds" >&2
  return 1
}

stop_user_unit() {
  local unit="$1"
  systemctl --user stop "$unit" 2>/dev/null || true
  wait_stopped "$unit"
}

if [ "$check_only" = 1 ]; then
  exec python3 "$SELF/tools/selftest.py"
fi

if [ "$uninstall" = 1 ]; then
  echo "==> stopping and removing the service"
  # The transient profile/game relay can own the same physical writer without
  # being enabled. Stop it before deleting the runtime it is executing.
  stop_user_unit apex4-relay-manual.service
  # Older names this project used, so an upgrade-then-uninstall leaves nothing.
  for unit in flydigi-apex4 flydigi-legacy-ds5 apex4-ds5; do
    systemctl --user disable --now "$unit" 2>/dev/null || true
    wait_stopped "$unit"
    rm -f "$UNIT_DIR/$unit.service"
  done
  systemctl --user daemon-reload || true

  echo "==> silencing the motors"
  # Services attempt their own reset first; this is the bounded final fallback.
  python3 "$PREFIX/tools/rumble-off.py" 2>/dev/null \
    || python3 "$SELF/tools/rumble-off.py" 2>/dev/null \
    || echo "    (no pad on the bus, nothing to silence)"

  echo "==> removing files"
  rm -rf "$PREFIX"
  rm -f "$ENV_DIR/apex4-ds5.conf"
  rm -f "$CONFIG_DIR/config.json"
  rmdir "$CONFIG_DIR" 2>/dev/null || true
  # The launchers point into $PREFIX, so they go with it.
  rm -f "$HOME/Desktop/apex4-autostart.desktop" "$HOME/Desktop/apex4-relay.desktop"

  echo "==> removing the parts that need root"
  if sudo sh -c "rm -f '$RULE_DST' /etc/modules-load.d/uhid.conf && \
                 udevadm control --reload && \
                 udevadm trigger --subsystem-match=input --subsystem-match=hidraw \
                                 --subsystem-match=misc"; then
    echo "    ok"
  else
    echo "    could not; do it by hand:" >&2
    echo "      sudo rm -f $RULE_DST /etc/modules-load.d/uhid.conf" >&2
    echo "      sudo udevadm control --reload" >&2
  fi

  echo
  echo "Done. The uhid module is left loaded -- harmless, and it will simply not"
  echo "load by itself after a reboot any more."
  if [ -f "$ENV_DIR/apex4-ds5.conf" ]; then
    echo "NOTE: could not remove $ENV_DIR/apex4-ds5.conf -- the pad stays hidden."
  else
    echo "Restart Steam so it sees the physical pad again."
  fi
  exit 0
fi

echo "==> checking this machine first"
if ! python3 "$SELF/tools/selftest.py"; then
  if [ "$force" = 0 ]; then
    echo
    echo "Self-test failed. Installing anyway would just move the failure later;"
    echo "fix the above, or run with --check to see it again. If the pad simply"
    echo "is not plugged in yet, --force installs regardless."
    exit 1
  fi
  echo
  echo "    self-test failed; continuing because --force was given"
fi

echo "==> staging complete runtime for $PREFIX"
mkdir -p "$(dirname "$PREFIX")" "$UNIT_DIR"
stage="$(mktemp -d "${PREFIX}.new.XXXXXX")"
cleanup_stage() {
  if [ -n "${stage:-}" ] && [ -d "$stage" ]; then
    rm -rf -- "$stage"
  fi
}
trap cleanup_stage EXIT
# systemd/ and the two control scripts come along so that the installed tree can
# regenerate its own unit file and the desktop launchers keep working if the
# checkout is moved or deleted.
cp -r "$SELF/apex4ds5" "$SELF/apex4-ds5" "$SELF/tools" "$SELF/systemd" \
      "$SELF/apex4-autostart" "$SELF/apex4-relay" \
      "$SELF/LICENSE" "$SELF/THIRD_PARTY_NOTICES.md" "$stage/"
python3 -m py_compile "$stage/apex4-ds5" "$stage"/apex4ds5/*.py \
        "$stage"/apex4ds5/_ds5/*.py "$stage"/tools/*.py

echo "==> stopping existing relay before atomic upgrade"
stop_user_unit apex4-relay-manual.service
stop_user_unit flydigi-apex4.service

backup=""
if [ -e "$PREFIX" ]; then
  backup="$(mktemp -d "${PREFIX}.backup.XXXXXX")"
  rmdir "$backup"
  mv "$PREFIX" "$backup"
fi
mv "$stage" "$PREFIX"
stage=""
echo "    installed complete runtime"
if [ -n "$backup" ]; then
  echo "    previous runtime retained at $backup"
fi

rollback_pending=1
rollback_upgrade() {
  local rc="${1:-1}" failed
  trap - ERR
  [ "$rollback_pending" = 1 ] || exit "$rc"
  echo "    new service failed; restoring previous runtime" >&2
  systemctl --user stop flydigi-apex4.service 2>/dev/null || true
  failed="$(mktemp -d "${PREFIX}.failed.XXXXXX")"
  rmdir "$failed"
  mv "$PREFIX" "$failed"
  if [ -n "$backup" ]; then
    mv "$backup" "$PREFIX"
  fi
  systemctl --user daemon-reload || true
  if [ -n "$backup" ]; then
    systemctl --user restart flydigi-apex4.service 2>/dev/null || true
  fi
  echo "    failed runtime retained at $failed" >&2
  exit "$rc"
}
trap 'rollback_upgrade $?' ERR

echo "==> user service"
sed "s|%PREFIX%|$PREFIX|g" "$SELF/systemd/flydigi-apex4.service" \
  > "$UNIT_DIR/flydigi-apex4.service"
systemctl --user daemon-reload

echo "==> udev rule (needs root; this is the only step that does)"
if sudo cp "$SELF/$RULE_SRC" "$RULE_DST"; then
  sudo udevadm control --reload
  # misc matters as much as the other two: /dev/uhid lives there, and on SteamOS
  # it comes up root-only, so without this the rule takes effect only at the next
  # reboot. On Fedora-derived systems the node is already open to everyone, which
  # is why this went unnoticed.
  sudo udevadm trigger --subsystem-match=input --subsystem-match=hidraw \
                       --subsystem-match=misc
else
  echo "could not install the rule; do it by hand:" >&2
  echo "  sudo cp $SELF/$RULE_SRC $RULE_DST && sudo udevadm control --reload" >&2
fi

echo "==> making sure uhid is loaded, now and at boot"
if sudo sh -c 'modprobe uhid && printf "uhid\n" > /etc/modules-load.d/uhid.conf'; then
  echo "    ok"
else
  echo "    could not; do it by hand if the self-test complains about uhid:" >&2
  echo "      sudo modprobe uhid && echo uhid | sudo tee /etc/modules-load.d/uhid.conf" >&2
fi

if [ "$hide_pad" = 1 ]; then
  echo "==> hiding the physical pad from SDL"
  mkdir -p "$ENV_DIR"
  cp "$SELF/env/apex4-ds5.conf" "$ENV_DIR/"
  echo "    Takes effect for programs started after this. A running Steam keeps"
  echo "    the environment it launched with, so restart it -- on a Steam Deck,"
  echo "    where Steam is part of the session, reboot."
else
  echo "==> leaving physical pad visible to SDL"
  rm -f "$ENV_DIR/apex4-ds5.conf"
fi

echo "==> default settings file"
python3 "$PREFIX/apex4-ds5" --write-config || true

echo "==> enabling autostart"
if ! systemctl --user enable flydigi-apex4.service \
    || ! systemctl --user restart flydigi-apex4.service \
    || ! unit_active flydigi-apex4.service; then
  rollback_upgrade 1
fi
rollback_pending=0
trap - ERR

if [ "$desktop" = 1 ]; then
  echo "==> desktop launchers"
  desktop_dir="$HOME/Desktop"
  if command -v xdg-user-dir >/dev/null 2>&1; then
    desktop_dir="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"
  fi
  if [ -d "$desktop_dir" ]; then
    for name in apex4-autostart apex4-relay; do
      sed "s|%PREFIX%|$PREFIX|g" "$SELF/desktop/$name.desktop" \
        > "$desktop_dir/$name.desktop"
      chmod +x "$desktop_dir/$name.desktop"
      if command -v gio >/dev/null 2>&1; then
        gio set "$desktop_dir/$name.desktop" metadata::trusted true 2>/dev/null || true
      fi
    done
    echo "    $desktop_dir/apex4-autostart.desktop"
    echo "    $desktop_dir/apex4-relay.desktop"
  else
    echo "    no Desktop directory at $desktop_dir; skipped" >&2
  fi
fi

echo
echo "Done. Status:  systemctl --user status flydigi-apex4"
echo "Logs:          journalctl --user -u flydigi-apex4 -f"
if [ "$hide_pad" = 1 ]; then
  echo
  echo "Note: with --hide-pad, stopping the relay leaves no controller at all."
fi
