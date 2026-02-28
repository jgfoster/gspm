"
A persistent collection of TodoItems with query methods.
"
Class {
	#name : #TodoList,
	#superclass : #Object,
	#instVars : [
		'name',
		'items'
	],
	#classVars : [],
	#poolDictionaries : [],
	#category : #TodoApp
}

{ #category : #'instance creation' }
TodoList class >> named: aString [
	^ self new initializeNamed: aString
]

{ #category : #initialization }
TodoList >> initializeNamed: aString [
	name := aString.
	items := OrderedCollection new.
]

{ #category : #accessing }
TodoList >> name [
	^ name
]

{ #category : #accessing }
TodoList >> items [
	^ items copy
]

{ #category : #accessing }
TodoList >> size [
	^ items size
]

{ #category : #operations }
TodoList >> add: aTitleString [
	| item |
	item := TodoItem title: aTitleString.
	items add: item.
	^ item
]

{ #category : #operations }
TodoList >> addWithPriority: aTitleString priority: anInteger [
	| item |
	item := self add: aTitleString.
	item priority: anInteger.
	^ item
]

{ #category : #operations }
TodoList >> remove: aTodoItem [
	items remove: aTodoItem ifAbsent: []
]

{ #category : #queries }
TodoList >> pending [
	^ items reject: [:each | each completed]
]

{ #category : #queries }
TodoList >> completed [
	^ items select: [:each | each completed]
]

{ #category : #queries }
TodoList >> overdue [
	^ items select: [:each | each isOverdue]
]

{ #category : #queries }
TodoList >> byPriority [
	^ items asSortedCollection: [:a :b | a priority > b priority]
]

{ #category : #printing }
TodoList >> printOn: aStream [
	aStream
		nextPutAll: name;
		nextPutAll: ' (';
		print: self pending size;
		nextPutAll: ' pending, ';
		print: self completed size;
		nextPutAll: ' done)'.
]
