! GemStone file-in: Contact manager tests

doit
TestCase subclass: #ContactTest
    instVarNames: #()
    classVars: #()
    classInstVars: #()
    poolDictionaries: #()
    inDictionary: UserGlobals
    category: 'ContactManager-Tests'
%

category: 'tests'
method: ContactTest
testCreateContact
    | c |
    c := Contact new.
    c firstName: 'Ada'.
    c lastName: 'Lovelace'.
    self assert: c firstName = 'Ada'.
    self assert: c lastName = 'Lovelace'.
%

category: 'tests'
method: ContactTest
testDescription
    | c descriptions |
    c := Contact new.
    descriptions := c magritteDescription children.
    self assert: descriptions size = 4.
    self assert: (descriptions anySatisfy: [:d | d label = 'First Name']).
%

category: 'tests'
method: ContactTest
testPrintString
    | c |
    c := Contact new firstName: 'Grace'; lastName: 'Hopper'.
    self assert: c printString = 'Grace Hopper'.
%
