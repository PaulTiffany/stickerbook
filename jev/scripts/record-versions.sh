#!/usr/bin/env bash
# Records exact upstream SHAs and toolchain versions for reproducibility.
set -u
B=/mnt/c/src/stickerbook/jev/PeTTa

echo "=== UPSTREAM COMMITS ==="
for name in PeTTa Omega petta_lib_chromadb; do
  case $name in
    PeTTa) p=$B ;;
    *)     p=$B/repos/$name ;;
  esac
  sha=$(git -C "$p" rev-parse HEAD 2>&1)
  date=$(git -C "$p" log -1 --format=%cI 2>&1)
  url=$(git -C "$p" config --get remote.origin.url 2>&1)
  tag=$(git -C "$p" describe --tags --always 2>&1)
  printf '%-20s %s\n' "$name" "$sha"
  printf '%-20s   date=%s  describe=%s\n' "" "$date" "$tag"
  printf '%-20s   url=%s\n' "" "$url"
done

echo
echo "=== TOOLCHAIN ==="
. /etc/os-release && echo "distro   : $PRETTY_NAME"
echo "kernel   : $(uname -r)"
echo "git      : $(git --version)"
echo "python3  : $(python3 --version 2>&1)"
echo "pip      : $(python3 -m pip --version 2>&1 | cut -d' ' -f1-2)"
if command -v swipl >/dev/null 2>&1; then
  echo "swipl    : $(swipl --version)"
else
  echo "swipl    : NOT INSTALLED"
fi
