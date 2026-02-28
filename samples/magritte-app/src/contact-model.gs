! GemStone file-in: Contact model
!
! Domain objects for a simple contact manager.

doit
Object subclass: #Contact
    instVarNames: #( firstName lastName email phone )
    classVars: #()
    classInstVars: #()
    poolDictionaries: #()
    inDictionary: UserGlobals
    category: 'ContactManager-Model'
%

category: 'accessing'
method: Contact
firstName
    ^ firstName
%

category: 'accessing'
method: Contact
firstName: aString
    firstName := aString
%

category: 'accessing'
method: Contact
lastName
    ^ lastName
%

category: 'accessing'
method: Contact
lastName: aString
    lastName := aString
%

category: 'accessing'
method: Contact
email
    ^ email
%

category: 'accessing'
method: Contact
email: aString
    email := aString
%

category: 'accessing'
method: Contact
phone
    ^ phone
%

category: 'accessing'
method: Contact
phone: aString
    phone := aString
%

category: 'printing'
method: Contact
printOn: aStream
    aStream
        nextPutAll: firstName;
        nextPut: $ ;
        nextPutAll: lastName
%
