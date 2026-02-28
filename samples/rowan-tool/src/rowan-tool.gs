! GemStone file-in: Rowan Tool — project introspection utilities
!
! Provides helper methods for listing loaded Rowan projects,
! packages, and their modification status.

doit
Object subclass: #RowanInspector
    instVarNames: #()
    classVars: #()
    classInstVars: #()
    poolDictionaries: #()
    inDictionary: UserGlobals
    category: 'RowanTool'
%

category: 'queries'
classmethod: RowanInspector
listProjects
    "Answer a collection of project name -> version associations."
    ^ Rowan projectNames collect: [:name |
        | project |
        project := Rowan projectNamed: name.
        name -> project loadedCommitId ]
%

category: 'queries'
classmethod: RowanInspector
packagesFor: projectName
    "Answer the packages loaded for a given project."
    ^ (Rowan projectNamed: projectName) packageNames
%

category: 'queries'
classmethod: RowanInspector
modifiedPackages
    "Answer packages that have been modified since their last commit."
    | modified |
    modified := OrderedCollection new.
    Rowan projectNames do: [:name |
        | project |
        project := Rowan projectNamed: name.
        project packageNames do: [:pkgName |
            (project isPackageModified: pkgName) ifTrue: [
                modified add: pkgName ]]].
    ^ modified
%

category: 'reporting'
classmethod: RowanInspector
printReport
    "Print a summary of all loaded Rowan projects."
    self listProjects do: [:assoc |
        GsFile gciLogServer: assoc key , ' @ ' , assoc value.
        (self packagesFor: assoc key) do: [:pkg |
            GsFile gciLogServer: '  - ' , pkg ]].
%
