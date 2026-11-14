#!/bin/zsh
# Downtime Credit engine, store, and flights tests under jsc (no node on this Mac). Exit 0 = all pass.
# Reference cases come from research/TF2-test-cases.json when present, or tests/fixtures/tf2-test-cases.json (pass $1 to override).
JSC=/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc
here="${0:A:h}"; site="${here:h}"
default_cases="${site:h:h}/research/TF2-test-cases.json"
[[ -f $default_cases ]] || default_cases="$here/fixtures/tf2-test-cases.json"
cases="${1:-$default_cases}"
gsrc="${site:h:h}/research/TF2-google-sla-source.txt"
[[ -f $gsrc ]] || gsrc="$here/fixtures/tf2-google-sla-source.txt"
gcases="${site:h:h}/research/TF2-google-cases.json"
[[ -f $gcases ]] || gcases="$here/fixtures/tf2-google-cases.json"
[[ -x $JSC ]] || { print "jsc not found"; exit 2; }
[[ -f $cases ]] || { print "reference cases not found: $cases"; exit 2; }
out=$($JSC "$here/test-engine.js" -- "$site" "$cases" "$gsrc" "$gcases" 2>&1)
print -r -- "$out"
print -r -- "$out" | tail -1 | grep -q " 0 failed$" || exit 1
fout=$(cd "$site" && $JSC "$site/flights/flights.js" "$here/test-flights.js" 2>&1)
print -r -- "$fout"
print -r -- "$fout" | tail -1 | grep -q " 0 failed$" || exit 1
for f in engine.js store.js; do
  for w in '(^|[^.A-Za-z])document[.]' '(^|[^A-Za-z])fetch[(]' XMLHttpRequest '(^|[^A-Za-z])eval[(]' 'new Function' innerHTML cookie; do
    grep -Eq "$w" "$site/$f" && { print "$f matches $w"; exit 1; }
  done
done
grep -q "localStorage" "$site/engine.js" && { print "engine touches storage"; exit 1; }
pout=$(cd "$site" && /usr/bin/python3 -I "$here/test_pages.py" 2>&1); print -r -- "$pout" | tail -3
print -r -- "$pout" | tail -1 | grep -q " 0 failed$" || exit 1
h0=$(cd "$site" && cat sla/index.html sla/*/index.html flights/airlines/*/index.html guides/index.html guides/*/index.html sitemap.xml | shasum); (cd "$site" && /usr/bin/python3 -I tools/build_pages.py >/dev/null && /usr/bin/python3 -I tools/build_airlines.py >/dev/null && /usr/bin/python3 -I tools/build_surplus.py >/dev/null && /usr/bin/python3 -I tools/build_unclaimed.py >/dev/null && /usr/bin/python3 -I tools/build_guides.py >/dev/null); h1=$(cd "$site" && cat sla/index.html sla/*/index.html flights/airlines/*/index.html guides/index.html guides/*/index.html sitemap.xml | shasum); [[ "$h0" == "$h1" ]] || { print "generated pages differ from a fresh build (run both tools)"; exit 1; }
print "static: engine and store have no DOM, network, eval or cookie; engine has no storage"
exit 0
