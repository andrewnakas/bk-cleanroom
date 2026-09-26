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
# one orphan commit per deploy: the Pages builder chokes on a long history of 16 MB ROMs
cd /d/n64work/bk/site && git checkout -q --orphan tmp && git add -A && git commit -qm "Site: ${1:-rebuild}"   && git branch -D gh-pages -q 2>/dev/null; git branch -m gh-pages && git push -q -f origin gh-pages && git gc -q --prune=now   && gh api -X POST repos/andrewnakas/bk-cleanroom/pages/builds -q .status && echo "pushed gh-pages"
