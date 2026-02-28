! GemStone file-in: Contact persistence for GemStone >= 3.7
!
! Uses GemStone 3.7+ persistence features.

category: 'persistence'
method: Contact
save
    "Persist using 3.7 transaction model."
    UserGlobals at: #ContactStore ifAbsent: [
        UserGlobals at: #ContactStore put: RcIdentityBag new ].
    (UserGlobals at: #ContactStore) add: self.
    System commitTransaction.
%
