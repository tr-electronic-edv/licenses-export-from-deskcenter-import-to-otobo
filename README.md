IF you have a lot of software contracts and licenses saved in Deskcenter IT-Service-Management program,  
AND you want to migrate them into the Otobo CMDB (free equivalent of Deskcenter),  
AND you've found, that the Deskcenter export DOES NOT save
  - the software keys tied to licenses
  - the relationship to the license contracts

THEN you may want to use this code.

As an administrator, you have the access to the Deskcenter DB and you can grep the list of contracts and/or licenses using SQL.


# Extract licenses from Deskcenter
Use the `export_from_deskcenter.sql` to get the list of 
- Contracts
- associated Licenses
- associated software Keys, license quantity, end date, user

# Transform
Save the table in a CSV file, manually check the data is correct, maybe delete outdated or obsolete contracts and licenses.

# Load licenses to Otobo CMDB
Make a backup of the Otobo DB.

Use `import_to_otobo.py` to load data into the Otobo CMDB
- Otobo CMDB plugin should be installed in advance
- use your own Otobo DB credentials
- links between software contracts and associated licenses will be created automatically
- associated keys, quantities, uses will be saved into the license details, too

Login into Otobo and click the CMDB tab to see the contacts and licenses.
