! GemStone file-in: Zinc HTTP client helper
!
! A thin wrapper around ZnClient that provides a convenient API
! for common HTTP operations in GemStone applications.

doit
Object subclass: #HttpHelper
    instVarNames: #( baseUrl )
    classVars: #()
    classInstVars: #()
    poolDictionaries: #()
    inDictionary: UserGlobals
    category: 'ZincClient'
%

category: 'instance creation'
classmethod: HttpHelper
baseUrl: aString
    ^ self new baseUrl: aString; yourself
%

category: 'accessing'
method: HttpHelper
baseUrl
    ^ baseUrl
%

category: 'accessing'
method: HttpHelper
baseUrl: aString
    baseUrl := aString
%

category: 'operations'
method: HttpHelper
get: aPath
    "Perform an HTTP GET and return the response body as a string."
    ^ (ZnClient new)
        url: baseUrl , aPath;
        get;
        yourself
%

category: 'operations'
method: HttpHelper
postJson: aPath body: aDictionary
    "POST a JSON body and return the response."
    ^ (ZnClient new)
        url: baseUrl , aPath;
        entity: (ZnEntity json: aDictionary asJson);
        post;
        yourself
%
