! GemStone file-in: Magritte descriptions for Contact
!
! Uses Magritte meta-descriptions to define the Contact model's
! fields, validation rules, and display properties.

category: 'magritte-descriptions'
method: Contact
descriptionFirstName
    ^ MAStringDescription new
        accessor: #firstName;
        label: 'First Name';
        priority: 100;
        beRequired;
        yourself
%

category: 'magritte-descriptions'
method: Contact
descriptionLastName
    ^ MAStringDescription new
        accessor: #lastName;
        label: 'Last Name';
        priority: 200;
        beRequired;
        yourself
%

category: 'magritte-descriptions'
method: Contact
descriptionEmail
    ^ MAStringDescription new
        accessor: #email;
        label: 'Email';
        priority: 300;
        yourself
%

category: 'magritte-descriptions'
method: Contact
descriptionPhone
    ^ MAStringDescription new
        accessor: #phone;
        label: 'Phone';
        priority: 400;
        yourself
%
