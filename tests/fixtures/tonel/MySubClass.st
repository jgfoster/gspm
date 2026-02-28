"A subclass that extends MyBaseClass"
Class {
    #name : #MySubClass,
    #superclass : #MyBaseClass,
    #instVars : [ 'extra' ],
    #classVars : [],
    #poolDictionaries : [],
    #category : #'MyApp-Core'
}

{ #category : #accessing }
MySubClass >> extra [
    ^ extra
]

{ #category : #accessing }
MySubClass >> extra: anObject [
    extra := anObject
]
