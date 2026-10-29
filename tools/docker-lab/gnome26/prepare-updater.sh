#!/bin/bash
# Export only committed public fixtures and updater code; never a user profile.
set -euo pipefail
here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo="$(git -C "$here" rev-parse --show-toplevel)"
ref="${1:-bc3abd444efb8065cf00607ff1ccb743e7ece5bf}"
commit="$(git -C "$repo" rev-parse --verify --end-of-options "${ref}^{commit}")"
context="$repo/tools/docker-lab/.runtime/gnome26-updater/context"
mkdir -p -- "$(dirname -- "$context")"
mkdir -m 700 -- "$context"
paths=(src/termia run_termia.py LICENSE
       tools/docker-lab/upgrade-preview/launch.py tools/docker-lab/upgrade-preview/reset.py)
git -C "$repo" ls-tree -r "$commit" -- "${paths[@]}" |
  awk '$1 != "100644" && $1 != "100755" { exit 1 }'
git -C "$repo" archive "$commit" -- "${paths[@]}" > "$context/source.tar"
mkdir "$context/export"
tar -xf "$context/source.tar" -C "$context/export"
mkdir "$context/review" "$context/fixtures"
mv "$context/export/src" "$context/export/run_termia.py" "$context/export/LICENSE" "$context/review/"
preview="$context/export/tools/docker-lab/upgrade-preview"
cp "$preview/reset.py" "$context/reset.py"
cp "$here/panel.py" "$context/panel.py"
grep -Fxq '# Register an actual polkit terminal agent for this app process and its descendants.' "$preview/launch.py"
grep -Fxq '    old_app.main([])' "$preview/launch.py"
sed '/^import subprocess$/d; /^# Register an actual polkit terminal agent/,$d' "$preview/launch.py" > "$context/launch.py"
printf '\nold_app.main([])\n' >> "$context/launch.py"
rm -r -- "$context/export" "$context/source.tar"
git -C "$repo" bundle create "$context/fixtures/releases.bundle" \
  refs/tags/v0.6.0-beta.3 refs/tags/v0.6.0-beta.4
download() {
  curl --fail --location --proto '=https' --proto-redir '=https' \
    --connect-timeout 15 --max-time 120 \
    "https://github.com/buuuki/termia/releases/download/$1/$2" -o "$context/fixtures/$3"
  printf '%s  %s\n' "$4" "$context/fixtures/$3" | sha256sum -c -
}
download v0.6.0-beta.3 termia_0.6.0.beta.3-1_all.deb beta3.deb \
  b0b1382abb505ab09f004a6b555f39b8b142c95a7d4dbe01052784f1151b0691
download v0.6.0-beta.4 termia_0.6.0.beta.4-1_all.deb termia_0.6.0.beta.4-1_all.deb \
  a8f1582fd70eb12510b29522fe164b23e38c0f69850e63a0908de6844fa995b3
for name in Dockerfile.updater updater-init.sh termia-lab-updater.service \
            configure-desktop.py org.termia.TestingLab.desktop; do
  cp "$here/$name" "$context/$name"
done
printf '%s\n' "$commit" > "$context/UPDATER_COMMIT"
printf '%s\n' '**' '!Dockerfile.updater' '!updater-init.sh' \
  '!termia-lab-updater.service' '!panel.py' '!launch.py' '!reset.py' \
  '!configure-desktop.py' '!org.termia.TestingLab.desktop' \
  '!UPDATER_COMMIT' '!review/' '!review/**' '!fixtures/' '!fixtures/**' > "$context/.dockerignore"
find "$context" -type d -exec chmod 755 {} +
find "$context" -type f -exec chmod 644 {} +
chmod 700 "$context"
printf 'Prepared updater %s in %s\n' "$commit" "$context"
