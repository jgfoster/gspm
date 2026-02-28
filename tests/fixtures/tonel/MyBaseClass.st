"A simple base class for testing"
Class {
    #name : #MyBaseClass,
    #superclass : #Object,
    #instVars : [ 'name', 'value' ],
    #classVars : [ 'DefaultName' ],
    #poolDictionaries : [],
    #category : #'MyApp-Core'
}

{ #category : #initialization }
MyBaseClass >> initialize [
    name := DefaultName.
    value := 0
]

{ #category : #accessing }
MyBaseClass >> name [
    ^ name
]

{ #category : #accessing }
MyBaseClass >> name: aString [
    name := aString
]

{ #category : #accessing }
MyBaseClass >> value [
    ^ value
]

{ #category : #accessing }
MyBaseClass >> value: anInteger [
    value := anInteger
]

{ #category : #initialization }
MyBaseClass class >> initialize [
    DefaultName := 'Unnamed'
]

{ #category : #'instance creation' }
MyBaseClass class >> named: aString [
    ^ self new name: aString; yourself
]
