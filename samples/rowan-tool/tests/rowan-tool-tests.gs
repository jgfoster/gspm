! GemStone file-in: Rowan Tool tests

doit
TestCase subclass: #RowanInspectorTest
    instVarNames: #()
    classVars: #()
    classInstVars: #()
    poolDictionaries: #()
    inDictionary: UserGlobals
    category: 'RowanTool-Tests'
%

category: 'tests'
method: RowanInspectorTest
testListProjects
    | projects |
    projects := RowanInspector listProjects.
    self assert: projects isKindOf: Collection.
%

category: 'tests'
method: RowanInspectorTest
testModifiedPackages
    | modified |
    modified := RowanInspector modifiedPackages.
    self assert: modified isKindOf: Collection.
%
