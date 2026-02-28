! GemStone file-in: Persistent counter
!
! A trivial class that demonstrates GemStone's transparent persistence.
! Create a Counter, increment it, commit, restart your session — the
! count is still there.

doit
Object subclass: #Counter
    instVarNames: #( count name )
    classVars: #()
    classInstVars: #()
    poolDictionaries: #()
    inDictionary: UserGlobals
    category: 'Counter'
%

category: 'instance creation'
classmethod: Counter
named: aString
    ^ self new initializeNamed: aString
%

category: 'initialization'
method: Counter
initializeNamed: aString
    name := aString.
    count := 0.
%

category: 'accessing'
method: Counter
count
    ^ count
%

category: 'accessing'
method: Counter
name
    ^ name
%

category: 'operations'
method: Counter
increment
    count := count + 1.
    ^ count
%

category: 'operations'
method: Counter
decrement
    count := count - 1.
    ^ count
%

category: 'operations'
method: Counter
reset
    count := 0
%

category: 'printing'
method: Counter
printOn: aStream
    aStream
        nextPutAll: name;
        nextPutAll: ': ';
        print: count
%
