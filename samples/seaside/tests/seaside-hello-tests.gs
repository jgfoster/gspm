! GemStone file-in: Seaside Hello tests

doit
TestCase subclass: #HelloAppTest
    instVarNames: #()
    classVars: #()
    classInstVars: #()
    poolDictionaries: #()
    inDictionary: UserGlobals
    category: 'SeasideHello-Tests'
%

category: 'tests'
method: HelloAppTest
testCanBeRoot
    self assert: HelloApp canBeRoot
%

category: 'tests'
method: HelloAppTest
testRendersGreeting
    | html |
    html := HelloApp new renderContentOn: (WAHtmlCanvas new).
    self assert: (html includesSubString: 'Hello from Geode!')
%
