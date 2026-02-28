Extension { #name : #String }

{ #category : #'*MyApp' }
String >> asMyBase [
    ^ MyBaseClass named: self
]

{ #category : #'*MyApp' }
String >> isMyAppString [
    ^ true
]
