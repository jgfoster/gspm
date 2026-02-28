! GemStone file-in: Counter tests

doit
TestCase subclass: #CounterTest
    instVarNames: #( counter )
    classVars: #()
    classInstVars: #()
    poolDictionaries: #()
    inDictionary: UserGlobals
    category: 'Counter-Tests'
%

category: 'running'
method: CounterTest
setUp
    counter := Counter named: 'test'
%

category: 'tests'
method: CounterTest
testInitialCount
    self assert: counter count = 0
%

category: 'tests'
method: CounterTest
testIncrement
    counter increment.
    self assert: counter count = 1.
    counter increment.
    self assert: counter count = 2.
%

category: 'tests'
method: CounterTest
testDecrement
    counter increment.
    counter increment.
    counter decrement.
    self assert: counter count = 1.
%

category: 'tests'
method: CounterTest
testReset
    counter increment.
    counter increment.
    counter reset.
    self assert: counter count = 0.
%

category: 'tests'
method: CounterTest
testName
    self assert: counter name = 'test'
%

category: 'tests'
method: CounterTest
testPrintString
    self assert: counter printString = 'test: 0'
%
