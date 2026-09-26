#!/bin/sh
# Rebuild the site from the clean ROM and push gh-pages (taint must pass first).
set -e
ROM=/d/n64work/bk/clean/build/us.v10/banjo.us.v10.z64
cd /d/n64work/bk-cleanroom
python -m games.bk.taint_report "/d/n64work/bk/rom/Banjo-Kazooie (USA) (Rev 1).z64" /d/n64work/bk/dirty /d/n64work/bk/clean/assets.clean.bin /d/n64work/bk/clean ${TAINT_ARGS:-} | tail -3
python ports/ejs/patch_core.py $ROM C:/Users/andre/n64work/mk64/emu/cores_orig /d/n64work/bk/emu/cores | tail -1
cd /d/n64work/bk/site && git rm -q -r --cached . >/dev/null 2>&1 || true
cd /d/n64work/bk-cleanroom && python ports/ejs/make_site.py $ROM C:/Users/andre/n64work/mk64/emu/ejs /d/n64work/bk/site
cp /d/n64work/bk/emu/cores/*.data /d/n64work/bk/site/data/cores/
cd /d/n64work/bk/site && git add -A && git commit -qm "Site update: ${1:-rebuild}" && git push -q -f origin gh-pages && echo "pushed gh-pages"
