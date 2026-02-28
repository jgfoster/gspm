! GemStone file-in: Grease portability demo
!
! Demonstrates using Grease's platform-portable API for common
! operations: string manipulation, collection helpers, and codecs.

doit
Object subclass: #GreaseDemo
    instVarNames: #()
    classVars: #()
    classInstVars: #()
    poolDictionaries: #()
    inDictionary: UserGlobals
    category: 'GreaseDemo'
%

category: 'examples'
classmethod: GreaseDemo
urlEncodeExample
    "Use Grease's codec API to URL-encode a string."
    ^ 'Hello World & Goodbye' encodeAsUTF8
%

category: 'examples'
classmethod: GreaseDemo
printPlatform
    "Print the current Grease platform name."
    ^ GRPlatform current label
%
