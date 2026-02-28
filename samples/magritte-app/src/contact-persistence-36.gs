! GemStone file-in: Contact persistence for GemStone 3.6.x
!
! Uses GemStone 3.6 persistence approach.

category: 'persistence'
method: Contact
save
    "Persist using 3.6 transaction model."
    UserGlobals at: #ContactStore ifAbsent: [
        UserGlobals at: #ContactStore put: IdentityBag new ].
    (UserGlobals at: #ContactStore) add: self.
    System commitTransaction.
%
