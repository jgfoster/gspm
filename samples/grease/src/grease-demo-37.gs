! GemStone 3.7+ conditional extensions for GreaseDemo.
!
! Loaded only on GemStone >= 3.7 where new Unicode APIs are available.

category: 'examples'
classmethod: GreaseDemo
unicodeNormalize: aString
    "Normalize a Unicode string using GemStone 3.7+ ICU support."
    ^ aString asUnicodeString
%
