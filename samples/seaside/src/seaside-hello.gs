! GemStone file-in: Seaside Hello World
!
! A trivial Seaside component that renders a greeting.
! Assumes Seaside is already loaded in the stone (via GsDevKit).

doit
WAComponent subclass: #HelloApp
    instVarNames: #( greeting )
    classVars: #()
    classInstVars: #()
    poolDictionaries: #()
    inDictionary: UserGlobals
    category: 'SeasideHello'
%

category: 'initialization'
method: HelloApp
initialize
    super initialize.
    greeting := 'Hello from gspm!'
%

category: 'rendering'
method: HelloApp
renderContentOn: html
    html heading: greeting.
    html paragraph: 'This app was loaded by gspm.'
%

category: 'registration'
classmethod: HelloApp
canBeRoot
    ^ true
%

category: 'registration'
classmethod: HelloApp
description
    ^ 'Hello World (gspm)'
%

doit
  (WAAdmin register: HelloApp asApplicationAt: '/hello') preferenceAt: #sessionClass put: GsSession.
  System commitTransaction.
%
