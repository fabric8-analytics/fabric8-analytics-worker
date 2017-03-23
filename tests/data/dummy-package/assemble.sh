#!/bin/bash

# this script creates an archive with files using different programming languages which contain many mistakes
# primary use for this is to use it with csmock worker
# it's also possible to add packaging stuff inside and test mercator on it (or other workers)

set -ue


cat >ugly.sh <<EOF
for i in \$(ls *.asdqwe); do
    some command \$i
done

cp \$file \$target

[ \$foo = "bar" ]

EOF

cat >ugly.py <<EOF

def x():
  pass

if name == main:
	f()

def f(x=[]):
  if x == None:
    x = 1

EOF

cat >ugly.js <<EOF
Math.pow(2, 53)+1 === Math.pow(2, 53)

var Thing = require('thing'),
    thing = new Thing(),
    stuff = thing.whatsit();

var Thing = require('thing')
var thing = new Thing()
var stuff = thing.whatsit()

var thing = null
var thingId = \$("#thing-id").val()
$.get("/thing/" + thingId, function(data){
  thing = data.thing
  console.log("got thing", thing)
}).fail(function(err){
  console.log("got error", err)
})

\$(".thing-name").text(thing)

if (x = 'hello world') console.log("winning!", x)
EOF

tar -c -f dummy.tar.gz ugly.*
rm ugly.*  # likely doesn't make sense to trap since it's done in a jiffy
