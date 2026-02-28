"
A single todo item with a title, completion status, and priority.
"
Class {
	#name : #TodoItem,
	#superclass : #Object,
	#instVars : [
		'title',
		'completed',
		'priority',
		'createdAt'
	],
	#classVars : [],
	#poolDictionaries : [],
	#category : #TodoApp
}

{ #category : #'instance creation' }
TodoItem class >> title: aString [
	^ self new initializeTitle: aString
]

{ #category : #initialization }
TodoItem >> initializeTitle: aString [
	title := aString.
	completed := false.
	priority := 0.
	createdAt := DateAndTime now.
]

{ #category : #accessing }
TodoItem >> title [
	^ title
]

{ #category : #accessing }
TodoItem >> completed [
	^ completed
]

{ #category : #accessing }
TodoItem >> priority [
	^ priority
]

{ #category : #accessing }
TodoItem >> priority: anInteger [
	priority := anInteger
]

{ #category : #accessing }
TodoItem >> createdAt [
	^ createdAt
]

{ #category : #operations }
TodoItem >> complete [
	completed := true
]

{ #category : #operations }
TodoItem >> reopen [
	completed := false
]

{ #category : #testing }
TodoItem >> isOverdue [
	"Items older than 7 days without completion are overdue."
	^ completed not and: [
		(DateAndTime now - createdAt) days > 7 ]
]

{ #category : #printing }
TodoItem >> printOn: aStream [
	completed
		ifTrue: [ aStream nextPutAll: '[x] ' ]
		ifFalse: [ aStream nextPutAll: '[ ] ' ].
	aStream nextPutAll: title.
]
