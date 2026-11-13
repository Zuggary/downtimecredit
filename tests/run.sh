#!/bin/zsh
# Downtime Credit engine and store tests under jsc (no node on this Mac). Exit 0 = all pass.
# Reference cases come from the factory's research/TF2-test-cases.json (pass its path as $1 to override).
JSC=/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc
here="${0:A:h}"; site="${here:h}"
cases="${1:-${site:h:h}/research/TF2-test-cases.json}"
[[ -x $JSC ]] || { print "jsc not found"; exit 2; }
[[ -f $cases ]] || { print "reference cases not found: $cases"; exit 2; }
out=$($JSC "$here/test-engine.js" -- "$site" "$cases" 2>&1)
print -r -- "$out"
print -r -- "$out" | tail -1 | grep -q " 0 failed$" || exit 1
for f in engine.js store.js; do
  for w in '(^|[^.A-Za-z])document[.]' '(^|[^A-Za-z])fetch[(]' XMLHttpRequest '(^|[^A-Za-z])eval[(]' 'new Function' innerHTML cookie; do
    grep -Eq "$w" "$site/$f" && { print "$f matches $w"; exit 1; }
  done
done
grep -q "localStorage" "$site/engine.js" && { print "engine touches storage"; exit 1; }
print "static: engine and store have no DOM, network, eval or cookie; engine has no storage"
exit 0
