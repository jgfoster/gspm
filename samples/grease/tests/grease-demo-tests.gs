! Tests for GreaseDemo

doit
TestCase subclass: #GreaseDemoTest
    instVarNames: #()
    classVars: #()
    classInstVars: #()
    poolDictionaries: #()
    inDictionary: UserGlobals
    category: 'GreaseDemo-Tests'
%

category: 'tests'
method: GreaseDemoTest
testPlatform
    self assert: (GreaseDemo printPlatform isKindOf: String).
%
