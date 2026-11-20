#!/bin/sh
# Opens the Hungry Hippos arena in Webots.
cd "$(dirname "$0")" || exit 1
WORLD="$PWD/worlds/hungry_hippos.wbt"
case "$(uname)" in
  Darwin)
    # The nightly build works on newer macOS versions where R2025a can't start.
    for app in "$HOME/Applications/Webots-nightly.app" "/Applications/Webots-nightly.app" \
               "$HOME/Applications/Webots.app" "/Applications/Webots.app"; do
      if [ -d "$app" ]; then exec open -a "$app" "$WORLD"; fi
    done
    echo "Webots isn't installed: see the README" >&2; exit 1 ;;
  *)
    exec webots "$WORLD" ;;
esac
