! GemStone file-in: Todo app tests

doit
TestCase subclass: #TodoItemTest
    instVarNames: #( item )
    classVars: #()
    classInstVars: #()
    poolDictionaries: #()
    inDictionary: UserGlobals
    category: 'TodoApp-Tests'
%

category: 'running'
method: TodoItemTest
setUp
    item := TodoItem title: 'Buy milk'
%

category: 'tests'
method: TodoItemTest
testTitle
    self assert: item title = 'Buy milk'
%

category: 'tests'
method: TodoItemTest
testInitiallyNotCompleted
    self deny: item completed
%

category: 'tests'
method: TodoItemTest
testComplete
    item complete.
    self assert: item completed
%

category: 'tests'
method: TodoItemTest
testReopen
    item complete.
    item reopen.
    self deny: item completed
%

doit
TestCase subclass: #TodoListTest
    instVarNames: #( list )
    classVars: #()
    classInstVars: #()
    poolDictionaries: #()
    inDictionary: UserGlobals
    category: 'TodoApp-Tests'
%

category: 'running'
method: TodoListTest
setUp
    list := TodoList named: 'Groceries'
%

category: 'tests'
method: TodoListTest
testAdd
    list add: 'Eggs'.
    self assert: list size = 1
%

category: 'tests'
method: TodoListTest
testPending
    | item |
    list add: 'Eggs'.
    item := list add: 'Bread'.
    item complete.
    self assert: list pending size = 1.
    self assert: list completed size = 1.
%

category: 'tests'
method: TodoListTest
testByPriority
    | low high sorted |
    low := list addWithPriority: 'Low' priority: 1.
    high := list addWithPriority: 'High' priority: 10.
    sorted := list byPriority.
    self assert: sorted first = high.
%
