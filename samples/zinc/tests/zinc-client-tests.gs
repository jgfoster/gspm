! Tests for HttpHelper (Zinc client wrapper)

doit
TestCase subclass: #HttpHelperTest
    instVarNames: #()
    classVars: #()
    classInstVars: #()
    poolDictionaries: #()
    inDictionary: UserGlobals
    category: 'ZincClient-Tests'
%

category: 'tests'
method: HttpHelperTest
testBaseUrl
    | helper |
    helper := HttpHelper baseUrl: 'http://localhost:8080'.
    self assert: helper baseUrl equals: 'http://localhost:8080'.
%
